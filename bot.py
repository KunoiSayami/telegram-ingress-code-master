#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# bot.py
# Copyright (C) 2020 KunoiSayami
#
# This module is part of telegram-ingress-code-poster and is released under
# the AGPL v3 License: https://www.gnu.org/licenses/agpl-3.0.txt
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
import asyncio
import logging
import re
from configparser import ConfigParser

import pyrogram
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from pyrogram.handlers import CallbackQueryHandler, MessageHandler

from libsqlite import PasscodeTracker

logger = logging.getLogger('code_poster')

PASSCODE = re.compile(r'^\w{5,20}$')


class Tracker:
    def __init__(self, api_id: int, api_hash: str, bot_token: str,  conn: PasscodeTracker, channel_id: int):
        self.app = Client('passcode', api_id=api_id, api_hash=api_hash, bot_token=bot_token)
        self.conn = conn
        self.channel_id = channel_id
        self.init_message_handler()

    def init_message_handler(self) -> None:
        self.app.add_handler(MessageHandler(self.handle_passcode, filters.text & filters.private))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback_query))

    async def start(self) -> None:
        await self.app.start()

    @staticmethod
    async def idle() -> None:
        await pyrogram.idle()

    async def stop(self) -> None:
        await self.app.stop()

    @classmethod
    async def new(cls, api_id: int, api_hash: str, bot_token: str, file_name: str, channel_id: int) -> 'Tracker':
        return cls(api_id, api_hash, bot_token, await PasscodeTracker.create(file_name, renew=True), channel_id)

    async def handle_passcode(self, client: Client, msg: Message) -> None:
        if len(msg.text) > 30:
            await msg.reply("Passcode length exceed")
            return
        if PASSCODE.match(msg.text) is None:
            await msg.reply("Passcode format error")
            return
        result = await self.conn.query(msg.text)
        if result is None:
            _msg = await client.send_message(self.channel_id, f'<code>{msg.text}</code>', 'html')
            await asyncio.gather(self.conn.insert(msg.text, _msg.message_id),
                                 self.conn.insert_history(msg.text, msg.chat.id))
            await msg.reply('Send successful')
        else:
            await msg.reply(f"Passcode exist, {'mark passcode' if not result.FR else 'undo mark'} as FR?",
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton(
                                    "Process", f"{'u' if result.FR else 'm'} {msg.text} {result.message_id}")]]))

    async def handle_callback_query(self, client: Client, msg: CallbackQuery) -> None:
        args = msg.data.split()
        if len(args) != 3:
            return
        _msg_text = f'<del>{args[1]}</del>' if args[0] == 'm' else f'<code>{args[1]}</code>'
        logger.debug("_msg_text => %s", _msg_text)
        await asyncio.gather(
            client.edit_message_text(self.channel_id, int(args[2]), _msg_text, 'html'),
            self.conn.update(args[1], args[0] == 'm'),
            msg.edit_message_reply_markup(),
            msg.answer(),
        )

    async def handle_auth(self) -> None:
        pass


async def main():
    config = ConfigParser()
    config.read('config.ini')
    bot = await Tracker.new(config.getint('telegram', 'api_id'), config.get('telegram', 'api_hash'),
                      config.get('telegram', 'bot_token'), 'codes.db', config.getint('telegram', 'channel'))
    await bot.start()
    await bot.idle()
    await bot.stop()


if __name__ == '__main__':
    try:
        import coloredlogs
        coloredlogs.install(logging.DEBUG,
                            fmt='%(asctime)s,%(msecs)03d - %(levelname)s - %(funcName)s - %(lineno)d - %(message)s')
    except ModuleNotFoundError:
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s - %(levelname)s - %(funcName)s - %(lineno)d - %(message)s')
    logging.getLogger('pyrogram').setLevel(logging.WARNING)
    logging.getLogger('aiosqlite').setLevel(logging.WARNING)
    asyncio.get_event_loop().run_until_complete(main())
