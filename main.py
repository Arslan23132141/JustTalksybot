from aiogram.enums import ParseMode
import asyncio
import os
import json
import logging
from datetime import datetime, timedelta
from datetime import datetime

from aiogram.client.default import DefaultBotProperties
from db import get_user, save_user, get_matching_profiles, update_user_like

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# БД-файл
DB_FILE = "data/users.json"
LIKE_LIMIT_PER_DAY = 200
LIKE_RESET_HOURS = 24
# Загрузка из файла + создание если нет
os.makedirs("data", exist_ok=True)  # гарантируем, что папка data есть

if not os.path.exists(DB_FILE):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f, ensure_ascii=False, indent=2)

try:
    with open(DB_FILE, "r", encoding="utf-8") as f:
        users = json.load(f)
except (json.JSONDecodeError, FileNotFoundError):
    users = {}

# Временное хранилище при заполнении анкеты и входящих лайков
temp_profiles = {}
pending_likes = {}
user_likes = {}

questions = ["name", "gender", "age", "city", "looking_for", "about", "media"]

@dp.message(Command("start"))
async def cmd_start(msg: Message):
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🚀 Начать")]], resize_keyboard=True)
    await msg.answer("👋 Привет! Добро пожаловать в Just Talksy — место, где находят друзей, флиртуют и просто весело проводят время 🌼\nНажми кнопку ниже, чтобы начать 🔥", reply_markup=kb)
    kb = ReplyKeyboardMarkup([[KeyboardButton("🚀 Начать")]], resize_keyboard=True)
    await msg.answer("👋 Привет! Добро пожаловать в Just Talksy! Жми 🚀 Начать, чтобы заполнить анкету.", reply_markup=kb)

@dp.message(F.text == "🚀 Начать")
async def start_questionnaire(msg: Message):
    user_id = str(msg.from_user.id)
    user_id = msg.from_user.id
    temp_profiles[user_id] = {"step": 0}
    await msg.answer("💬 Введи своё имя:", reply_markup=ReplyKeyboardRemove())

