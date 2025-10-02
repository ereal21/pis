import asyncio
from aiogram import Dispatcher
from aiogram.types import Message, CallbackQuery
from aiogram.utils.exceptions import (BotBlocked, ChatNotFound, RetryAfter,
                                      TelegramAPIError, UserDeactivated)

from bot.keyboards import back, close
from bot.database.methods import check_role, get_all_users
from bot.database.models import Permission
from bot.misc import TgConfig
from bot.logger_mesh import logger
from bot.handlers.other import get_bot_user_ids


async def send_message_callback_handler(call: CallbackQuery):
    bot, user_id = await get_bot_user_ids(call)
    TgConfig.STATE[user_id] = 'waiting_for_message'
    TgConfig.STATE[f'{user_id}_message_id'] = call.message.message_id
    role = check_role(user_id)
    if role & Permission.BROADCAST:
        await bot.edit_message_text(chat_id=call.message.chat.id,
                                    message_id=call.message.message_id,
                                    text='Send the message for broadcast:',
                                    reply_markup=back("console"))
        return
    await call.answer('Insufficient rights')


async def broadcast_messages(message: Message):
    bot, user_id = await get_bot_user_ids(message)
    user_info = await bot.get_chat(user_id)
    msg = message.html_text or message.text or message.caption or message.html_caption
    message_id = TgConfig.STATE.get(f'{user_id}_message_id')
    TgConfig.STATE[user_id] = None
    TgConfig.STATE.pop(f'{user_id}_message_id', None)

    if not msg:
        await bot.send_message(
            chat_id=message.chat.id,
            text='Only text announcements are supported.',
            reply_markup=back("console")
        )
        return

    try:
        await bot.delete_message(chat_id=message.chat.id,
                                 message_id=message.message_id)
    except TelegramAPIError:
        pass
    users = get_all_users()
    sent_count = 0
    total_users = len(users)
    for user_row in users:
        target_id = int(user_row[0])
        await asyncio.sleep(0.05)
        try:
            await bot.send_message(chat_id=target_id,
                                   text=msg,
                                   reply_markup=close(),
                                   parse_mode='HTML')
            sent_count += 1
        except RetryAfter as exc:
            await asyncio.sleep(exc.timeout)
            try:
                await bot.send_message(chat_id=target_id,
                                       text=msg,
                                       reply_markup=close(),
                                       parse_mode='HTML')
                sent_count += 1
            except (BotBlocked, ChatNotFound, UserDeactivated, TelegramAPIError):
                continue
        except (BotBlocked, ChatNotFound, UserDeactivated):
            continue
        except TelegramAPIError as exc:
            logger.warning("Failed to deliver broadcast to %s: %s", target_id, exc)
            continue
    if message_id:
        await bot.edit_message_text(chat_id=message.chat.id,
                                    message_id=message_id,
                                    text=f'Broadcast finished. Delivered to {sent_count}/{total_users} users.',
                                    reply_markup=back("console"))
    else:
        await bot.send_message(chat_id=message.chat.id,
                               text=f'Broadcast finished. Delivered to {sent_count}/{total_users} users.',
                               reply_markup=back("console"))
    logger.info(f"User {user_info.id} ({user_info.first_name})"
                f" performed a broadcast. Message was sent to {sent_count}/{total_users} users.")


def register_mailing(dp: Dispatcher) -> None:
    dp.register_callback_query_handler(send_message_callback_handler,
                                       lambda c: c.data == 'send_message')

    dp.register_message_handler(broadcast_messages,
                                lambda c: TgConfig.STATE.get(c.from_user.id) == 'waiting_for_message')
