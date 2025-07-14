from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode
import asyncio
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

users = {}

@dp.message(Command("start"))
async def start(msg: Message):
    await msg.answer("Привет! Введи коротко о себе (анкета):")

@dp.message()
async def handle_profile(msg: Message):
    user_id = msg.from_user.id
    if user_id not in users:
        users[user_id] = {
            "text": msg.text,
            "shown": []
        }
        await msg.answer("Анкета сохранена! Введи /search чтобы искать других.")
    else:
        await msg.answer("Команда не распознана. Введи /search.")

@dp.message(Command("search"))
async def search(msg: Message):
    user_id = msg.from_user.id
    for uid, u in users.items():
        if uid != user_id and uid not in users[user_id]["shown"]:
            users[user_id]["shown"].append(uid)
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="❤️", callback_data=f"like_{uid}"),
                 types.InlineKeyboardButton(text="👎", callback_data=f"skip_{uid}")]
            ])
            await msg.answer(f"Анкета:\n{u['text']}", reply_markup=kb)
            return
    await msg.answer("Анкет больше нет 😔")

@dp.callback_query()
async def callbacks(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = callback.data
    if data.startswith("like_"):
        liked_id = int(data.split("_")[1])
        await callback.message.edit_text("❤️ Ты лайкнул анкету!")
    elif data.startswith("skip_"):
        await callback.message.edit_text("👎 Пропущено")
    await callback.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
