#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# localserver.py
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
from typing import NoReturn

import pyrogram
from aiohttp import web
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler

logger = logging.getLogger('Receiver')
logger.setLevel(logging.DEBUG)


class Receiver:
    def __init__(self, api_id: int, api_hash: str, bot_token: str, channel: str, prefix: str, bind: str, port: int):
        self.api_id = api_id
        self.api_hash = api_hash
        self.bot_token = bot_token
        self.bot = Client('receiver', api_id=api_id, api_hash=api_hash, bot_token=bot_token)
        self.channel = channel
        self.queue = asyncio.Queue()
        self.website_prefix = prefix
        if not self.website_prefix.startswith('/'):
            self.website_prefix = f'/{self.website_prefix}'
        self.website = web.Application()
        self.runner = web.AppRunner(self.website)
        self.bind = bind
        self.port = port
        self.site = None

    def init_handle(self) -> None:
        self.bot.add_handler(MessageHandler(self.handle_incoming_passcode, filters.chat(self.channel) & filters.text))

    async def handle_incoming_passcode(self, _client: Client, msg: Message) -> None:
        logger.info('Put passcode => %s', msg.text)
        self.queue.put_nowait(msg.text)

    async def handle_web_request(self, _request: web.Request) -> web.StreamResponse:
        if self.queue.empty():
            return web.Response(status=204, content_type='text/html')
        text = self.queue.get_nowait()
        logger.debug('Get passcode => %s', text)
        return web.Response(text=text)

    async def start_server(self) -> None:
        async def wrapper(_request: web.Request) -> NoReturn:
            raise web.HTTPForbidden
        self.website.router.add_get(self.website_prefix, self.handle_web_request)
        self.website.router.add_get('/', wrapper)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.bind, self.port)
        await self.site.start()
        logger.info('Start server on %s:%d', self.bind, self.port)

    async def stop_server(self) -> None:
        await self.site.stop()
        await self.runner.cleanup()

    @classmethod
    async def new(cls, api_id: int, api_hash: str, bot_token: str, channel: str, prefix: str,
                  bind: str, port: int) -> 'Receiver':
        return cls(api_id, api_hash, bot_token, channel, prefix, bind, port)

    async def start_bot(self) -> None:
        await self.bot.start()

    async def stop_bot(self) -> None:
        await self.bot.stop()

    async def start(self) -> None:
        await asyncio.gather(self.start_bot(), self.start_server())

    async def stop(self) -> None:
        await asyncio.gather(self.stop_bot(), self.stop_server())

    @staticmethod
    async def idle() -> None:
        await pyrogram.idle()


async def main(debug: bool = False) -> None:
    config = ConfigParser()
    config.read('config.ini')
    bot = await Receiver.new(config.getint('telegram', 'api_id'), config.get('telegram', 'api_hash'),
                             config.get('server', 'bot_token'), config.getint('server', 'listen_user'),
                             config.get('web', 'default_prefix'), config.get('web', 'bind'),
                             config.getint('web', 'port', fallback=29985))

    await bot.start()
    if debug:
        for x in range(20):
            bot.queue.put_nowait(f'test{x}')
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
    asyncio.get_event_loop().run_until_complete(main(len(sys.argv) > 1 and sys.argv[1] == '--debug'))

