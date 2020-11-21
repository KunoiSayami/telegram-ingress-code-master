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

    if server_core_only:
        from server.localserver import main
    else:
        from server.receiver import main

    asyncio.get_event_loop().run_until_complete(main(debug_mode, _load_from_file))
