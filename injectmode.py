#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# injectmode.py
# Copyright (C) 2020-2021 KunoiSayami
#
# This module is part of telegram-ingress-code-master and is released under
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
from configparser import ConfigParser
from typing import Callable, Coroutine
import os

import aioredis

from forwarder.bot import Tracker, PasscodeTracker
from localserver import WebServer as Server


class RewriteTracker(Tracker):
    def __init__(self, api_id: int, api_hash: str, bot_token: str, conn: PasscodeTracker, channel_id: int,
                 password: str, owners: str, redis: aioredis.Redis):
        super().__init__(api_id, api_hash, bot_token, conn, channel_id, password, owners, redis)
        self.hook_send_passcode_func = None
        self.hook_mark_passcode_func = None

    async def hook_send_passcode(self, passcode: str) -> None:
        if self.hook_send_passcode_func is not None:
            await self.hook_send_passcode_func(passcode)

    async def hook_mark_full_redeemed_passcode(self, passcode: str, is_fr: bool = False) -> None:
        if self.hook_mark_passcode_func is not None:
            await self.hook_mark_passcode_func(passcode, is_fr)

    async def register_hook_functions(self, hook_send_passcode_func: Callable[[str], Coroutine[None]],
                                      hook_mark_passcode_func: Callable[[str, bool], Coroutine[None]]):
        self.hook_send_passcode_func = hook_send_passcode_func
        self.hook_mark_passcode_func = hook_mark_passcode_func


class WebServer:
    def __init__(self, tracker: RewriteTracker, web_server: Server):
        self.tracker = tracker
        self.web_server = web_server
        self.tracker.register_hook_functions(self.put_passcode, self.mark_passcode)

    @classmethod
    async def new(cls, debug: bool = False) -> 'WebServer':
        config_tracker, config_web_server = ConfigParser(), ConfigParser()
        config_web_server.read('config.ini')
        config_tracker.read(os.path.join('forwarder', 'config.ini'))
        return cls(await RewriteTracker.load_from_config(config_tracker, debug),
                   await Server.load_from_cfg(config_web_server, debug))

    async def start(self) -> None:
        await self.web_server.start()
        await self.tracker.start()

    async def stop(self) -> None:
        await self.tracker.stop()
        await self.web_server.stop()

    async def idle(self) -> None:
        await self.web_server.idle()

    async def put_passcode(self, passcode: str) -> None:
        await self.web_server.put_code(passcode)

    async def mark_passcode(self, passcode: str, is_fr: bool) -> None:
        await self.web_server.mark_code(passcode, is_fr)
