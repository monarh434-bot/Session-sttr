import os
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import (
    ApiIdInvalid, PhoneNumberInvalid, PhoneCodeInvalid,
    PhoneCodeExpired, SessionPasswordNeeded, PasswordHashInvalid
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Токен бота-генератора (отдельный бот!) ===
BOT_TOKEN = os.environ.get("GEN_BOT_TOKEN", "9ca11338796d375b98ab716bc20603d7")
API_ID = int(os.environ.get("API_ID", 730880))
API_HASH = os.environ.get("API_HASH", "8452616761:AAE7E-cadqGwikNwn44b-evrzdSCdFsN8Zw")

# Хранилище состояний пользователей
user_sessions = {}

bot = Client(
    "session_gen_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)


@bot.on_message(filters.command("start") & filters.private)
async def start(client: Client, message: Message):
    uid = message.from_user.id
    user_sessions[uid] = {"step": "idle"}
    await message.reply(
        "👋 Привет! Я помогу сгенерировать SESSION_STRING для юзербота.\n\n"
        "⚠️ **Важно:** Сессия даёт полный доступ к аккаунту. "
        "Никому не передавай SESSION_STRING кроме своего сервера!\n\n"
        "Напиши /generate чтобы начать."
    )


@bot.on_message(filters.command("generate") & filters.private)
async def generate(client: Client, message: Message):
    uid = message.from_user.id
    user_sessions[uid] = {"step": "wait_phone"}
    await message.reply(
        "📱 Введи номер телефона в международном формате:\n"
        "Пример: `+79991234567`"
    )


@bot.on_message(filters.private & filters.text & ~filters.command(["start", "generate"]))
async def handle_input(client: Client, message: Message):
    uid = message.from_user.id
    text = message.text.strip()

    if uid not in user_sessions or user_sessions[uid].get("step") == "idle":
        await message.reply("Напиши /generate чтобы начать генерацию сессии.")
        return

    step = user_sessions[uid]["step"]

    # === Шаг 1: получили номер телефона ===
    if step == "wait_phone":
        phone = text
        await message.reply("⏳ Отправляю код на номер...")

        try:
            tmp_client = Client(
                f"tmp_{uid}",
                api_id=API_ID,
                api_hash=API_HASH,
                in_memory=True,
            )
            await tmp_client.connect()
            sent = await tmp_client.send_code(phone)
            user_sessions[uid] = {
                "step": "wait_code",
                "phone": phone,
                "phone_code_hash": sent.phone_code_hash,
                "client": tmp_client,
            }
            await message.reply(
                "✅ Код отправлен в Telegram!\n\n"
                "Введи код через пробел между цифрами:\n"
                "Пример: `1 2 3 4 5`\n\n"
                "_(пробелы нужны чтобы Telegram не счёл это за реальный код)_"
            )
        except PhoneNumberInvalid:
            await message.reply("❌ Неверный номер телефона. Попробуй снова /generate")
        except ApiIdInvalid:
            await message.reply("❌ Неверный API_ID или API_HASH на сервере.")
        except Exception as e:
            await message.reply(f"❌ Ошибка: {e}")

    # === Шаг 2: получили код ===
    elif step == "wait_code":
        code = text.replace(" ", "")
        tmp_client = user_sessions[uid]["client"]
        phone = user_sessions[uid]["phone"]
        phone_code_hash = user_sessions[uid]["phone_code_hash"]

        try:
            await tmp_client.sign_in(phone, phone_code_hash, code)
            session_string = await tmp_client.export_session_string()
            await tmp_client.disconnect()

            user_sessions[uid] = {"step": "idle"}
            await message.reply(
                f"🎉 **SESSION_STRING сгенерирована!**\n\n"
                f"`{session_string}`\n\n"
                f"📋 Скопируй и вставь в переменные Railway как `SESSION_STRING`\n\n"
                f"⚠️ Сохрани в надёжном месте и никому не передавай!"
            )
        except PhoneCodeInvalid:
            await message.reply("❌ Неверный код. Попробуй снова /generate")
        except PhoneCodeExpired:
            await message.reply("❌ Код истёк. Попробуй снова /generate")
        except SessionPasswordNeeded:
            user_sessions[uid]["step"] = "wait_password"
            user_sessions[uid]["client"] = tmp_client
            await message.reply(
                "🔐 У тебя включена двухфакторная аутентификация.\n"
                "Введи пароль от Telegram:"
            )
        except Exception as e:
            await message.reply(f"❌ Ошибка: {e}")

    # === Шаг 3: двухфакторный пароль ===
    elif step == "wait_password":
        password = text
        tmp_client = user_sessions[uid]["client"]

        try:
            await tmp_client.check_password(password)
            session_string = await tmp_client.export_session_string()
            await tmp_client.disconnect()

            user_sessions[uid] = {"step": "idle"}
            await message.reply(
                f"🎉 **SESSION_STRING сгенерирована!**\n\n"
                f"`{session_string}`\n\n"
                f"📋 Скопируй и вставь в переменные Railway как `SESSION_STRING`\n\n"
                f"⚠️ Сохрани в надёжном месте и никому не передавай!"
            )
        except PasswordHashInvalid:
            await message.reply("❌ Неверный пароль. Попробуй снова /generate")
        except Exception as e:
            await message.reply(f"❌ Ошибка: {e}")


async def main():
    logger.info("Session generator bot started...")
    await bot.start()
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
