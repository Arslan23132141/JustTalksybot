from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.enums import ParseMode
import asyncio
import os
import json
import logging
from datetime import datetime, timedelta

from aiogram.client.default import DefaultBotProperties

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
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

questions = ["name", "gender", "age", "city", "looking_for", "about", "media"]

@dp.message(Command("start"))
async def cmd_start(msg: Message):
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🚀 Начать")]], resize_keyboard=True)
    await msg.answer("👋 Привет! Добро пожаловать в Just Talksy — место, где находят друзей, флиртуют и просто весело проводят время 🌼\nНажми кнопку ниже, чтобы начать 🔥", reply_markup=kb)

@dp.message(F.text == "🚀 Начать")
async def start_questionnaire(msg: Message):
    user_id = str(msg.from_user.id)
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

    if user_id not in temp_profiles:
        await msg.answer("Нажми /start, чтобы начать.")
        return

    profile = temp_profiles[user_id]
    step = profile["step"]

    if questions[step] == "name":
        profile["name"] = msg.text
        profile["step"] += 1
        kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Парень")], [KeyboardButton(text="Девушка")]], resize_keyboard=True)
        await msg.answer("🧑 Выбери свой пол:", reply_markup=kb)

    elif questions[step] == "gender":
        if msg.text not in ["Парень", "Девушка"]:
            await msg.answer("Пожалуйста, выбери кнопку: Парень или Девушка")
            return
        profile["gender"] = msg.text
        profile["step"] += 1
        await msg.answer("📅 Укажи свой возраст:", reply_markup=ReplyKeyboardRemove())

    elif questions[step] == "age":
        if not msg.text.isdigit():
            await msg.answer("Введи возраст числом")
            return
        profile["age"] = int(msg.text)
        profile["step"] += 1
        await msg.answer("📍 Напиши свой город:")

    elif questions[step] == "city":
        profile["city"] = msg.text.strip().lower()
        profile["step"] += 1
        kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Парня")], [KeyboardButton(text="Девушку")], [KeyboardButton(text="Друзей")]], resize_keyboard=True)
        await msg.answer("👀 Кого ты ищешь?", reply_markup=kb)

    elif questions[step] == "looking_for":
        if msg.text not in ["Парня", "Девушку", "Друзей"]:
            await msg.answer("Пожалуйста, выбери подходящий вариант")
            return
        profile["looking_for"] = msg.text
        profile["step"] += 1
        await msg.answer("✍️ Напиши коротко о себе:", reply_markup=ReplyKeyboardRemove())

    elif questions[step] == "about":
        profile["about"] = msg.text
        profile["step"] += 1
        await msg.answer("📸 Пришли фото или видео профиля")

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
        del temp_profiles[user_id]
        save_db()

        kb = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="🔍 Найти")],
            [KeyboardButton(text="✏️ Изменить анкету")],
            [KeyboardButton(text="⚙️ Настройки")]
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

@dp.callback_query()
async def handle_callback(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    data = callback.data

    if user_id not in users:
        await callback.message.answer("❌ Пожалуйста, сначала заполни анкету.")
        await callback.answer()
        return

    current_user = users[user_id]
    now = datetime.now().isoformat()

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

    elif data.startswith("skip_"):
        skipped_id = data.split("_")[1]
        current_user["skips"][skipped_id] = now
        save_db()
        await callback.message.edit_reply_markup(reply_markup=None)
        await asyncio.sleep(0.2)
        await show_profile(callback.message)

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

    elif data == "match_no":
        await callback.answer("Отказ отправлен.")

    await callback.answer()

def save_db():
    os.makedirs("data", exist_ok=True)
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)
    logging.info(f"DB saved with {len(users)} users.")
    
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
