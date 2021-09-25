# INTRODUCTION

Send messages and files to telegram and wait for replies directly from the terminal or python api with tgcli.

This project was created to help developers who have to monitor system or ML models for long hours :) You can create a telegram bot to monitor and control your server directly from your phone.

<p align="center">
  <img width=700px src="https://drive.google.com/uc?export=view&id=18V751lLm5cx-FoRoC3ueOAdLjl5eoN5e" />
</p>

# QUICK INSTALLATION
0. Create telegram bot ([telegram docs](https://core.telegram.org/bots#6-botfather))
    > Ok, now you have a telegram token like "110201543:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"

1. Run server
    ```bash
    $ CHAT=<chat_id>
    $ TOKEN=<token>
    $ docker run -d --name tgcli_server --restart always -p 4444:4444 rkorv/tgcli:latest tgcli_server --token $TOKEN --chat $CHAT
    ```

    If you have no idea which chat_id to use, then just start the server without this argument, and send "/start" message to the bot.

2. Send message
    ```bash
    $ docker run --rm -it --network host rkorv/tgcli:latest tgcli "Hi TGCLI"
    ```

    OR without docker (for python>=3.6):
    ```bash
    $ git clone https://github.com/rkorv/tgcli
    $ cd tgcli/tgcli && pip install --no-cache-dir .
    $ tgcli "Hi TGCLI"
    ```

# USE CASES
## TGCLI

This api is low-level and only allows you to send messages or files. To use more complex cases, see **TOOLBOX** chapter.

### Bash
```bash
# Send text
$ tgcli "Hello..."

# Send image
$ tgcli -f ./image.jpg
$ tgcli "It is my image" -f ./image.jpg

# Send file
$ tgcli -f ./logs.txt
$ tgcli "night build logs" -f ./logs.txt

# Bash pipe (send as text)
$ cat file.txt | tgcli
$ ./run_my_script.sh | tail -n 30 | tgcli

# Long build
$ ./build.sh && tgcli "Build done!" || tgcli "Build failed..."

# Get reply from telegram:
$ lr=$(tgcli "Learning rate?" -r)
$ echo $lr

# Get answer from telegram using keyboard:
$ should_run=$(tgcli "Run another one script?" -c "yes;no")
$ echo $should_run
```

### Python
```python
>>> import tgcli

# Send text
>>> message_id = tgcli.send(text="Hi!")

# Send image from np array
>>> import numpy as np
>>> import cv2
>>> img = np.zeros((200, 200, 3), dtype=np.uint8)
>>> img = cv2.putText(img, "HI TGCLI", (25, 110), 3, 1, (200, 100, 0), 2)
>>> img_bytes = cv2.imencode(".jpg", img)[1]
>>> message_id = tgcli.send(filename="file.jpg", data=img_bytes)
```


# TOOLBOX

This repository already contains some scripts for convenient work with the system.

## Installation

Without docker (for python>=3.6):
```bash
$ git clone https://github.com/rkorv/tgcli
$ cd tgcli/toolbox && pip install --no-cache-dir .
```

## Examples

- Send file on interval (Interval in human format. Ex: '10m', '1h 30m', '1m 30s')
    ```bash
    $ tgcli_monitor_file ./image.png 10m

    # send on change
    $ tgcli_monitor_file ./image.png
    ```
- Send tail on interval
    ```bash
    $ tgcli_monitor_tail ./my_app.log 5s

    # set lines limit:
    $ tgcli_monitor_tail ./my_app.log 5s -l 5
    ```
- Send changed files in directory
    ```bash
    $ tgcli_monitor_dir ./
    ```

# CONFIGURATION
In case if you need to change port or host, you can do it with eviroment variables.

## Bash
```bash
$ TGCLI_PORT=4444 TGCLI_HOST="127.0.0.1" tgcli "Hi"
```

## Python
```python
>>> import tgcli
>>> tgcli.init("127.0.0.1", 4444)
```
