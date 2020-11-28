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
import asyncio
import logging
import os
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from typing import Generator, Optional, Tuple

import aiosqlite

logger = logging.getLogger("code_poster").getChild("sqlite")
logger.setLevel(logging.getLogger("code_poster").level)

_DROP_STATEMENT_PasscodeTracker = '''
    DROP TABLE IF EXISTS "code";
    DROP TABLE IF EXISTS "users";
    DROP TABLE IF EXISTS "history";
'''

_CREATE_STATEMENT_PasscodeTracker = '''
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


@dataclass(init=False)
class CodeStatus:
    message_id: int
    FR: bool

    def __init__(self, message_id: int, fr: int):
        self.message_id = message_id
        self.FR = bool(fr)


class SqliteBase(metaclass=ABCMeta):
    def __init__(self, file_name: str):
        self.file_name = file_name
        self.lock = asyncio.Lock()

    @classmethod
    async def _new(cls, file_name: str, drop_statement: str, create_statement: str, *, main_table_name: str, renew: bool = False) -> 'SqliteBase':
        if renew:
            try:
                os.remove(file_name)
            except FileNotFoundError:
                pass
        async with aiosqlite.connect(file_name) as db:
            async with db.execute('''SELECT name FROM sqlite_master WHERE type = 'table' AND name = ? ''',
                                  (main_table_name,)) as cursor:
                if (await cursor.fetchone()) is not None:
                    logger.debug('Found database, load it')
                    return cls(file_name)
            logger.debug('Create new database structure')
            async with db.executescript(drop_statement):
                pass
            async with db.executescript(create_statement):
                pass
        return cls(file_name)

    @classmethod
    @abstractmethod
    async def new(cls, file_name: str, *, renew: bool = False) -> 'SqliteBase':
        return NotImplemented


class PasscodeTracker(SqliteBase):

    @classmethod
    async def new(cls, file_name: str, *, renew: bool = False) -> 'PasscodeTracker':
        return await cls._new(file_name, _DROP_STATEMENT_PasscodeTracker, _CREATE_STATEMENT_PasscodeTracker,
                              main_table_name="code", renew=renew)

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
            async with db.execute('''SELECT "send_by" FROM "history" WHERE "str" LIKE ?''', (f'{s}%',)) as cursor:
                r = await cursor.fetchone()
                if r is None:
                    return None
                return r

    async def query_user(self, user_id: int) -> Optional[bool]:
        async with self.lock, aiosqlite.connect(self.file_name) as db:
            async with db.execute('''SELECT * FROM "users" WHERE "id" = ?''', (user_id,)) as cursor:
                r = await cursor.fetchone()
                if r is None:
                    return None
                return bool(r[1])

    async def query_all_user(self) -> Generator[int, None, None]:
        async with self.lock, aiosqlite.connect(self.file_name) as db:
            async with db.execute('''SELECT * FROM "users" WHERE "authorized" = 1''') as cursor:
                for user_row in await cursor.fetchall():
                    yield user_row[0]

    async def insert_user(self, user_id: int) -> None:
        async with self.lock, aiosqlite.connect(self.file_name) as db:
            async with db.execute('''INSERT INTO "users" VALUES (?, 1)''', (user_id,)):
                pass
            await db.commit()

    async def delete_user(self, user_id: int) -> None:
        async with self.lock, aiosqlite.connect(self.file_name) as db:
            async with db.execute('''DELETE FROM "users" WHERE "id" = ?''', (user_id,)):
                pass
            await db.commit()


class CodeStorage(SqliteBase):
    @classmethod
    async def new(cls, file_name: str, *, renew: bool = False) -> 'CodeStorage':
        return await cls._new(file_name, _DROP_STATEMENT_CodeStorage, _CREATE_STATEMENT_CodeStorage,
                              main_table_name='storage', renew=renew)

    async def insert_code(self, code: str) -> bool:
        async with self.lock, aiosqlite.connect(self.file_name) as db:
            async with db.execute('''SELECT * FROM "storage" WHERE "code" = ? ''', (code,)) as cursor:
                if await cursor.fetchone() is not None:
                    return False
            async with db.execute('''INSERT INTO "storage" ("code") VALUES (?)''', (code,)):
                pass
            await db.commit()
            return True

    async def delete_code(self, code: str) -> None:
        async with self.lock, aiosqlite.connect(self.file_name) as db:
            async with db.execute('''DELETE FROM "storage" WHERE "code" = ?''', (code,)):
                pass
            await db.commit()

    async def mark_code(self, code: str, is_fr: bool, other: bool = False) -> None:
        async with self.lock, aiosqlite.connect(self.file_name) as db:
            async with db.execute('''UPDATE "storage" SET "FR" = ?, "other" = ? WHERE "code" = ?''',
                                  (code, int(is_fr), int(other))):
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
