import asyncio
import secrets
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

TOKEN = "8711798783:AAGCkdPILh20kBDzQHWvYM5EXmaaPbahn50"
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Хранилища в памяти (не сохраняются после перезапуска)
pending_invites = {}   # {token: creator_user_id}
active_chats = {}      # {user_id: partner_user_id}

# Предупреждение о мошенниках
WARNING = (
    "⚠️ <b>Обращение к пользователям:</b>\n\n"
    "Этот бот часто используется для обмана. "
    "Если вам предлагают перевести деньги за запрещённые вещества — это ОБМАН! "
    "У вас просто заберут деньги и закроют чат.\n"
    "Разработчик не сохраняет логи и не сможет помочь — мы бережём приватность.\n"
    "Берегите свои деньги и будьте внимательны!"
)

# Клавиатура с основными кнопками
def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔗 Создать чат")],
            [KeyboardButton(text="❌ Выйти из чата")]
        ],
        resize_keyboard=True
    )

# ================= ОБРАБОТЧИКИ КОМАНД =================
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    # Если перешли по ссылке с параметром join_<token>
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("join_"):
        token = args[1][5:]
        if token in pending_invites:
            creator_id = pending_invites[token]
            if creator_id == message.from_user.id:
                await message.answer("❌ Нельзя подключиться к самому себе.")
                return
            if creator_id in active_chats or message.from_user.id in active_chats:
                await message.answer("❌ Один из вас уже состоит в чате.")
                return
            # Связываем пользователей
            active_chats[creator_id] = message.from_user.id
            active_chats[message.from_user.id] = creator_id
            del pending_invites[token]  # одноразовый токен
            await message.answer("✅ Собеседник вошёл в чат. Приятного общения!", reply_markup=main_keyboard())
            await bot.send_message(creator_id, "✅ Твой собеседник вошёл в чат. Приятного общения!", reply_markup=main_keyboard())
        else:
            await message.answer("❌ Ссылка недействительна или чат уже создан.")
    else:
        # Обычный /start
        await message.answer(
            "👋 Приватный чат.\n\n" + WARNING,
            parse_mode="HTML",
            reply_markup=main_keyboard()
        )

@dp.message(Command("stop"))
async def stop_cmd(message: types.Message):
    await leave_chat(message)

# ================= КНОПКИ =================
@dp.message(F.text == "🔗 Создать чат")
async def create_chat(message: types.Message):
    user_id = message.from_user.id
    if user_id in active_chats:
        await message.answer("❌ Вы уже состоите в чате. Сначала выйдите из него.")
        return
    # Генерируем уникальный токен
    token = secrets.token_urlsafe(24)
    pending_invites[token] = user_id
    bot_username = (await bot.me()).username
    link = f"https://t.me/{bot_username}?start=join_{token}"
    await message.answer(
        f"🔗 Отправьте эту ссылку собеседнику:\n{link}\n\n{WARNING}",
        disable_web_page_preview=True,
        parse_mode="HTML"
    )

@dp.message(F.text == "❌ Выйти из чата")
async def leave_chat_button(message: types.Message):
    await leave_chat(message)

async def leave_chat(message: types.Message):
    user_id = message.from_user.id
    partner_id = active_chats.pop(user_id, None)
    if partner_id:
        active_chats.pop(partner_id, None)
        await message.answer("🚪 Вы вышли из чата.", reply_markup=main_keyboard())
        await bot.send_message(partner_id, "🚪 Собеседник покинул чат.", reply_markup=main_keyboard())
    else:
        await message.answer("❌ Вы не состоите в чате.")

# ================= ПЕРЕСЫЛКА СООБЩЕНИЙ =================
@dp.message(F.text)
async def forward_message(message: types.Message):
    user_id = message.from_user.id
    if user_id in active_chats:
        partner_id = active_chats[user_id]
        await bot.send_message(partner_id, f"💬 Собеседник: {message.text}")
    else:
        await message.answer("Вы не в чате. Используйте /start и создайте новый чат.")

# ================= ЗАПУСК =================
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
