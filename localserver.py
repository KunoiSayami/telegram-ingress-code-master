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
import json
import logging
import sys
from configparser import ConfigParser
from queue import Queue
from typing import NoReturn

import aiohttp
import aiohttp_cors
import pyrogram
from aiohttp import web
from deprecated import deprecated
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler

from libsqlite import CodeStorage

logger = logging.getLogger('Receiver')
logger.setLevel(logging.DEBUG)


class NeverFetched(Exception):
    """If user never fetched code, but want to delete, exception will raised"""


class Receiver:
    def __init__(self, api_id: int, api_hash: str, bot_token: str, channel: str, prefix: str, bind: str, port: int,
                 conn: CodeStorage):
        self.api_id = api_id
        self.api_hash = api_hash
        self.bot_token = bot_token
        self.bot = Client('receiver', api_id=api_id, api_hash=api_hash, bot_token=bot_token)
        self.channel = channel
        self.queue = Queue()
        self.website_prefix = prefix
        if not self.website_prefix.startswith('/'):
            self.website_prefix = f'/{self.website_prefix}'
        self.website = web.Application()
        self.bind = bind
        self.port = port
        self.site = None
        self.conn = conn
        self._fetched = False
        self.cors = aiohttp_cors.setup(self.website, defaults={
            "*": aiohttp_cors.ResourceOptions(
                    allow_credentials=True,
                    expose_headers="*",
                    allow_headers="*",
            )})
        self.runner = web.AppRunner(self.website)

    def init_handle(self) -> None:
        self.bot.add_handler(MessageHandler(self.handle_incoming_passcode, filters.chat(self.channel) & filters.text))

    async def handle_incoming_passcode(self, _client: Client, msg: Message) -> None:
        # logger.info('Put passcode => %s', msg.text)
        await self._put_code(msg.text)

    @staticmethod
    def build_response_json(status: int, body: str = '') -> str:
        return json.dumps({'status': status, 'body': body}, indent=' ' * 4, separators=(': ', ','))

    async def handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        print(request.remote)
        await ws.prepare(request)
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                if msg.data == 'close':
                    await ws.close()
                elif msg.data == 'fetch':
                    if self.queue.empty():
                        await ws.send_str(self.build_response_json(204))
                        continue
                    await ws.send_str(self.build_response_json(200, self.queue.queue[0]))
                    self._fetched = True
                elif msg.data == 'delete':
                    if self.queue.empty():
                        await ws.send_str(self.build_response_json(400, 'Queue is empty!'))
                        continue
                    if not self._fetched:
                        await ws.send_str(self.build_response_json(400, 'Should fetch passcode first'))
                    await asyncio.gather(self._pop_code(), ws.send_str(self.build_response_json(200)))
                else:
                    await ws.send_str(self.build_response_json(403, 'Forbidden'))
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.exception('ws connection closed with exception', ws.exception())
        logger.info('websocket connection closed')
        return ws

    @deprecated(version='2.0.0', reason='Please use websocket to connect this server')
    async def handle_get_request(self, _request: web.Request) -> web.StreamResponse:
        if self.queue.empty():
            return web.Response(status=204, content_type='text/html')
        text = self.queue.queue[0]
        self._fetched = True
        # logger.debug('Get passcode => %s', text)
        return web.Response(text=text)

    @deprecated(version='2.0.0', reason='Please use websocket to connect this server')
    async def handle_delete_request(self, _request: web.Request) -> web.StreamResponse:
        if self.queue.empty():
            return web.Response(status=400, text='Queue is empty!')
        if not self._fetched:
            return web.Response(status=400, text='Should fetch passcode first')
        await self._pop_code()
        return web.Response(content_type='text/plain')

    async def start_server(self) -> None:
        async def inner_handle(_request: web.Request) -> NoReturn:
            raise web.HTTPForbidden
        resource = self.cors.add(self.website.router.add_resource(self.website_prefix))
        self.website.router.add_get('/', inner_handle)
        self.website.router.add_get('/ws', self.handle_websocket)
        self.cors.add(resource.add_route('GET', self.handle_get_request))
        self.cors.add(resource.add_route('DELETE', self.handle_delete_request))
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.bind, self.port)
        await self.site.start()
        logger.info('Start server on %s:%d', self.bind, self.port)

    async def stop_server(self) -> None:
        await self.site.stop()
        await self.runner.cleanup()

    @classmethod
    async def new(cls, api_id: int, api_hash: str, bot_token: str, channel: str, prefix: str,
                  bind: str, port: int, conn: CodeStorage) -> 'Receiver':
        self = cls(api_id, api_hash, bot_token, channel, prefix, bind, port, conn)
        async for code in self.conn.iter_code():
            await self._put_code(code)
        return self

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

    async def _put_code(self, code: str) -> str:
        if code in self.queue.queue:
            return code
        self.queue.put_nowait(code)
        await self.conn.insert_code(code)
        logger.info("insert code => %s to queue", code)
        return code

    async def _pop_code(self) -> str:
        if not self._fetched:
            raise NeverFetched
        self._fetched = False
        code = self.queue.get_nowait()
        await self.conn.delete_code(code)
        logger.info("delete code => %s from queue", code)
        return code


async def main(debug: bool = False) -> None:
    config = ConfigParser()
    config.read('config.ini')
    bot = await Receiver.new(config.getint('telegram', 'api_id'), config.get('telegram', 'api_hash'),
                             config.get('server', 'bot_token'), config.getint('server', 'listen_user'),
                             config.get('web', 'default_prefix'), config.get('web', 'bind'),
                             config.getint('web', 'port', fallback=29985),
                             await CodeStorage.new('codeserver.db', renew=debug))
    if debug:
        import aiofiles
        async with aiofiles.open("passcode.txt") as fin:
            for code in (await fin.read()).splitlines():
                await bot._put_code(code)
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
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    asyncio.get_event_loop().run_until_complete(main(len(sys.argv) > 1 and sys.argv[1] == '--debug'))

