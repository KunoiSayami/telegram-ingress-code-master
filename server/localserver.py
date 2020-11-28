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
import concurrent.futures
import logging
import hashlib
import os
import signal
import ssl
import weakref
from configparser import ConfigParser
from queue import Queue
from typing import Dict, NoReturn, Optional, Union
from types import FrameType

import aiofiles
import aiohttp
from aiohttp import web

from libsqlite import CodeStorage

logger = logging.getLogger('Receiver')
logger.setLevel(logging.DEBUG)


class NeverFetched(Exception):
    """If user never fetched code, but want to delete, exception will raised"""


class WsCoroutine:
    def __init__(self, ws: web.WebSocketResponse, conn: CodeStorage, request_send: asyncio.Event):
        self.ws = ws
        self.conn = conn
        self.request_send = request_send
        self.stop_event = asyncio.Event()
        self._identify_id = ''
        self.last_code = None

    async def runnable(self) -> None:
        while True:
            if self.request_send.is_set():
                self.last_code = await self.conn.request_next_code(self.identify_id)
                if self.last_code is not None:
                    await self.ws.send_json(WebServer.build_response_json(200, 0, self.last_code))
                    self.request_send.clear()
            if self.stop_event.is_set():
                return
            await asyncio.sleep(0.5)

    def req(self) -> None:
        logger.debug('Request new code')
        self.request_send.set()

    def req_stop(self):
        logger.debug('Request stop')
        self.stop_event.set()

    @property
    def identify_id(self) -> str:
        return self._identify_id

    @identify_id.setter
    def identify_id(self, identify_id: str) -> None:
        self._identify_id = identify_id

    async def mark_last_code(self, is_fr: bool, is_other: bool) -> None:
        if self.last_code is None:
            await self.ws.send_json(WebServer.build_response_json(400, 3, 'Code not sent yet'))
        await self.conn.mark_code(self.last_code, is_fr, is_other)


class WebServer:
    def __init__(self, prefix: str, bind: str, port: int, conn: CodeStorage,
                 ssl_context: Optional[web.SSLContext] = None):
        self.queue = Queue()
        self.ws_prefix = prefix
        if not self.ws_prefix.startswith('/'):
            self.ws_prefix = f'/{self.ws_prefix}'
        self.website = web.Application()
        self.bind = bind
        self.port = port
        self.site = None
        self.conn = conn
        self._fetched = False
        self.runner = web.AppRunner(self.website)
        self.website['websockets'] = weakref.WeakSet()
        self._idled = False
        self.ssl_context = ssl_context
        self._request_stop = False

    @classmethod
    async def new(cls, prefix: str, bind: str, port: int, conn: CodeStorage,
                  ssl_context: Optional[web.SSLContext] = None):
        self = cls(prefix, bind, port, conn, ssl_context)
        return self

    @staticmethod
    def build_response_json(status: int, sub_status: int = 0, /, body: str = '') -> Dict[str, Union[str, int]]:
        return {'status': status, 'sub': sub_status, 'body': body}

    @staticmethod
    def get_hash(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    async def handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        request_next_event = asyncio.Event()
        ws = web.WebSocketResponse()
        logger.info('Accept websocket from %s', request.remote)

        await ws.prepare(request)
        request.app['websockets'].add(ws)
        wsc = WsCoroutine(ws, self.conn, request_next_event)
        future = asyncio.run_coroutine_threadsafe(wsc.runnable(), asyncio.get_event_loop())
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    if msg.data == 'close':
                        await ws.close()
                        break
                    elif msg.data.startswith('register'):
                        group = msg.data.split()
                        if len(group) != 2:
                            await ws.send_json(self.build_response_json(400, 2, 'Bad register request'))
                            continue
                        wsc.identify_id = self.get_hash(group[-1])
                        wsc.req()
                    elif msg.data == 'continue':
                        if not len(wsc.identify_id):
                            await ws.send_json(self.build_response_json(400, 1, 'register required'))
                            continue
                        wsc.req()
                    elif msg.data == 'FR':
                        await wsc.mark_last_code(True, False)
                    elif msg.data == 'mark_other':
                        await wsc.mark_last_code(False, True)
                    else:
                        await ws.send_json(self.build_response_json(403, body='Forbidden'))
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.exception('ws connection closed with exception', ws.exception())
                    break
        finally:
            wsc.req_stop()
            request.app['websockets'].discard(ws)
            try:
                future.exception(timeout=1)
            except concurrent.futures.TimeoutError:
                pass
            except:
                logger.exception('Got exception while process coroutine')
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
        self.website.router.add_get(self.ws_prefix, self.handle_websocket)
        self.website.on_shutdown.append(self.handle_web_shutdown)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.bind, self.port, ssl_context=self.ssl_context)
        await self.site.start()
        logger.info('Listen websocket on ws%s://%s:%d%s',
                    's' if self.ssl_context is not None else '',
                    self.bind, self.port, self.ws_prefix)

    async def stop_server(self) -> None:
        self._request_stop = True
        await self.site.stop()
        await self.runner.cleanup()

    async def put_code(self, code: str, *, from_storage: bool = False) -> str:
        if code in self.queue.queue:
            return code
        self.queue.put_nowait(code)
        if not from_storage:
            if not await self.conn.insert_code(code):
                return code
        logger.debug("Insert code => %s to database", code)
        return code

    async def idle(self):
        self._idled = True

        for sig in (signal.SIGINT, signal.SIGABRT, signal.SIGTERM):
            signal.signal(sig, self._reset_idle)

        while self._idled:
            await asyncio.sleep(1)

    def _reset_idle(self, signal_: signal.Signals, _frame_type: FrameType) -> None:
        if not self._idled:
            logger.debug('Got signal %s, killing...', signal_)
            os.kill(os.getpid(), signal.SIGKILL)
        else:
            logger.debug('Got signal %s, stopping...', signal_)
            self._idled = False

    @classmethod
    async def load_from_cfg(cls, config: ConfigParser, debug: bool = False) -> 'WebServer':
        ssl_context = None
        if config.getboolean('ssl', 'enabled', fallback=False):
            logger.info('SSL is enabled.')
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(
                config.get('ssl', 'pem', fallback='cert.pem'),
                config.get('ssl', 'key', fallback='cert.key')
            )
        return await cls.new(
            config.get('web', 'ws_prefix'),
            config.get('web', 'bind'),
            config.getint('web', 'port', fallback=29985),
            await CodeStorage.new('codeserver.db', renew=debug),
            ssl_context
        )


async def main(debug: bool, load_from_file: bool) -> None:
    config = ConfigParser()
    config.read('config.ini')
    website = await WebServer.load_from_cfg(config, debug)

    if load_from_file:
        logger.debug('Insert passcode to database')
        async with aiofiles.open('passcode.txt') as fin:
            for code in await fin.readlines():
                if len(code) == 0:
                    break
                await website.put_code(code.strip())

    await website.start_server()
    await website.idle()
    await website.stop_server()
