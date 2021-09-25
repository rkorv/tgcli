import logging
import base64
import os
import time
import traceback
import argparse
import sys

from typing import Dict, List

import requests


def init(host: str = None, port: int = None):
    """Set configuration for TGCLI Client.

    Args:
        host (str, optional): Defaults to "127.0.0.1".
        port (int, optional): Defaults to 4444.
    """
    global TGCLI_PORT
    global TGCLI_HOST

    if isinstance(host, str):
        TGCLI_HOST = host
    if isinstance(port, int):
        TGCLI_PORT = port


def send(
    text: str = None,
    filename: str = "unknown",
    data: bytes = None,
    markdown: bool = False,
    keyboard_choice: List[str] = [],
    reply_to_id: str = None,
) -> str:
    """Send to telegram.

    Example:
        import numpy as np
        import cv2
        img = np.zeros((200, 200, 3), dtype=np.uint8)
        img = cv2.putText(img, "HI TGCLI", (25, 110), 3, 1, (200, 100, 0), 2)
        tgcli.send(filename="file.jpg", data=cv2.imencode(".jpg", img)[1])

    Type of this file will be automaticly recognized from filename extension.
    Images (ex. .png) will be sent as photo.
    Videos (ex. .mp4) will be sent as video.
    Other types will be sent as document.

    This method will not print anything during job.
    Use 'TGCLI_DEBUG' enviroment variable to see error messages.

    Args:
        text (str, optional): Text or caption in case of file.
        filename (str, optional): This name will be displayed in telegram.
        data (bytes, optional): File content.
        markdown (bool, optional): Should telegram parse special chars or no
        keyboard_choice (List[str], optional): Keyboard with this list will be
            created in telegram. You can read answer to this message later.
        reply_to_id (str, optional): Message id

    Returns:
        str: message id or None
    """
    try:
        filecontent = (
            base64.b64encode(bytes(data)).decode("utf-8")
            if data is not None
            else ""
        )
        res = _send(
            {
                "method": "send",
                "data": {
                    "text": text or "",
                    "filename": filename,
                    "filecontent": filecontent,
                    "markdown": markdown,
                    "keyboard_choice": keyboard_choice,
                    "reply_to_id": reply_to_id or "",
                },
            }
        )
        if not res or res["status"] != "ok":
            return None

        return res["data"]["message_id"]

    except Exception as e:
        _debug("%s: %s" % (e, traceback.format_exc()))

    return None


def get_replies(message_ids: List[str] = []) -> Dict:
    """Receive replies.

    Returns:
        Dict: messages or None
    """
    try:
        res = _send(
            {"method": "get_replies", "data": {"message_ids": message_ids}}
        )
        if not res or res["status"] != "ok":
            return None

        return res["data"]["replies"]

    except Exception as e:
        _debug("%s: %s" % (e, traceback.format_exc()))

    return None


def _debug(text: str):
    if TGCLI_DEBUG:
        logging.getLogger("tgcli").error(text)


def _send(data: dict) -> bool:
    req = requests.post(
        _get_connection_string(), json=data, timeout=TGCLI_SEND_TIMEOUT
    )

    if req.status_code != 200:
        return None

    return req.json()


def _get_connection_string():
    return "http://%s:%s" % (TGCLI_HOST, TGCLI_PORT)


def _default_init():
    init(
        host=os.environ.get("TGCLI_HOST", TGCLI_HOST),
        port=int(os.environ.get("TGCLI_PORT", TGCLI_PORT)),
    )

    global TGCLI_DEBUG
    TGCLI_DEBUG = bool(os.environ.get("TGCLI_DEBUG", TGCLI_DEBUG))


TGCLI_PORT = 4444
TGCLI_HOST = "127.0.0.1"

TGCLI_SEND_TIMEOUT = 1
TGCLI_DEBUG = False

_default_init()


def _parse_args():
    description_str = """
CLI for telegram server. You can send file or message.

Examples:
* Send text:
    $ tgcli "Hi tgcli"

* Send image:
    $ tgcli -f ./image.jpg

* Send file:
    $ tgcli -f ./logs.txt

* Pipe output to telegram:
    $ cat file.txt | tgcli
    $ ./run_my_script.sh | tail -n 30 | tgcli

* Get answer from telegram:
    $ should_run=$(tgcli "Run another one script? 0-no; 1-yes;" -r)
    $ echo $should_run

* Get answer from telegram using keyboard:
    $ should_run=$(tgcli "Run another one script?" -c "yes;no")
    $ echo $should_run

To find more details and examples: https://github.com/rkorv/tgcli
"""

    parser = argparse.ArgumentParser(
        description=description_str,
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "text",
        nargs="?",
        default="",
        type=str,
        help="Text to be sent",
    )
    parser.add_argument(
        "--filepath",
        "-f",
        type=str,
        help="""Type of this file will be automaticly recognized from filename extension.
Images (ex. .png) will be sent as photo.
Videos (ex. .mp4) will be sent as video.
Other types will be sent as document.""",
    )
    parser.add_argument(
        "--filename",
        "-n",
        type=str,
        default=None,
        help="""This name will be displayed in telegram. In case of None,
filename will be taken as basename of filepath.""",
    )
    parser.add_argument(
        "--wait_reply",
        "-r",
        action="store_true",
        help="Wait 1 reply message",
    )
    parser.add_argument(
        "--choice",
        "-c",
        type=str,
        default=None,
        help='Wait 1 reply message from list. Example: -c "yes;no"',
    )

    return parser.parse_args()


def _wait_replies(message_ids: str) -> None:
    while True:
        res = get_replies(message_ids)
        if res is None:
            return None
        if res:
            return res

        time.sleep(0.1)


def _run_from_stdin() -> None:
    MAX_MESSAGE_LEN = 4096
    msg_text = ""

    if not os.isatty(sys.stdin.fileno()):
        for line in sys.stdin:
            if len(msg_text) + len(line) > MAX_MESSAGE_LEN:
                send(text=msg_text)
                msg_text = ""
            msg_text += line

        if msg_text:
            send(text=msg_text)

    sys.exit(0)


def _run_from_args() -> None:
    args = _parse_args()
    if not args.filepath and not args.text:
        print("--filename/-f or text required!")
        sys.exit(1)

    send_args = {"text": args.text or ""}

    if args.filepath:
        if not os.path.isfile(args.filepath):
            print("File '%s' doesn't exist!" % args.filepath)
            sys.exit(1)

        send_args["data"] = open(args.filepath, "rb").read()
        send_args["filename"] = args.filename or args.filepath

    if args.choice:
        send_args["keyboard_choice"] = args.choice.split(";")

    if args.wait_reply or args.choice:
        send_args["text"] = (
            "*❓ REPLY TO THIS MESSAGE: *\n---\n```\n%s\n```" % send_args["text"]
        )
        send_args["markdown"] = True

    message_id = send(**send_args)

    if args.wait_reply or args.choice:
        if message_id is None:
            print("[ERROR] Got error while sending")
            sys.exit(1)

        answer = _wait_replies([message_id])
        if answer is None:
            print("[ERROR] Got error while receiving answer")
            sys.exit(1)

        print(answer[message_id][0]["text"])


def main():
    if len(sys.argv) > 1:
        _run_from_args()

    _run_from_stdin()


if __name__ == "__main__":
    main()
