# -*- coding: utf-8 -*-
# libsqlite.py
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
import logging
import os
from dataclasses import dataclass
from typing import Optional, Tuple

import asyncio
import aiosqlite

logger = logging.getLogger("code_poster").getChild("sqlite")
logger.setLevel(logging.getLogger("code_poster").level)

_DROP_STATEMENT = '''
    DROP TABLE IF EXISTS "code";
    DROP TABLE IF EXISTS "users";
'''

_CREATE_STATEMENT = '''
    CREATE TABLE "code" (
        "str"	        TEXT NOT NULL,
        "message_id"	INTEGER NOT NULL,
        "fr"	        INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY("str")
    );
    
    CREATE TABLE "users" (
        "id"            INTEGER NOT NULL,
        "authorized"    INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY("id")
    );
    
    CREATE TABLE "history" (
        "str"   TEXT NOT NULL,
        "send_by" INTEGER NOT NULL
    );
'''


@dataclass(init=False)
class CodeStatus:
    message_id: int
    FR: bool

    def __init__(self, message_id: int, fr: int):
        self.message_id = message_id
        self.FR = bool(fr)


class PasscodeTracker:
    def __init__(self, file_name: str):
        self.file_name = file_name
        self.lock = asyncio.Lock()

    @classmethod
    async def create(cls, file_name: str, *, renew: bool = False) -> 'PasscodeTracker':
        if renew:
            os.remove(file_name)
        async with aiosqlite.connect(file_name) as db:
            async with db.execute('''SELECT name FROM sqlite_master WHERE type='table' AND name='code' ''') as cursor:
                if (await cursor.fetchone()) is not None:
                    logger.debug('Found database, load it')
                    return cls(file_name)
            logger.debug('Create new database structure')
            async with db.executescript(_DROP_STATEMENT):
                pass
            async with db.executescript(_CREATE_STATEMENT):
                pass
        return cls(file_name)

    async def query(self, code: str) -> Optional[CodeStatus]:
        async with self.lock, aiosqlite.connect(self.file_name) as db:
            async with db.execute('''SELECT * FROM "code" WHERE "str" = ?''', (code,)) as cursor:
                r = await cursor.fetchone()
                if r is None:
                    return None
                return CodeStatus(r[1], r[2])

    async def update(self, code: str, fr: bool) -> None:
        async with self.lock, aiosqlite.connect(self.file_name) as db:
            async with db.execute('''UPDATE "code" SET "fr" = ? WHERE "str" = ?''', (int(fr), code)):
                pass
            await db.commit()

    async def insert(self, code: str, message_id: int) -> None:
        async with self.lock, aiosqlite.connect(self.file_name) as db:
            async with db.execute('''INSERT INTO "code" VALUES (?, ?, 0)''', (code, message_id)):
                pass
            await db.commit()

    async def insert_history(self, s: str, sender: int) -> None:
        async with self.lock, aiosqlite.connect(self.file_name) as db:
            async with db.execute('''INSERT INTO "history" VALUES (?, ?)''', (s, sender)):
                pass
            await db.commit()

    async def query_history(self, s: str) -> Optional[Tuple[str, int]]:
        async with self.lock, aiosqlite.connect(self.file_name) as db:
            async with db.execute('''SELECT * FROM "history" WHERE "str" LIKE %s''', (s,)) as cursor:
                r = await cursor.fetchone()
                if r is None:
                    return None
                return r