@dp.message()
async def collect_profile(msg: Message):
    user_id = str(msg.from_user.id)
    now = datetime.now().isoformat()

    if user_id in users:
        if msg.text == "🔍 Найти":
            await show_profile(msg)
            return
        elif msg.text == "✏️ Изменить анкету":
            temp_profiles[user_id] = {"step": 0}
            await msg.answer("💬 Введи своё имя:", reply_markup=ReplyKeyboardRemove())
            return
        elif msg.text == "⚙️ Настройки":
            await msg.answer("Настройки пока недоступны.")
            return
    user_id = msg.from_user.id
    now = datetime.utcnow()

    user = await get_user(user_id)
    if user and msg.text == "🔍 Найти":
        return await show_profile(msg)

    if user and msg.text == "✏️ Изменить анкету":
        temp_profiles[user_id] = {"step": 0}
        return await msg.answer("💬 Введи своё имя:", reply_markup=ReplyKeyboardRemove())

    if user and msg.text == "⚙️ Настройки":
        return await msg.answer("Настройки пока недоступны.")

    if user_id not in temp_profiles:
        await msg.answer("Нажми /start, чтобы начать.")
        return
        return await msg.answer("Нажми /start, чтобы начать.")

    profile = temp_profiles[user_id]
    step = profile["step"]

    if questions[step] == "name":
        profile["name"] = msg.text
        profile["step"] += 1
        kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Парень")], [KeyboardButton(text="Девушка")]], resize_keyboard=True)
        await msg.answer("🧑 Выбери свой пол:", reply_markup=kb)
        return await msg.answer("Укажи свой пол (Парень/Девушка):")

    elif questions[step] == "gender":
        if msg.text not in ["Парень", "Девушка"]:
            await msg.answer("Пожалуйста, выбери кнопку: Парень или Девушка")
            return
        profile["gender"] = msg.text
        profile["step"] += 1
        await msg.answer("📅 Укажи свой возраст:", reply_markup=ReplyKeyboardRemove())
        return await msg.answer("Сколько тебе лет?")

    elif questions[step] == "age":
        if not msg.text.isdigit():
            await msg.answer("Введи возраст числом")
            return
            return await msg.answer("Возраст должен быть числом. Попробуй ещё раз:")
        profile["age"] = int(msg.text)
        profile["step"] += 1
        await msg.answer("📍 Напиши свой город:")
        return await msg.answer("Из какого ты города?")

    elif questions[step] == "city":
        profile["city"] = msg.text.strip().lower()
        profile["city"] = msg.text
        profile["step"] += 1
        kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Парня")], [KeyboardButton(text="Девушку")], [KeyboardButton(text="Друзей")]], resize_keyboard=True)
        await msg.answer("👀 Кого ты ищешь?", reply_markup=kb)
        return await msg.answer("Кого ты ищешь? (Парня/Девушку):")

    elif questions[step] == "looking_for":
        if msg.text not in ["Парня", "Девушку", "Друзей"]:
            await msg.answer("Пожалуйста, выбери подходящий вариант")
            return
        profile["looking_for"] = msg.text
        profile["target_gender"] = msg.text
        profile["step"] += 1
        await msg.answer("✍️ Напиши коротко о себе:", reply_markup=ReplyKeyboardRemove())
        return await msg.answer("Напиши немного о себе:")

    elif questions[step] == "about":
        profile["about"] = msg.text
        profile["description"] = msg.text
        profile["step"] += 1
        await msg.answer("📸 Пришли фото или видео профиля")
        return await msg.answer("Отправь свою фотографию:")

    elif questions[step] == "media":
        if not msg.photo and not msg.video:
            await msg.answer("Пожалуйста, отправь фото или видео")
            return
        profile["media"] = msg.photo[-1].file_id if msg.photo else msg.video.file_id
        profile["media_type"] = "photo" if msg.photo else "video"

        users[user_id] = {
            "name": profile["name"],
            "gender": profile["gender"],
            "age": profile["age"],
            "city": profile["city"],
            "looking_for": profile["looking_for"],
            "about": profile["about"],
            "media": profile["media"],
            "media_type": profile["media_type"],
            "username": msg.from_user.username,
            "shown": [],
            "likes": [],
            "skips": {},
            "like_times": [],
            "last_active": now
        }
        if not msg.photo:
            return await msg.answer("Пожалуйста, отправь фото.")

        profile["photo_id"] = msg.photo[-1].file_id
        profile["user_id"] = user_id
        profile["username"] = msg.from_user.username
        profile["last_active"] = now

        await save_user(profile)
        del temp_profiles[user_id]
        save_db()

        kb = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="🔍 Найти")],
            [KeyboardButton(text="✏️ Изменить анкету")],
            [KeyboardButton(text="⚙️ Настройки")]
        kb = ReplyKeyboardMarkup([
            [KeyboardButton("🔍 Найти")],
            [KeyboardButton("✏️ Изменить анкету")],
            [KeyboardButton("⚙️ Настройки")]
        ], resize_keyboard=True)

        await msg.answer("✅ Отлично! Твоя анкета готова!", reply_markup=kb)

        if user_id in pending_likes:
            for liker_id in pending_likes[user_id]:
                gender = "понравился" if users[liker_id]["gender"] == "Парень" else "понравилась"
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="❤️ Принять", callback_data=f"matchlike_{liker_id}"),
                     InlineKeyboardButton(text="👎 Отказ", callback_data="match_no")]
                ])
                await bot.send_message(chat_id=user_id, text=f"💌 Похоже, ты кому-то {gender}!", reply_markup=kb)
                gender = ("понравился" if profile["gender"] == "Парень" else "понравилась")
                kb2 = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("❤️ Принять", callback_data=f"matchlike_{liker_id}"),
                        InlineKeyboardButton("👎 Отказ", callback_data="match_no")
                    ]])
                await bot.send_message(user_id, f"💌 Похоже, ты кому-то {gender}!", reply_markup=kb2)
            del pending_likes[user_id]

async def show_profile(msg: Message):
    user_id = str(msg.from_user.id)
    now = datetime.now()

    if user_id not in users:
        await msg.answer("❌ Заполни анкету сначала с помощью /start")
        return

    def clean_old_profiles():
        to_delete = []
        for uid, u in users.items():
            last = datetime.fromisoformat(u.get("last_active", now.isoformat()))
            if (now - last).days >= 30:
                to_delete.append(uid)
        for uid in to_delete:
            users.pop(uid)
        for u in users.values():
            u["shown"] = [sid for sid in u["shown"] if sid in users]
        if to_delete:
            save_db()

    clean_old_profiles()

    current_user = users[user_id]

    times = [datetime.fromisoformat(t) for t in current_user.get("like_times", [])]
    times = [t for t in times if (now - t).total_seconds() < LIKE_RESET_HOURS * 3600]
    current_user["like_times"] = [t.isoformat() for t in times]  # очистка старых
    if len(times) >= LIKE_LIMIT_PER_DAY:
        await msg.answer("Ты достиг лимита лайков на сегодня (200). Попробуй позже.")
        return

    for uid, u in users.items():
        if uid == user_id:
            continue
        if u["city"] != current_user["city"]:
            continue
        if abs(u["age"] - current_user["age"]) > 3:
            continue
        if uid in current_user["shown"]:
            last = current_user["skips"].get(uid)
            if last and (now - datetime.fromisoformat(last)).days < 1:
                continue

        current_user["shown"].append(uid)
        save_db()

        media_type = u.get("media_type", "photo")
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❤️", callback_data=f"like_{uid}"),
             InlineKeyboardButton(text="👎", callback_data=f"skip_{uid}")]
        ])

        caption = f"<b>{u['name']}, {u['age']}</b>\n{u['about']}\n👀 Ищет: {u['looking_for']}"

        if media_type == "photo":
            await msg.answer_photo(photo=u["media"], caption=caption, reply_markup=markup)
        else:
            await msg.answer_video(video=u["media"], caption=caption, reply_markup=markup)
        return

    await msg.answer("Анкет больше нет 😔")
    user_id = msg.from_user.id
    current = await get_user(user_id)
    if not current:
        return await msg.answer("❌ Сначала заполни анкету с помощью /start")

    candidates = await get_matching_profiles(current)
    if not candidates:
        return await msg.answer("Анкет больше нет 😔")

    u = candidates[0]
    text = f"<b>{u['name']}, {u['age']}</b>\nГород: {u['city']}\nО себе: {u['description']}"
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("❤️", callback_data=f"like_{u['user_id']}"),
            InlineKeyboardButton("👎", callback_data=f"skip_{u['user_id']}")
        ]])
    await msg.answer_photo(photo=u["photo_id"], caption=text, reply_markup=kb)

