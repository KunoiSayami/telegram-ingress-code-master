# -*- coding: utf-8 -*-
# libsqlite.py
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
import logging
from typing import Optional

import aiosqlite

from forwarder.libsqlite import SqliteBase

logger = logging.getLogger("code_master").getChild("sqlite")
logger.setLevel(logging.getLogger("code_master").level)

_CREATE_STATEMENT_CodeStorage = '''
    CREATE TABLE "storage" (
        "code"	TEXT NOT NULL UNIQUE,
        "id"	INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
        "FR"    INTEGER NOT NULL DEFAULT 0,
        "other" INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE "user_status" (
        "user_id"	TEXT NOT NULL,
        "index"	INTEGER,
        PRIMARY KEY("user_id")
    );
'''

_DROP_STATEMENT_CodeStorage = '''
    DROP TABLE IF EXISTS "storage";
    DROP TABLE IF EXISTS "sqlite_sequence";
    DROP TABLE IF EXISTS "user_status";
'''


class CodeStorage(SqliteBase):
    @classmethod
    async def new(cls, file_name: str, *, renew: bool = False) -> 'CodeStorage':
        return await cls._new(file_name, _DROP_STATEMENT_CodeStorage, _CREATE_STATEMENT_CodeStorage,
                              main_table_name='storage', renew=renew)

    async def insert_code(self, code: str) -> bool:
        async with self.lock, aiosqlite.connect(self.file_name) as db:
            async with db.execute('''SELECT * FROM "storage" WHERE "code" = ? ''', (code.lower(),)) as cursor:
                if await cursor.fetchone() is not None:
                    return False
            async with db.execute('''INSERT INTO "storage" ("code") VALUES (?)''', (code.lower(),)):
                pass
            await db.commit()
            return True

    async def delete_code(self, code: str) -> None:
        async with self.lock, aiosqlite.connect(self.file_name) as db:
            async with db.execute('''DELETE FROM "storage" WHERE "code" = ?''', (code.lower(),)):
                pass
            await db.commit()

    async def mark_code(self, code: str, is_fr: bool, other: bool = False) -> None:
        async with self.lock, aiosqlite.connect(self.file_name) as db:
            async with db.execute('''UPDATE "storage" SET "FR" = ?, "other" = ? WHERE "code" = ?''',
                                  (code.lower(), int(is_fr), int(other))):
                pass
            await db.commit()

    @staticmethod
    async def update_user_index(db: aiosqlite.Connection, user: str, index: int, insert: bool = False) -> None:
        if insert:
            async with db.execute('''INSERT INTO "user_status" VALUES (?, ?)''', (user, index)):
                pass
        else:
            async with db.execute('''UPDATE "user_status" SET "index" = ? WHERE "user_id" = ?''', (index, user)):
                pass
        await db.commit()

    async def request_next_code(self, user: str) -> Optional[str]:
        async with self.lock, aiosqlite.connect(self.file_name) as db:
            async with db.execute('''SELECT "index" FROM "user_status" WHERE "user_id" = ?''', (user,)) as cursor:
                obj = await cursor.fetchone()
                if obj is None:
                    async with db.execute('''
                    SELECT "code", "id" FROM "storage"
                    WHERE "FR" = 0 AND "other" = 0
                    ORDER BY "id" ASC LIMIT 1''') as cursor1:
                        obj = await cursor1.fetchone()
                        if obj is None:
                            return None
                        passcode, current_num = obj
                    await self.update_user_index(db, user, current_num, True)
                else:
                    current_num = obj[0]
                    async with db.execute('''
                    SELECT "code", "id" FROM "storage"
                    WHERE "id" > ? AND "FR" = 0 AND "other" = 0
                    ORDER BY "id" ASC LIMIT 1''',
                                          (current_num,)) as cursor1:
                        obj = await cursor1.fetchone()
                        if obj is None:
                            return None
                        passcode, current_num = obj
                    await self.update_user_index(db, user, current_num)
            return passcode

    async def update_user_status(self, user: str) -> None:
        pass
