import os
import psycopg
from datetime import datetime


DB_URL = os.getenv("DB_URL")  # Переменная среды из Railway

# ⏳ Подключение к базе (асинхронно)
async def connect():
    return await psycopg.AsyncConnection.connect(DB_URL)


# ✅ Сохранить или обновить анкету
async def save_user(user_data: dict):
    async with await connect() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO users (user_id, name, gender, age, city, looking_for, about, media, media_type, username, shown, likes, skips, like_times, last_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE
                SET name = EXCLUDED.name,
                    gender = EXCLUDED.gender,
                    age = EXCLUDED.age,
                    city = EXCLUDED.city,
                    looking_for = EXCLUDED.looking_for,
                    about = EXCLUDED.about,
                    media = EXCLUDED.media,
                    media_type = EXCLUDED.media_type,
                    username = EXCLUDED.username,
                    shown = EXCLUDED.shown,
                    likes = EXCLUDED.likes,
                    skips = EXCLUDED.skips,
                    like_times = EXCLUDED.like_times,
                    last_active = EXCLUDED.last_active;
            """, (
                user_data["user_id"],
                user_data.get("name"),
                user_data.get("gender"),
                user_data.get("age"),
                user_data.get("city"),
                user_data.get("looking_for"),
                user_data.get("about"),
                user_data.get("media"),
                user_data.get("media_type"),
                user_data.get("username"),
                user_data.get("shown", []),
                user_data.get("likes", []),
                psycopg.types.json.Json(user_data.get("skips", {})),
                user_data.get("like_times", []),
                datetime.utcnow()
            ))


# ✅ Получить анкету по user_id
async def get_user(user_id: int):
    async with await connect() as conn:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            return await cur.fetchone()


# ✅ Получить подходящие анкеты по городу и возрасту ±3
async def get_matching_profiles(current_user: dict):
    async with await connect() as conn:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute("""
                SELECT * FROM users
                WHERE city = %s
                  AND gender = %s
                  AND ABS(age - %s) <= 3
                  AND user_id != %s
            """, (
                current_user["city"],
                current_user["looking_for"],
                current_user["age"],
                current_user["user_id"]
            ))
            return await cur.fetchall()
