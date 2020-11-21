#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# server.py
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
import signal
import sys
import weakref
from configparser import ConfigParser
from queue import Queue
from typing import NoReturn
from types import FrameType

import aiofiles
import aiohttp
from aiohttp import web

from libsqlite import CodeStorage

logger = logging.getLogger('Receiver')
logger.setLevel(logging.DEBUG)


class NeverFetched(Exception):
    """If user never fetched code, but want to delete, exception will raised"""


class WebServer:
    def __init__(self, prefix: str, bind: str, port: int, conn: CodeStorage):
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
        self.runner = web.AppRunner(self.website)
        self.website['websockets'] = weakref.WeakSet()
        self._idled = False

    @classmethod
    async def new(cls, prefix: str, bind: str, port: int, conn: CodeStorage):
        self = cls(prefix, bind, port, conn)
        async for code in self.conn.iter_code():
            await self.put_code(code, from_storage=True)
        return self

    @staticmethod
    def build_response_json(status: int, body: str = '') -> str:
        return json.dumps({'status': status, 'body': body}, indent=' ' * 4, separators=(',', ': '))

    async def handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        logger.info('Accept websocket from %s', request.remote)
        await ws.prepare(request)
        request.app['websockets'].add(ws)
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    if msg.data == 'close':
                        await ws.close()
                    elif msg.data == 'ping':
                        await ws.send_str(self.build_response_json(101))
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
                            continue
                        await asyncio.gather(self.pop_code(), ws.send_str(self.build_response_json(200)))
                    else:
                        await ws.send_str(self.build_response_json(403, 'Forbidden'))
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.exception('ws connection closed with exception', ws.exception())
        finally:
            request.app['websockets'].discard(ws)
        logger.info('websocket connection closed')
        return ws

    @staticmethod
    async def handle_web_shutdown(app: web.Application) -> None:
        for ws in set(app['websockets']):
            await ws.close(code=aiohttp.WSCloseCode.GOING_AWAY, message='Server shutdown')

    async def start_server(self) -> None:
        async def inner_handle(_request: web.Request) -> NoReturn:
            raise web.HTTPForbidden
        self.website.router.add_get('/', inner_handle)
        self.website.router.add_get(self.website_prefix, self.handle_websocket)
        self.website.on_shutdown.append(self.handle_web_shutdown)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.bind, self.port)
        await self.site.start()
        logger.info('Start server on %s:%d', self.bind, self.port)

    async def stop_server(self) -> None:
        await self.site.stop()
        await self.runner.cleanup()

    async def put_code(self, code: str, *, from_storage: bool = False) -> str:
        if code in self.queue.queue:
            return code
        self.queue.put_nowait(code)
        if not from_storage:
            await self.conn.insert_code(code)
        logger.debug("insert code => %s to queue", code)
        return code

    async def pop_code(self) -> str:
        if not self._fetched:
            raise NeverFetched
        self._fetched = False
        code = self.queue.get_nowait()
        await self.conn.delete_code(code)
        logger.debug("delete code => %s from queue", code)
        return code

    async def idle(self):
        self._idled = True

        for sig in (signal.SIGINT, signal.SIGABRT, signal.SIGTERM):
            signal.signal(sig, self._reset_idle)

        while self._idled:
            await asyncio.sleep(1)

    def _reset_idle(self, signal_: signal.Signals, _frame_type: FrameType) -> None:
        logger.debug('Got signal %s, stopping...', signal_)
        self._idled = False

    @classmethod
    async def load_from_cfg(cls, config: ConfigParser, debug: bool = False) -> 'WebServer':
        return await cls.new(
            config.get('web', 'default_prefix'),
            config.get('web', 'bind'),
            config.getint('web', 'port', fallback=29985),
            await CodeStorage.new('codeserver.db', renew=debug)
        )


async def main(debug: bool, load_from_file: bool) -> None:
    config = ConfigParser()
    config.read('config.ini')
    website = await WebServer.load_from_cfg(config, debug)

    if debug or load_from_file:
        async with aiofiles.open('passcode.txt') as fin:
            for code in await fin.readlines():
                if len(code) == 0:
                    break
                await website.put_code(code.strip())

    await website.start_server()
    await website.idle()
    await website.stop_server()
