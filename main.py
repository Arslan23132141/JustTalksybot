from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.enums import ParseMode
import asyncio
import logging
from datetime import datetime

from db import get_user, save_user, get_matching_profiles, update_user_like

logging.basicConfig(level=logging.INFO)
BOT_TOKEN = "ТОКЕН_ТВОЕГО_БОТА"
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

LIKE_LIMIT_PER_DAY = 200
LIKE_RESET_HOURS = 24

temp_profiles = {}
pending_likes = {}
user_likes = {}

questions = ["name", "gender", "age", "city", "looking_for", "about", "media"]

@dp.message(Command("start"))
async def cmd_start(msg: Message):
    kb = ReplyKeyboardMarkup([[KeyboardButton("🚀 Начать")]], resize_keyboard=True)
    await msg.answer("👋 Привет! Добро пожаловать в Just Talksy! Жми 🚀 Начать, чтобы заполнить анкету.", reply_markup=kb)

@dp.message(F.text == "🚀 Начать")
async def start_questionnaire(msg: Message):
    user_id = msg.from_user.id
    temp_profiles[user_id] = {"step": 0}
    await msg.answer("💬 Введи своё имя:", reply_markup=ReplyKeyboardRemove())

@dp.message()
async def collect_profile(msg: Message):
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
        return await msg.answer("Нажми /start, чтобы начать.")

    profile = temp_profiles[user_id]
    step = profile["step"]

    if questions[step] == "name":
        profile["name"] = msg.text
        profile["step"] += 1
        return await msg.answer("Укажи свой пол (Парень/Девушка):")

    elif questions[step] == "gender":
        profile["gender"] = msg.text
        profile["step"] += 1
        return await msg.answer("Сколько тебе лет?")

    elif questions[step] == "age":
        if not msg.text.isdigit():
            return await msg.answer("Возраст должен быть числом. Попробуй ещё раз:")
        profile["age"] = int(msg.text)
        profile["step"] += 1
        return await msg.answer("Из какого ты города?")

    elif questions[step] == "city":
        profile["city"] = msg.text
        profile["step"] += 1
        return await msg.answer("Кого ты ищешь? (Парня/Девушку):")

    elif questions[step] == "looking_for":
        profile["target_gender"] = msg.text
        profile["step"] += 1
        return await msg.answer("Напиши немного о себе:")

    elif questions[step] == "about":
        profile["description"] = msg.text
        profile["step"] += 1
        return await msg.answer("Отправь свою фотографию:")

    elif questions[step] == "media":
        if not msg.photo:
            return await msg.answer("Пожалуйста, отправь фото.")

        profile["photo_id"] = msg.photo[-1].file_id
        profile["user_id"] = user_id
        profile["username"] = msg.from_user.username
        profile["last_active"] = now

        await save_user(profile)
        del temp_profiles[user_id]

        kb = ReplyKeyboardMarkup([
            [KeyboardButton("🔍 Найти")],
            [KeyboardButton("✏️ Изменить анкету")],
            [KeyboardButton("⚙️ Настройки")]
        ], resize_keyboard=True)

        await msg.answer("✅ Отлично! Твоя анкета готова!", reply_markup=kb)

        if user_id in pending_likes:
            for liker_id in pending_likes[user_id]:
                gender = ("понравился" if profile["gender"] == "Парень" else "понравилась")
                kb2 = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("❤️ Принять", callback_data=f"matchlike_{liker_id}"),
                        InlineKeyboardButton("👎 Отказ", callback_data="match_no")
                    ]])
                await bot.send_message(user_id, f"💌 Похоже, ты кому-то {gender}!", reply_markup=kb2)
            del pending_likes[user_id]

async def show_profile(msg: Message):
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
    data = callback.data
    from_id = callback.from_user.id

    if data.startswith("like_"):
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
        to_id = int(data.split("_")[1])
        await update_user_like(from_id, to_id, liked=False)
        await callback.message.edit_reply_markup()
        await callback.answer("Пропущено")

    elif data.startswith("matchlike_"):
        liker_id = int(data.split("_")[1])
        liker = await get_user(liker_id)
        current = await get_user(callback.from_user.id)

        liker_link = f"@{liker['username']}" if liker.get("username") else f"<code>{liker_id}</code>"
        current_link = f"@{current['username']}" if current.get("username") else f"<code>{callback.from_user.id}</code>"

        await bot.send_message(liker_id, f"🎉 У вас новая пара!\nТы можешь написать: {current_link}")
        await bot.send_message(callback.from_user.id, f"🎉 Пара принята!\nТы можешь написать: {liker_link}")
        await callback.message.delete()

    elif data == "match_no":
        await callback.message.delete()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
