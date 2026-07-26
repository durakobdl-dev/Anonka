import asyncio
import secrets
from datetime import datetime, timezone
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
    BotCommand, BotCommandScopeDefault
)

TOKEN = "8711798783:AAGCkdPILh20kBDzQHWvYM5EXmaaPbahn50"
bot = Bot(token=TOKEN)
dp = Dispatcher()

# ---------- АДМИНИСТРАТОРЫ ----------
ADMIN_USERNAMES = ["Woozinoid"]  # без @, замените на свои

# ---------- ХРАНИЛИЩА ----------
pending_invites = {}            # {token: creator_user_id}
active_chats = {}               # {user_id: partner_user_id}
active_chats_log_key = {}       # {user_id: log_key} – активный чат
chat_logs = {}                  # {log_key: [{"from": user_id, "text": str, "time": str}, ...]}
user_info = {}                  # {user_id: {"username": str, "first_name": str}}
banned_users = set()            # {user_id, ...}

# Маппинг сообщений для реакций: {user_id: {original_msg_id: forwarded_msg_id}}
message_map = {}

MOSCOW_TZ = timezone.utc

# ---------- СООБЩЕНИЯ ----------
MSG_CREATED = "[BOT] Создан новый чат. Отправь собеседнику эту ссылку и как только он присоединится к чату, вы сможете общаться."
MSG_ALREADY_CREATED = "[BOT] Чат уже создан. Твой собеседник еще не вошел в чат. Подожди, пока он присоединится или отмени чат командой /stop"
MSG_JOINED = "[BOT] Твой собеседник вошел в чат. Приятного общения!"
MSG_CHAT_ENDED = "[BOT] Чат завершен. Чтобы начать новый чат нажми /start"
MSG_INVALID_LINK = "[BOT] Ссылка недействительна или чат уже создан."
MSG_SELF_CONNECT = "[BOT] Нельзя подключиться к самому себе."
MSG_BANNED = "[BOT] Вы заблокированы."
MSG_ADMIN_MENU = "🔧 Админ‑панель"

WARNING = (
    "⚠️ Обращение к пользователям:\n\n"
    "Этот бот используется для общения. "
    "Если вам предлагают перевести деньги за запрещённые вещества — это ОБМАН! "
    "У вас просто заберут деньги и закроют чат.\n"
    "Разработчик не сохраняет логи и не сможет помочь — мы бережём приватность.\n"
    "Берегите свои деньги и будьте внимательны!"
)

# ---------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ----------
def is_admin(user: types.User) -> bool:
    return user.username is not None and user.username.lower() in [u.lower() for u in ADMIN_USERNAMES]

def update_user_info(user: types.User):
    user_info[user.id] = {
        "username": user.username,
        "first_name": user.first_name
    }

def get_user_display(uid: int) -> str:
    info = user_info.get(uid, {})
    if info.get("username"):
        return f"@{info['username']}"
    if info.get("first_name"):
        return info["first_name"]
    return str(uid)

async def leave_chat(message: types.Message):
    """Завершение чата."""
    user_id = message.from_user.id
    if user_id in banned_users:
        await message.answer(MSG_BANNED)
        return
    partner_id = active_chats.pop(user_id, None)
    if partner_id:
        active_chats.pop(partner_id, None)
        log_key = active_chats_log_key.pop(user_id, None)
        active_chats_log_key.pop(partner_id, None)
        # Очищаем маппинг сообщений для этой пары
        message_map.pop(user_id, None)
        message_map.pop(partner_id, None)
        await message.answer(MSG_CHAT_ENDED)
        await bot.send_message(partner_id, MSG_CHAT_ENDED)
    else:
        for token, uid in list(pending_invites.items()):
            if uid == user_id:
                del pending_invites[token]
                await message.answer(MSG_CHAT_ENDED)
                return
        await message.answer("[BOT] Вы не состоите в чате.")

