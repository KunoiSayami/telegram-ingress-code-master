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
import sys
from configparser import ConfigParser

import aiohttp
from aiohttp import web
import pyrogram
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler


class Receiver:
    def __init__(self, api_id: int, api_hash: str, bot_token: str, channel: str, prefix: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.bot_token = bot_token
        self.bot = Client('receiver', api_id=api_id, api_hash=api_hash, bot_token=bot_token)
        self.channel = channel
        self.queue = asyncio.Queue()
        self.website_prefix = prefix
        self.website = web.Application()

    def init_handle(self) -> None:
        self.bot.add_handler(MessageHandler(self.handle_incoming_passcode, filters.chat(self.channel) & filters.text))

    async def handle_incoming_passcode(self, _client: Client, msg: Message) -> None:
        self.queue.put_nowait(msg.text)

    async def handle_web_request(self) -> None:
        pass

    def create_server(self) -> None:
        self.website.router.add_get(self.website_prefix, self.handle_web_request)
        web.run_app(self.website)

    @classmethod
    async def new(cls, api_id: int, api_hash: str, bot_token: str, channel: str, prefix: str) -> 'Receiver':
        return cls(api_id, api_hash, bot_token, channel, prefix)

    async def start(self) -> None:
        await self.bot.start()

    async def stop(self) -> None:
        await self.bot.stop()


async def main(debug: bool = False) -> None:
    config = ConfigParser()
    config.read('config.ini')
    bot = await Receiver.new(config.getint('telegram', 'api_id'), config.get('telegram', 'api_hash'),
                             config.get('server', 'bot_token'), config.getint('server', 'listen_to'),
                             config.get('server', 'default_prefix'))
    await bot.start()
    bot.create_server()
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
    asyncio.get_event_loop().run_until_complete(main(len(sys.argv) > 1 and sys.argv[1] == 'debug'))

