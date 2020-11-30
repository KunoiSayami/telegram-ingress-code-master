## Usage

* Copy `config.ini.default` to `config.ini`
* Fill `web` section in configure file if you want to start web server only.
* Otherwise, Fill all blanks except option (`telegram`, `bot_token`), (`telegram`, `channel`), (`telegram`, `password`)
* Install requirements
```shell script
pip install -r requirements.txt
```
* Init submodule
```shell script
git submodule update --init
```
* Start server
```shell script
./bootstrap.py
```

## Load from local

* If you want to read passcode from local, put passcode to `passcode.txt`, one passcode each line.
* Run server with `--load` parameter.
```shell script
./bootstrap.py --load
```

## Server core only

* If you want to run web server only, use `--nbot` parameter.

```shell script
./bootstrap.py --nbot
```

## Configure ssl

Following [here](cert.md)