# ---------- ОБРАБОТЧИКИ КОМАНД ----------
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    update_user_info(message.from_user)

    if user_id in banned_users:
        await message.answer(MSG_BANNED)
        return

    args = message.text.split()
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
            # Создаём чат
            active_chats[creator_id] = user_id
            active_chats[user_id] = creator_id
            del pending_invites[token]
            log_key = f"chat_{datetime.now(MOSCOW_TZ).strftime('%Y%m%d_%H%M%S')}_{creator_id}_{user_id}"
            chat_logs[log_key] = []
            active_chats_log_key[creator_id] = log_key
            active_chats_log_key[user_id] = log_key
            # Инициализируем маппинг сообщений
            message_map[creator_id] = {}
            message_map[user_id] = {}

            await message.answer(WARNING)
            await message.answer(MSG_JOINED)
            await bot.send_message(creator_id, WARNING)
            await bot.send_message(creator_id, MSG_JOINED)
        else:
            await message.answer(MSG_INVALID_LINK)
        return

    if user_id in active_chats:
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
    await leave_chat(message)

@dp.message(Command("admin"))
async def admin_cmd(message: types.Message):
    if not is_admin(message.from_user):
        return
    await message.answer(
        MSG_ADMIN_MENU,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Логи чатов", callback_data="admin_logs")],
            [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
            [InlineKeyboardButton(text="🚫 Бан‑лист", callback_data="admin_banlist")]
        ])
    )

# ---------- ПЕРЕСЫЛКА СООБЩЕНИЙ ----------
@dp.message(F.text, ~F.text.startswith("/"))
async def forward_text(message: types.Message):
    user_id = message.from_user.id
    update_user_info(message.from_user)

    if user_id in banned_users:
        await message.answer(MSG_BANNED)
        return

    partner_id = active_chats.get(user_id)
    if partner_id:
        sent_msg = await bot.send_message(partner_id, message.text)
        # Сохраняем маппинг сообщений для реакций
        if user_id not in message_map:
            message_map[user_id] = {}
        message_map[user_id][message.message_id] = sent_msg.message_id

        # Логирование
        log_key = active_chats_log_key.get(user_id)
        if log_key and log_key in chat_logs:
            chat_logs[log_key].append({
                "from": user_id,
                "text": message.text,
                "time": datetime.now(MOSCOW_TZ).strftime("%Y-%m-%d %H:%M:%S")
            })

@dp.message(F.photo)
async def forward_photo(message: types.Message):
    user_id = message.from_user.id
    update_user_info(message.from_user)

    if user_id in banned_users:
        await message.answer(MSG_BANNED)
        return

    partner_id = active_chats.get(user_id)
    if partner_id:
        photo = message.photo[-1]
        caption = message.caption
        sent_msg = await bot.send_photo(partner_id, photo.file_id, caption=caption)

        if user_id not in message_map:
            message_map[user_id] = {}
        message_map[user_id][message.message_id] = sent_msg.message_id

        log_key = active_chats_log_key.get(user_id)
        if log_key and log_key in chat_logs:
            log_text = "[Фото]" if not caption else f"[Фото: {caption}]"
            chat_logs[log_key].append({
                "from": user_id,
                "text": log_text,
                "time": datetime.now(MOSCOW_TZ).strftime("%Y-%m-%d %H:%M:%S")
            })

# ---------- РЕАКЦИИ ----------
@dp.message_reaction()
async def forward_reaction(message: types.Message, reaction: types.MessageReactionUpdated):
    user_id = message.from_user.id
    if user_id not in active_chats:
        return
    partner_id = active_chats[user_id]

    # Получаем новые реакции (добавленные)
    new_reactions = reaction.new_reaction
    if not new_reactions:
        return

    # Нам нужно отправить реакцию на сообщение собеседнику
    # Для этого нам нужен message_id сообщения у партнёра
    user_map = message_map.get(user_id, {})
    forwarded_msg_id = user_map.get(message.message_id)
    if not forwarded_msg_id:
        # Если не знаем, просто пересылаем эмодзи текстом (на всякий случай)
        emojis = "".join([r.emoji for r in new_reactions if hasattr(r, 'emoji')])
        if emojis:
            await bot.send_message(partner_id, f"Реакция: {emojis}")
        return

    # Отправляем реакцию на сообщение партнёру
    try:
        await bot.set_message_reaction(
            chat_id=partner_id,
            message_id=forwarded_msg_id,
            reaction=[types.ReactionTypeEmoji(emoji=r.emoji) for r in new_reactions if hasattr(r, 'emoji')],
            is_big=False
        )
    except Exception as e:
        # Fallback: текстовая реакция
        emojis = "".join([r.emoji for r in new_reactions if hasattr(r, 'emoji')])
        if emojis:
            await bot.send_message(partner_id, f"Реакция: {emojis}")

