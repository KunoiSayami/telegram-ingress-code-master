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
import logging
import sys
from configparser import ConfigParser

import aiofiles
from server.localserver import WebServer
from server.receiver import Receiver


async def main(debug: bool, load_from_file: bool, start_website_only: bool) -> None:
    config = ConfigParser()
    config.read('config.ini')
    website = await WebServer.load_from_cfg(config, debug)
    instance = website

    if load_from_file:
        async with aiofiles.open('passcode.txt') as fin:
            for code in await fin.readlines():
                if len(code) == 0:
                    break
                await website.put_code(code.strip())

    if not start_website_only:
        instance = await Receiver.new(
            config.getint('telegram', 'api_id'),
            config.get('telegram', 'api_hash'),
            config.get('server', 'bot_token'),
            config.getint('server', 'listen_user'),
            website
        )

    await instance.start()
    await instance.idle()
    await instance.stop()


if __name__ == '__main__':
    try:
        import coloredlogs
        coloredlogs.install(logging.DEBUG,
                            fmt='%(asctime)s,%(msecs)03d - %(levelname)s - %(funcName)s - %(lineno)d - %(message)s')
    except ModuleNotFoundError:
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s - %(levelname)s - %(funcName)s - %(lineno)d - %(message)s')

    logging.getLogger('aiosqlite').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('pyrogram').setLevel(logging.WARNING)

    debug_mode = '--debug' in sys.argv
    _load_from_file = '--load' in sys.argv
    server_core_only = '--nbot' in sys.argv

    asyncio.get_event_loop().run_until_complete(main(debug_mode, _load_from_file, server_core_only))
