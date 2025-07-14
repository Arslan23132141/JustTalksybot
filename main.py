from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.enums import ParseMode
import asyncio
import os
import json
from datetime import datetime, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# БД-файл
DB_FILE = "users.json"
LIKE_LIMIT_PER_DAY = 200
LIKE_RESET_HOURS = 24

# Загрузка из файла
if os.path.exists(DB_FILE):
    with open(DB_FILE, "r", encoding="utf-8") as f:
        users = json.load(f)
else:
    users = {}

# Временное хранилище при заполнении анкеты
temp_profiles = {}

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

        users[user_id] = {
            "name": profile["name"],
            "gender": profile["gender"],
            "age": profile["age"],
            "city": profile["city"],
            "looking_for": profile["looking_for"],
            "about": profile["about"],
            "media": profile["media"],
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

def save_db():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def clean_old_profiles():
    now = datetime.now()
    to_delete = []
    for uid, u in users.items():
        last = datetime.fromisoformat(u.get("last_active", now.isoformat()))
        if (now - last).days >= 30:
            to_delete.append(uid)
    for uid in to_delete:
        users.pop(uid)
    if to_delete:
        save_db()

async def show_profile(msg: Message):
    user_id = str(msg.from_user.id)
    now = datetime.now()
    clean_old_profiles()

    current_user = users[user_id]

    # Проверка лимита лайков
    times = [datetime.fromisoformat(t) for t in current_user.get("like_times", [])]
    times = [t for t in times if (now - t).total_seconds() < LIKE_RESET_HOURS * 3600]
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

        media_type = "photo" if u["media"].startswith("AgAC") else "video"
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❤️", callback_data=f"like_{uid}"),
             InlineKeyboardButton(text="👎", callback_data=f"skip_{uid}")]
        ])

        caption = f"<b>{u['name']}, {u['age']}</b>\n{u['about']}\n👀 Ищет: {u['looking_for']}\n"
        if u.get("username"):
            caption += f"@{u['username']}"

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
    current_user = users[user_id]
    now = datetime.now().isoformat()

    if data.startswith("like_"):
        liked_id = data.split("_")[1]
        current_user["likes"].append(liked_id)
        current_user["like_times"].append(now)
        save_db()

        if user_id in users[liked_id]["likes"]:
            gender = "понравился" if current_user["gender"] == "Парень" else "понравилась"
            username = callback.from_user.username
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❤️ Принять", url=f"https://t.me/{username}" if username else "")],
                [InlineKeyboardButton(text="👎 Отказ", callback_data="match_no")]
            ])
            await bot.send_message(chat_id=liked_id, text=f"💌 Похоже, ты кому-то {gender}!", reply_markup=kb)

        await callback.message.edit_text("❤️ Ты лайкнул анкету!")

    elif data.startswith("skip_"):
        skipped_id = data.split("_")[1]
        current_user["skips"][skipped_id] = now
        save_db()
        await callback.message.edit_text("👎 Пропущено")

    await callback.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
