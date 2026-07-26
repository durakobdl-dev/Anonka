import asyncio
import secrets
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart

TOKEN = "8711798783:AAGCkdPILh20kBDzQHWvYM5EXmaaPbahn50"
bot = Bot(token=TOKEN)
dp = Dispatcher()

pending_invites = {}   # {token: creator_user_id}
active_chats = {}      # {user_id: partner_user_id}

# Тексты сообщений
MSG_CREATED = "[BOT] Создан новый чат. Отправь собеседнику эту ссылку и как только он присоединится к чату, вы сможете общаться."
MSG_ALREADY_CREATED = "[BOT] Чат уже создан. Твой собеседник еще не вошел в чат. Подожди, пока он присоединится или отмени чат командой /stop"
MSG_JOINED = "[BOT] Твой собеседник вошел в чат. Приятного общения!"
MSG_CHAT_ENDED = "[BOT] Чат завершен. Чтобы начать новый чат нажми /start"
MSG_INVALID_LINK = "[BOT] Ссылка недействительна или чат уже создан."
MSG_SELF_CONNECT = "[BOT] Нельзя подключиться к самому себе."

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    args = message.text.split()

    # Если перешли по ссылке с параметром join_<token>
    if len(args) > 1 and args[1].startswith("join_"):
        token = args[1][5:]
        if token in pending_invites:
            creator_id = pending_invites[token]
            if creator_id == user_id:
                await message.answer(MSG_SELF_CONNECT)
                return
            if creator_id in active_chats or user_id in active_chats:
                await message.answer(MSG_CHAT_ENDED)
                return
            # Связываем
            active_chats[creator_id] = user_id
            active_chats[user_id] = creator_id
            del pending_invites[token]
            await message.answer(MSG_JOINED)
            await bot.send_message(creator_id, MSG_JOINED)
        else:
            await message.answer(MSG_INVALID_LINK)
        return

    # Обычный /start
    if user_id in active_chats:
        # Уже есть активный чат
        await message.answer(MSG_ALREADY_CREATED)
        return

    # Создаём новый чат
    token = secrets.token_urlsafe(24)
    pending_invites[token] = user_id
    bot_username = (await bot.me()).username
    link = f"https://t.me/{bot_username}?start=join_{token}"
    await message.answer(MSG_CREATED)
    await message.answer(link, disable_web_page_preview=True)

@dp.message(Command("stop"))
async def stop_cmd(message: types.Message):
    user_id = message.from_user.id
    partner_id = active_chats.pop(user_id, None)
    if partner_id:
        active_chats.pop(partner_id, None)
        await message.answer(MSG_CHAT_ENDED)
        await bot.send_message(partner_id, MSG_CHAT_ENDED)
    else:
        # Если не в чате, но есть ожидающий инвайт – удаляем его
        for token, uid in list(pending_invites.items()):
            if uid == user_id:
                del pending_invites[token]
                await message.answer(MSG_CHAT_ENDED)
                return
        await message.answer("[BOT] Вы не состоите в чате.")

@dp.message(F.text)
async def forward_text(message: types.Message):
    user_id = message.from_user.id
    if user_id in active_chats:
        partner_id = active_chats[user_id]
        await bot.send_message(partner_id, message.text)
    # Если не в чате – игнорируем

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
