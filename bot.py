import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
    ChatMemberMember,
    ChatMemberAdministrator,
    ChatMemberOwner,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode

import config
import database as db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=config.BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
router = Router()
dp.include_router(router)


# ─── FSM States ───
class AdminStates(StatesGroup):
    waiting_sub_media = State()
    waiting_sub_text = State()
    waiting_welcome_media = State()
    waiting_welcome_text = State()


# ─── Helpers ───
async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(config.CHANNEL_ID, user_id)
        return isinstance(member, (ChatMemberMember, ChatMemberAdministrator, ChatMemberOwner))
    except Exception:
        return False


async def send_with_media(chat_id: int, media_type: str, media_id: str, text: str, markup=None):
    """Send a message with optional media."""
    if media_type == "photo" and media_id:
        await bot.send_photo(chat_id, media_id, caption=text, reply_markup=markup)
    elif media_type == "video" and media_id:
        await bot.send_video(chat_id, media_id, caption=text, reply_markup=markup)
    elif media_type == "animation" and media_id:
        await bot.send_animation(chat_id, media_id, caption=text, reply_markup=markup)
    else:
        await bot.send_message(chat_id, text, reply_markup=markup)


def sub_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Подписаться", url=config.CHANNEL_URL)],
        [InlineKeyboardButton(text="✅ Проверить", callback_data="check_sub")],
    ])


def webapp_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🎬 Открыть WatchTogether",
            web_app=WebAppInfo(url=config.WEBAPP_URL),
        )],
    ])


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖼 Медиа подписки", callback_data="admin_sub_media"),
         InlineKeyboardButton(text="📝 Текст подписки", callback_data="admin_sub_text")],
        [InlineKeyboardButton(text="🖼 Медиа приветствия", callback_data="admin_wel_media"),
         InlineKeyboardButton(text="📝 Текст приветствия", callback_data="admin_wel_text")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🗑 Сброс медиа подписки", callback_data="admin_reset_sub_media")],
        [InlineKeyboardButton(text="🗑 Сброс медиа приветствия", callback_data="admin_reset_wel_media")],
    ])


# ─── /start ───
@router.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user
    await db.upsert_user(user.id, user.username or "", user.first_name or "")

    if await is_subscribed(user.id):
        media_type = await db.get_setting("welcome_media_type")
        media_id = await db.get_setting("welcome_media_file_id")
        text = await db.get_setting("welcome_text")
        await send_with_media(message.chat.id, media_type, media_id, text, webapp_keyboard())
    else:
        media_type = await db.get_setting("sub_media_type")
        media_id = await db.get_setting("sub_media_file_id")
        text = await db.get_setting("sub_text")
        await send_with_media(message.chat.id, media_type, media_id, text, sub_keyboard())


# ─── Check subscription ───
@router.callback_query(F.data == "check_sub")
async def check_subscription(callback: CallbackQuery):
    if await is_subscribed(callback.from_user.id):
        await callback.message.delete()
        media_type = await db.get_setting("welcome_media_type")
        media_id = await db.get_setting("welcome_media_file_id")
        text = await db.get_setting("welcome_text")
        await send_with_media(callback.message.chat.id, media_type, media_id, text, webapp_keyboard())
    else:
        await callback.answer("❌ Вы не подписались на канал!", show_alert=True)


# ─── /admin ───
@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id not in config.ADMIN_IDS:
        return await message.answer("⛔ Нет доступа.")
    await message.answer("⚙️ <b>Админ-панель</b>", reply_markup=admin_keyboard())