# ================= АДМИН‑ПАНЕЛЬ (инлайн) =================
@dp.callback_query(F.data == "admin_logs")
async def show_logs(call: CallbackQuery):
    if not is_admin(call.from_user):
        return await call.answer("Нет доступа")
    if not chat_logs:
        return await call.answer("Нет завершённых чатов")
    kb = []
    for log_key in chat_logs:
        parts = log_key.split("_")
        if len(parts) >= 4:
            time_str = parts[1] + "_" + parts[2]
            uid1 = int(parts[3])
            uid2 = int(parts[4])
            display = f"{get_user_display(uid1)} ↔ {get_user_display(uid2)} ({time_str})"
            kb.append([InlineKeyboardButton(text=display, callback_data=f"viewlog_{log_key}")])
    await call.message.edit_text("Выберите чат для просмотра:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer()

@dp.callback_query(F.data.startswith("viewlog_"))
async def view_log(call: CallbackQuery):
    if not is_admin(call.from_user):
        return await call.answer("Нет доступа")
    log_key = call.data[len("viewlog_"):]
    log = chat_logs.get(log_key)
    if not log:
        return await call.answer("Лог не найден")
    lines = []
    for entry in log:
        sender = get_user_display(entry["from"])
        lines.append(f"[{entry['time']}] {sender}: {entry['text']}")
    text = "\n".join(lines)
    if not text:
        text = "Пустой чат"
    for i in range(0, len(text), 4096):
        await call.message.answer(text[i:i+4096])
    await call.answer("Готово")

@dp.callback_query(F.data == "admin_users")
async def show_users(call: CallbackQuery):
    if not is_admin(call.from_user):
        return await call.answer("Нет доступа")
    if not user_info:
        return await call.answer("Нет пользователей")
    kb = []
    for uid, info in user_info.items():
        display = get_user_display(uid)
        kb.append([InlineKeyboardButton(text=display, callback_data=f"userinfo_{uid}")])
    await call.message.edit_text("Список пользователей:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer()

@dp.callback_query(F.data.startswith("userinfo_"))
async def user_info_cb(call: CallbackQuery):
    if not is_admin(call.from_user):
        return await call.answer("Нет доступа")
    uid = int(call.data.split("_")[1])
    info = user_info.get(uid, {})
    text = f"ID: {uid}\nUsername: {info.get('username') or 'нет'}\nИмя: {info.get('first_name') or 'нет'}"
    is_banned = uid in banned_users
    kb = [
        [InlineKeyboardButton(text="Разбанить" if is_banned else "Забанить",
                              callback_data=f"toggleban_{uid}")],
        [InlineKeyboardButton(text="← Назад", callback_data="admin_users")]
    ]
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer()

@dp.callback_query(F.data.startswith("toggleban_"))
async def toggle_ban(call: CallbackQuery):
    if not is_admin(call.from_user):
        return await call.answer("Нет доступа")
    uid = int(call.data.split("_")[1])
    if uid in banned_users:
        banned_users.remove(uid)
        await call.answer("Пользователь разбанен")
    else:
        banned_users.add(uid)
        if uid in active_chats:
            partner = active_chats.pop(uid)
            active_chats.pop(partner, None)
            active_chats_log_key.pop(uid, None)
            active_chats_log_key.pop(partner, None)
            message_map.pop(uid, None)
            message_map.pop(partner, None)
            await bot.send_message(partner, MSG_CHAT_ENDED)
        await call.answer("Пользователь забанен")
    await user_info_cb(call)

@dp.callback_query(F.data == "admin_banlist")
async def show_banlist(call: CallbackQuery):
    if not is_admin(call.from_user):
        return await call.answer("Нет доступа")
    if not banned_users:
        return await call.answer("Бан‑лист пуст")
    kb = []
    for uid in banned_users:
        display = get_user_display(uid)
        kb.append([InlineKeyboardButton(text=f"{display} (разбанить)", callback_data=f"toggleban_{uid}")])
    await call.message.edit_text("Забаненные пользователи:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer()

# ---------- ЗАПУСК ----------
async def main():
    # Устанавливаем список команд, видимых при вводе /
    commands = [
        BotCommand(command="start", description="Создать новый чат"),
        BotCommand(command="stop", description="Выйти из чата"),
        BotCommand(command="admin", description="Админ‑панель (только для администраторов)")
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