@dp.callback_query()
async def handle_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = callback.data

    if user_id not in users:
        await callback.message.answer("❌ Пожалуйста, сначала заполни анкету.")
        await callback.answer()
        return

    current_user = users[user_id]
    now = datetime.now().isoformat()
    from_id = callback.from_user.id

    if data.startswith("like_"):
        liked_id = data.split("_")[1]
        if liked_id not in current_user["likes"]:
            current_user["likes"].append(liked_id)
        current_user["like_times"].append(now)
        current_user["like_times"] = [
            t for t in current_user["like_times"]
            if (datetime.now() - datetime.fromisoformat(t)).total_seconds() < LIKE_RESET_HOURS * 3600
        ]
        save_db()

        if liked_id in users and user_id in users[liked_id]["likes"]:
            gender = "понравился" if current_user["gender"] == "Парень" else "понравилась"
            if users[liked_id].get("username"):
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="❤️ Принять", callback_data=f"matchlike_{user_id}"),
                     InlineKeyboardButton(text="👎 Отказ", callback_data="match_no")]
                ])
                await bot.send_message(chat_id=liked_id, text=f"💌 Похоже, ты кому-то {gender}!", reply_markup=kb)
        else:
            pending_likes.setdefault(liked_id, []).append(user_id)

        await callback.message.edit_reply_markup(reply_markup=None)
        await asyncio.sleep(0.2)
        await show_profile(callback.message)
        to_id = int(data.split("_")[1])
        await update_user_like(from_id, to_id, liked=True)
        other_user = await get_user(to_id)
        if other_user:
            if other_user.get("likes") and from_id in other_user["likes"]:
                kb = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("❤️ Принять", callback_data=f"matchlike_{from_id}"),
                        InlineKeyboardButton("👎 Отказ", callback_data="match_no")
                    ]])
                await bot.send_message(to_id, "💌 Похоже, ты кому-то понравился(ась)!", reply_markup=kb)
        await callback.message.edit_reply_markup()
        await callback.answer("Лайк!")

    elif data.startswith("skip_"):
        skipped_id = data.split("_")[1]
        current_user["skips"][skipped_id] = now
        save_db()
        await callback.message.edit_reply_markup(reply_markup=None)
        await asyncio.sleep(0.2)
        await show_profile(callback.message)
        to_id = int(data.split("_")[1])
        await update_user_like(from_id, to_id, liked=False)
        await callback.message.edit_reply_markup()
        await callback.answer("Пропущено")

    elif data.startswith("matchlike_"):
        liked_user_id = data.split("_")[1]
        liked_user = users.get(liked_user_id)
        if liked_user:
            if liked_user.get("username"):
                media_type = liked_user.get("media_type", "photo")
                caption = f"🎉 У вас взаимная симпатия!\n👉 @{liked_user['username']}\n<b>{liked_user['name']}, {liked_user['age']}</b>\n{liked_user['about']}"
                if media_type == "photo":
                    await bot.send_photo(chat_id=user_id, photo=liked_user['media'], caption=caption)
                else:
                    await bot.send_video(chat_id=user_id, video=liked_user['media'], caption=caption)
            else:
                await bot.send_message(chat_id=user_id, text="🎉 У вас взаимная симпатия! Но у этого пользователя нет username 😔")
        liker_id = int(data.split("_")[1])
        liker = await get_user(liker_id)
        current = await get_user(callback.from_user.id)

    elif data == "match_no":
        await callback.answer("Отказ отправлен.")
        liker_link = f"@{liker['username']}" if liker.get("username") else f"<code>{liker_id}</code>"
        current_link = f"@{current['username']}" if current.get("username") else f"<code>{callback.from_user.id}</code>"

        await bot.send_message(liker_id, f"🎉 У вас новая пара!\nТы можешь написать: {current_link}")
        await bot.send_message(callback.from_user.id, f"🎉 Пара принята!\nТы можешь написать: {liker_link}")
        await callback.message.delete()

    await callback.answer()
    elif data == "match_no":
        await callback.message.delete()

def save_db():
    os.makedirs("data", exist_ok=True)
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)
    logging.info(f"DB saved with {len(users)} users.")
    
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