# ─── Admin callbacks ───
@router.callback_query(F.data == "admin_sub_media")
async def admin_sub_media(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in config.ADMIN_IDS:
        return
    await callback.message.answer("📎 Отправьте фото, видео или GIF для сообщения подписки:")
    await state.set_state(AdminStates.waiting_sub_media)
    await callback.answer()


@router.callback_query(F.data == "admin_sub_text")
async def admin_sub_text(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in config.ADMIN_IDS:
        return
    await callback.message.answer("📝 Отправьте новый текст для сообщения подписки:")
    await state.set_state(AdminStates.waiting_sub_text)
    await callback.answer()


@router.callback_query(F.data == "admin_wel_media")
async def admin_wel_media(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in config.ADMIN_IDS:
        return
    await callback.message.answer("📎 Отправьте фото, видео или GIF для приветственного сообщения:")
    await state.set_state(AdminStates.waiting_welcome_media)
    await callback.answer()


@router.callback_query(F.data == "admin_wel_text")
async def admin_wel_text(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in config.ADMIN_IDS:
        return
    await callback.message.answer("📝 Отправьте новый текст для приветственного сообщения:")
    await state.set_state(AdminStates.waiting_welcome_text)
    await callback.answer()


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id not in config.ADMIN_IDS:
        return
    stats = await db.get_stats()
    text = (
        "📊 <b>Статистика бота</b>\n\n"
        f"👥 Пользователей: <b>{stats['users']}</b>\n"
        f"🎬 Комнат всего: <b>{stats['rooms_total']}</b>\n"
        f"🟢 Активных комнат: <b>{stats['rooms_active']}</b>\n"
        f"💬 Сообщений в чатах: <b>{stats['messages']}</b>"
    )
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "admin_reset_sub_media")
async def admin_reset_sub(callback: CallbackQuery):
    if callback.from_user.id not in config.ADMIN_IDS:
        return
    await db.set_setting("sub_media_type", "none")
    await db.set_setting("sub_media_file_id", "")
    await callback.answer("✅ Медиа подписки сброшено!", show_alert=True)


@router.callback_query(F.data == "admin_reset_wel_media")
async def admin_reset_wel(callback: CallbackQuery):
    if callback.from_user.id not in config.ADMIN_IDS:
        return
    await db.set_setting("welcome_media_type", "none")
    await db.set_setting("welcome_media_file_id", "")
    await callback.answer("✅ Медиа приветствия сброшено!", show_alert=True)


# ─── FSM: receive media / text ───
@router.message(AdminStates.waiting_sub_media, F.photo)
async def save_sub_photo(message: Message, state: FSMContext):
    await db.set_setting("sub_media_type", "photo")
    await db.set_setting("sub_media_file_id", message.photo[-1].file_id)
    await message.answer("✅ Фото для сообщения подписки сохранено!", reply_markup=admin_keyboard())
    await state.clear()


@router.message(AdminStates.waiting_sub_media, F.video)
async def save_sub_video(message: Message, state: FSMContext):
    await db.set_setting("sub_media_type", "video")
    await db.set_setting("sub_media_file_id", message.video.file_id)
    await message.answer("✅ Видео сохранено!", reply_markup=admin_keyboard())
    await state.clear()


@router.message(AdminStates.waiting_sub_media, F.animation)
async def save_sub_gif(message: Message, state: FSMContext):
    await db.set_setting("sub_media_type", "animation")
    await db.set_setting("sub_media_file_id", message.animation.file_id)
    await message.answer("✅ GIF сохранено!", reply_markup=admin_keyboard())
    await state.clear()


@router.message(AdminStates.waiting_sub_text)
async def save_sub_text(message: Message, state: FSMContext):
    await db.set_setting("sub_text", message.text or message.caption or "")
    await message.answer("✅ Текст подписки обновлён!", reply_markup=admin_keyboard())
    await state.clear()


@router.message(AdminStates.waiting_welcome_media, F.photo)
async def save_wel_photo(message: Message, state: FSMContext):
    await db.set_setting("welcome_media_type", "photo")
    await db.set_setting("welcome_media_file_id", message.photo[-1].file_id)
    await message.answer("✅ Фото приветствия сохранено!", reply_markup=admin_keyboard())
    await state.clear()


@router.message(AdminStates.waiting_welcome_media, F.video)
async def save_wel_video(message: Message, state: FSMContext):
    await db.set_setting("welcome_media_type", "video")
    await db.set_setting("welcome_media_file_id", message.video.file_id)
    await message.answer("✅ Видео сохранено!", reply_markup=admin_keyboard())
    await state.clear()


@router.message(AdminStates.waiting_welcome_media, F.animation)
async def save_wel_gif(message: Message, state: FSMContext):
    await db.set_setting("welcome_media_type", "animation")
    await db.set_setting("welcome_media_file_id", message.animation.file_id)
    await message.answer("✅ GIF сохранено!", reply_markup=admin_keyboard())
    await state.clear()


@router.message(AdminStates.waiting_welcome_text)
async def save_wel_text(message: Message, state: FSMContext):
    await db.set_setting("welcome_text", message.text or message.caption or "")
    await message.answer("✅ Текст приветствия обновлён!", reply_markup=admin_keyboard())
    await state.clear()