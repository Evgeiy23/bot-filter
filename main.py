import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from aiogram.filters import Command

import api

API_TOKEN = api.API_TOKEN
ADMIN_ID = api.ADMIN_ID  # твой Telegram ID
CHANNEL_ID = api.CHANNEL_ID  # ID канала

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

blacklist = set()  # ЧС в памяти

@dp.message(Command("start"))
async def start(message: Message):
    await bot.send_video(chat_id=message.chat.id, video=FSInputFile("video.mp4"))
    await message.answer("салам! хочешь в мой тгк? отправь команду /join")

@dp.message(Command("join"))
async def join_request(message: Message):
    if message.from_user.id in blacklist:
        await message.answer("ты в чс :(")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Одобрить", callback_data=f"approve:{message.from_user.id}"),
            InlineKeyboardButton(text="Отклонить", callback_data=f"reject:{message.from_user.id}"),
            InlineKeyboardButton(text="В ЧС", callback_data=f"blacklist:{message.from_user.id}")
        ]
    ])

    user_link = f"[{message.from_user.full_name}](tg://user?id={message.from_user.id})"
    await bot.send_message(
        ADMIN_ID,
        f"хочет вступить: {user_link}",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await message.answer("брат, жди заявка у админа канала")

@dp.callback_query(lambda c: c.data.startswith(("approve", "reject", "blacklist", "unban")))
async def process_callback(callback_query: CallbackQuery):
    action, user_id = callback_query.data.split(":")
    user_id = int(user_id)

    if action == "approve":
        try:
            member = await bot.get_chat_member(CHANNEL_ID, user_id)
            if member.status not in ["left", "kicked"]:
                await bot.send_message(user_id, "ты уже в канале, отстань")
                await callback_query.answer("Пользователь уже в канале.")
                return
        except:
            pass  # если бот не видит пользователя, продолжаем

        invite_link = await bot.create_chat_invite_link(CHANNEL_ID, member_limit=1)
        await bot.send_message(user_id, f"жду тебя в своем канале:\n{invite_link.invite_link}")

    elif action == "reject":
        await bot.send_message(user_id, "сорри((, но я тебе не дам ссылку))")

    elif action == "blacklist":
        blacklist.add(user_id)
        await bot.send_message(user_id, "ты в черном списке, поздравляю!")
        await bot.send_message(ADMIN_ID, f"пользователь [{user_id}](tg://user?id={user_id}) добавлен в ЧС.", parse_mode="Markdown")

    elif action == "unban":
        if user_id in blacklist:
            blacklist.remove(user_id)
            await bot.send_message(user_id, "тебя админ пожалел, ты не в чс")
            await bot.send_message(ADMIN_ID, f"пользователь [{user_id}](tg://user?id={user_id}) разблокирован.", parse_mode="Markdown")
        else:
            await bot.send_message(ADMIN_ID, f"пользователь [{user_id}](tg://user?id={user_id}) не был в ЧС.", parse_mode="Markdown")

    await callback_query.answer("действие выполнено.")

@dp.message(Command("show_blacklist"))
async def show_blacklist(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("иди в попу у тебя нет прав")
        return

    if not blacklist:
        await message.answer("чс пуст.")
        return

    keyboard_buttons = [
        [InlineKeyboardButton(text=f"разблокировать {user_id}", callback_data=f"unban:{user_id}")]
        for user_id in blacklist
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await message.answer("чс пользователей:", reply_markup=keyboard)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
