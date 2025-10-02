import asyncio
import datetime
import html
from typing import Optional

from aiogram import Dispatcher
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.exceptions import (BotBlocked, ChatNotFound, RetryAfter,
                                      TelegramAPIError, UserDeactivated)

from bot.database.methods import (check_user, get_all_users,
                                  update_last_reminder_sent)
from bot.logger_mesh import logger

REMINDER_INTERVAL_HOURS = 72
CHECK_INTERVAL_SECONDS = 3600


def _parse_timestamp(value: Optional[str]) -> Optional[datetime.datetime]:
    if not value:
        return None
    try:
        return datetime.datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None


def _inactivity_keyboard() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton('🚀 Start', callback_data='back_to_menu'))
    return markup


def _format_mention(user_id: int, username: Optional[str], full_name: Optional[str]) -> str:
    if username:
        return f"@{username}"
    safe_name = html.escape(full_name) if full_name else str(user_id)
    return f"<a href='tg://user?id={user_id}'>{safe_name}</a>"


def _build_reminder_text(mention: str) -> str:
    return (
        f"👋 Hey {mention}! We haven't seen you in a while—want to check us out again? 😎\n"
        f"🇱🇹 Labas {mention}! Seniai tavęs nematėme, gal nori vėl pas mus užsukti? 😊\n"
        f"🇷🇺 Привет {mention}! Мы давно тебя не видели, хочешь заглянуть к нам? 🔥"
    )


async def _send_reminder(dp: Dispatcher, user_id: int, text: str, timestamp: str) -> None:
    try:
        await dp.bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode='HTML',
            reply_markup=_inactivity_keyboard(),
        )
        update_last_reminder_sent(user_id, timestamp)
        await asyncio.sleep(0.1)
    except RetryAfter as exc:
        await asyncio.sleep(exc.timeout)
        try:
            await dp.bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode='HTML',
                reply_markup=_inactivity_keyboard(),
            )
            update_last_reminder_sent(user_id, timestamp)
        except (BotBlocked, ChatNotFound, UserDeactivated, TelegramAPIError):
            update_last_reminder_sent(user_id, timestamp)
    except (BotBlocked, ChatNotFound, UserDeactivated):
        update_last_reminder_sent(user_id, timestamp)
    except TelegramAPIError as exc:
        logger.warning("Failed to send inactivity reminder to %s: %s", user_id, exc)


async def _reminder_loop(dp: Dispatcher,
                         check_interval: int = CHECK_INTERVAL_SECONDS,
                         inactivity_hours: int = REMINDER_INTERVAL_HOURS) -> None:
    while True:
        now = datetime.datetime.utcnow()
        cutoff = now - datetime.timedelta(hours=inactivity_hours)
        cutoff_dt = cutoff
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
        try:
            for row in get_all_users():
                user_id = int(row[0])
                user = check_user(user_id)
                if not user:
                    continue
                last_activity = _parse_timestamp(getattr(user, 'last_activity', None))
                if not last_activity:
                    last_activity = _parse_timestamp(getattr(user, 'registration_date', None))
                if not last_activity or last_activity > cutoff_dt:
                    continue
                last_reminder = _parse_timestamp(getattr(user, 'last_reminder_sent', None))
                if last_reminder and last_reminder >= last_activity and last_reminder >= cutoff_dt:
                    continue
                try:
                    chat = await dp.bot.get_chat(user_id)
                except (BotBlocked, ChatNotFound, UserDeactivated):
                    update_last_reminder_sent(user_id, timestamp)
                    continue
                mention = _format_mention(user_id, chat.username, chat.full_name)
                text = _build_reminder_text(mention)
                await _send_reminder(dp, user_id, text, timestamp)
        except Exception as exc:  # pragma: no cover - safety net
            logger.exception("Inactive user reminder loop error: %s", exc)
        await asyncio.sleep(check_interval)


def start_inactivity_reminder(dp: Dispatcher) -> None:
    asyncio.create_task(_reminder_loop(dp))
