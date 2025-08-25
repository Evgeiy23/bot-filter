import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
import api
from collections import defaultdict
import time

api_token = api.API_TOKEN
admin_id = api.ADMIN_ID
channel_id = api.CHANNEL_ID

bot = Bot(token=api_token)
dp = Dispatcher()

blacklist = set()
already_requested = set()
processing = set()
last_join_time = defaultdict(lambda: 0)
spam_ban_until = defaultdict(lambda: 0)
SPAM_BAN = 24 * 60 * 60  # бан на сутки в секундах

user_names = {}  # храним user_id -> имя

@dp.message(Command("start"))
async def start(message: types.Message):
    user_names[message.from_user.id] = message.from_user.full_name
    await bot.send_video(chat_id=message.chat.id, video=FSInputFile("video.mp4"))
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="хочу в канал", callback_data="join_request")]
    ])
    await message.answer("салам! нажми кнопку ниже, чтобы попроситься в канал:", reply_markup=keyboard)

@dp.message(Command("help"))
async def help_command(message: types.Message):
    if message.from_user.id == admin_id:
        text = (
            "привет админ!\n"
            "команды:\n"
            "/show_blacklist - показать черный список\n"
            "на кнопках в сообщении с заявкой: одобрить / отклонить / в чс / разблокировать\n"
        )
    else:
        text = (
            "привет!\n"
            "нажми кнопку 'хочу в канал', чтобы попроситься в канал\n"
            "подожди, пока админ одобрит\n"
            "спамить кнопку не нужно, бот проигнорит лишние нажатия"
        )
    await message.answer(text)

@dp.callback_query(lambda c: c.data == "join_request")
async def join_request_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user_names[user_id] = callback_query.from_user.full_name
    now = time.time()

    # удаляем сообщение с кнопкой после нажатия
    await callback_query.message.delete()

    if user_id in blacklist:
        await callback_query.message.answer("ты в чс :(")
        await callback_query.answer()
        return

    if now < spam_ban_until[user_id]:
        await callback_query.message.answer("ты в бане за спам, подожди пока истечет сутки")
        await callback_query.answer()
        return

    time_since_last = now - last_join_time[user_id]
    if time_since_last < JOIN_COOLDOWN:
        spam_ban_until[user_id] = now + SPAM_BAN
        await callback_query.message.answer("ты слишком часто жмешь кнопку, бан на сутки")
        await bot.send_message(admin_id, f"пользователь {user_names[user_id]} спамит кнопку, получил бан на сутки")
        await callback_query.answer()
        return

    if user_id in already_requested or user_id in processing:
        await callback_query.answer()
        return

    processing.add(user_id)
    already_requested.add(user_id)
    last_join_time[user_id] = now

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{user_names[user_id]}", url=f"tg://user?id={user_id}")],
        [
            InlineKeyboardButton(text="одобрить", callback_data=f"approve:{user_id}"),
            InlineKeyboardButton(text="отклонить", callback_data=f"reject:{user_id}"),
            InlineKeyboardButton(text="в чс", callback_data=f"blacklist:{user_id}")
        ]
    ])
    try:
        await bot.send_message(admin_id, "хочет вступить:", reply_markup=keyboard)
        await callback_query.message.answer("брат, жди заявка у админа канала")
    finally:
        processing.remove(user_id)
    await callback_query.answer()

@dp.callback_query(lambda c: c.data.startswith(("approve", "reject", "blacklist", "unban")))
async def process_callback(callback_query: types.CallbackQuery):
    action, user_id = callback_query.data.split(":")
    user_id = int(user_id)
    user_name = user_names.get(user_id, str(user_id))

    if action == "approve":
        if user_id in blacklist:
            await bot.send_message(user_id, "ты в чс, нельзя добавить")
            await bot.send_message(admin_id, f"ты пытался одобрить {user_name}, но он в чс")
            await callback_query.answer("пользователь в чс")
            return
        try:
            invite_link = await bot.create_chat_invite_link(channel_id, member_limit=1)
            await bot.send_message(user_id, f"только для тебя:\n{invite_link.invite_link}")
            await bot.send_message(admin_id, f"ты одобрил {user_name} и сгенерировал ссылку")
            await callback_query.answer("ссылка отправлена")
        except Exception:
            await bot.send_message(user_id, "не могу создать ссылку, бот не в канале")
            await bot.send_message(admin_id, f"не удалось одобрить {user_name}, бот не в канале")
            await callback_query.answer("ошибка ссылки")
    elif action == "reject":
        await bot.send_message(user_id, "сорри((, ссылки не будет)")
        await bot.send_message(admin_id, f"ты отклонил {user_name}")
        await callback_query.answer("отклонено")
    elif action == "blacklist":
        blacklist.add(user_id)
        await bot.send_message(user_id, "ты в чс")
        await bot.send_message(admin_id, f"ты забанил {user_name}")
        await callback_query.answer("добавлен в чс")
    elif action == "unban":
        if user_id in blacklist:
            blacklist.remove(user_id)
            await bot.send_message(user_id, "тебя разблокировали")
            await bot.send_message(admin_id, f"ты разблокировал {user_name}")
        else:
            await bot.send_message(admin_id, f"{user_name} не был в чс")
        await callback_query.answer("разблокирован")

@dp.message(Command("show_blacklist"))
async def show_blacklist(message: types.Message):
    if message.from_user.id != admin_id:
        await message.answer("нет прав")
        return
    if not blacklist:
        await message.answer("чс пуст")
        return
    keyboard_buttons = [
        [InlineKeyboardButton(text=f"разблокировать {user_names.get(user_id, user_id)}", callback_data=f"unban:{user_id}")]
        for user_id in blacklist
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await message.answer("чс:", reply_markup=keyboard)

async def main():
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
