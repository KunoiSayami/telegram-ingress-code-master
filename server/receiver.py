#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# receiver.py
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

import pyrogram
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler

from server.localserver import WebServer


class Receiver:
    def __init__(self, api_id: int, api_hash: str, bot_token: str, listen_user: str, website: WebServer):
        self.api_id = api_id
        self.api_hash = api_hash
        self.bot_token = bot_token
        self.bot = Client('receiver', api_id=api_id, api_hash=api_hash, bot_token=bot_token)
        self.listen_user = listen_user
        self.website = website

    def init_handle(self) -> None:
        self.bot.add_handler(
            MessageHandler(self.handle_incoming_passcode, filters.chat(self.listen_user) & filters.text))

    async def handle_incoming_passcode(self, _client: Client, msg: Message) -> None:
        # logger.info('Put passcode => %s', msg.text)
        if '\n' in msg.text:
            for code in msg.text.splitlines():
                await self.website.put_code(code.strip())
        else:
            await self.website.put_code(msg.text)

    @classmethod
    async def new(cls, api_id: int, api_hash: str, bot_token: str, listen_user: str, website: WebServer) -> 'Receiver':
        return cls(api_id, api_hash, bot_token, listen_user, website)

    async def start_bot(self) -> None:
        await self.bot.start()

    async def stop_bot(self) -> None:
        await self.bot.stop()

    async def start(self) -> None:
        await asyncio.gather(self.start_bot(), self.website.start())

    async def stop(self) -> None:
        await asyncio.gather(self.stop_bot(), self.website.stop())

    @staticmethod
    async def idle() -> None:
        await pyrogram.idle()



