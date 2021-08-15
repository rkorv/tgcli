# INTRODUCTION

Send messages and files to telegram directly from the terminal or python api with tgcli.

The project was created to help developers who have to monitor system for long hours :) You can create a telegram bot and monitor the server state directly from your phone.

<p align="center">
  <img src="https://drive.google.com/uc?export=view&id=1no-9WBDDwFhYB49mT0QGliLwBUJtpMUz" />
</p>


# QUICK INSTALLATION
0. Create telegram bot ([telegram docs](https://core.telegram.org/bots#6-botfather))
    > Ok, now you have a telegram token like "110201543:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"

1. Run server
    ```bash
    $ PASSWORD=<password>
    $ TOKEN=<token>
    $ docker run -d --name tgcli_server -v /tmp/:/workspace/ --restart always -p 4444:4444 rkorv/tgcli:latest tgcli_server --token $TOKEN --auth_mode password --auth_password $PASSWORD
    ```

2. Log in to your bot. Open chat and write
    > /password \<password\>

3. Send message
    ```bash
    $ docker run --rm --network host rkorv/tgcli:latest tgcli "Hi from TGCLI"
    ```

    OR without docker (for python>=3.6):
    ```bash
    $ git clone https://github.com/rkorv/tgcli
    $ cd tgcli/api && pip install --no-cache-dir .
    $ tgcli "Hi from TGCLI!"
    ```

# USE CASES
## TGCLI

This api is low-level and only allows you to send messages or files. To use more complex cases, see **TOOLBOX** chapter.

### Bash
```bash
# Send text
$ tgcli "Hello!"

# Send image
$ tgcli -f ./image.jpg
$ tgcli -f ./image.jpg "It is my image"

# Send file
$ tgcli -f ./logs.txt
$ tgcli -f ./logs.txt "night build logs"

# Bash pipe (send as text)
$ tail ./logs.txt | tgcli

# Long build
$ ./build.sh && tgcli "Build done!" || tgcli "Build failed..."
```

### Python
```python
>>> import tgcli

# Send text
>>> tgcli.send_text("Hi!")
True

# Send file from disk
>>> tgcli.send_file("./Downloads/jetson_apt_list.txt")
True
>>> tgcli.send_file("./Downloads/logs.txt", "and some information about this")
True

# Send images from np array
>>> import numpy as np
>>> import cv2
>>> img = np.zeros((200, 200, 3), dtype=np.uint8)
>>> img = cv2.putText(img, "HI TGCLI", (25, 110), 3, 1, (200, 100, 0), 2)
>>> tgcli.send_bytes("file.jpg", cv2.imencode(".jpg", img)[1])
True
```

<p align="center">
  <img src="https://drive.google.com/uc?export=view&id=1GIgqf-j8sAOQonivLtc5d7VcbddpxB45" height=400 />
</p>

# TOOLBOX

This repository already contains some scripts for convenient work with the system.

<p align="center">
  <img src="https://drive.google.com/uc?export=view&id=1SsGj5cLi1OOT8TNGeP3DXb_Bc7Tq-GJ9" />
</p>


- Send file on interval
    ```bash
    $ F="logs.txt" INTERVAL="20m"
    $ touch $F && docker run --rm -d --network host -v $(realpath $F):/workspace/$(basename "$F") rkorv/tgcli_toolbox:latest tgcli_monitor_file -f $(basename "$F") $INTERVAL
    ```
- Send file on change
    ```bash
    $ F="metrics.png"
    $ touch $F && DF="/workspace/$(basename $F)" && docker run --rm -d --network host -v $(realpath $F):$DF rkorv/tgcli_toolbox:latest bash -c "while :; do inotifywait $DF; tgcli -f $DF \"File '$F' was changed\"; done;"
    ```
- Send tail on interval
    ```bash
    $ F="logs.txt" INTERVAL="10m" TLINES="20"
    $ touch $F && docker run --rm -d --network host -v $(realpath $F):/workspace/$(basename "$F") rkorv/tgcli_toolbox:latest tgcli_monitor_tail -f $(basename "$F") -l $TLINES $INTERVAL
    ```
- Send system metrics
    ```
    $ docker run --rm -d -v /proc:/proc -v /sys:/sys -v /etc:/etc --network host rkorv/tgcli_toolbox:latest tgcli_monitor_system 20m
    ```

P.S. You can implement 'realpath' for MacOS:
```bash
realpath() {
    [[ $1 = /* ]] && echo "$1" || echo "$PWD/${1#./}"
}
```

# CONFIGURATION
## Server

1. Create configuration file somewhere. For example ./tgcli_config.json
```json
{
    "token": "",
    "auth": {
        "mode": "userlist",
        "users": [],
        "password": "strong_password"
    },
    "api": {
        "host": "0.0.0.0",
        "port": 4444
    }
}
```

* **token** - token for your telegram bot
* **auth.mode** - 'userlist' opens access only for users from the configuration
            file, 'password' allows you to connect both: users from list and
            anyone who knows the password
* **auth.users** - list of user or chat ids. To find it, you can send '*/start*' message to your bot to get your id. And restart bot with new config.
* **auth.password** - you can skip this in case of '*userlist*' auth mode.

2. Create empty json file for database with users. For example:
```bash
$ echo "{}" > ./tgcli_database.json
```

3. Run server
```bash
$ docker run -d --name tgcli_server -v $PWD/tgcli_database.json:/workspace/tgcli_database.json -v $PWD/tgcli_config.json:/workspace/tgcli_config.json --restart always -p 4444:4444 rkorv/tgcli_server:latest tgcli_server
```

## Client
In case if you need to change port or host, you can do it with eviroment variables.

### Bash
```bash
$ TGCLI_PORT=4444 TGCLI_HOST="127.0.0.1" tgcli "Hi"
```

### Python
```python
>>> import tgcli
>>> tgcli.init("127.0.0.1", 4444)
```
