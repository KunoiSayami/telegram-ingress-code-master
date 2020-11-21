## Usage

* Copy `config.ini.default` to `config.ini`
* Fill all blanks except section (`telegram`, `bot_token`), (`telegram`, `channel`), (`telegram`, `password`)
* Install requirements
```shell script
pip install aiofiles aiohttp pyrogram aiosqlite
```
* Start server
```shell script
python3 localserver.py
```

## Configure file structure

```ini
[telegram]
; Obtain api_id and api_hash them from telegram
api_id =
api_hash =

[server]
; Specify listen only message from user id
listen_user =
; Bot token listen message from listen_user
bot_token =

[web]
; Server bind address
bind = 127.0.0.1
; Server listen port
port = 29985
; Server fetch prefix
; e.g. set default_prefix to "ws"
; Connect to server use ws://localhost:29985/ws
default_prefix =
```

## Load from local

* If you want to read passcode from local, put passcode to `passcode.txt`, one passcode each line.
* Run server with `--load` parameters
```shell script
python3 localserver.py --load
```