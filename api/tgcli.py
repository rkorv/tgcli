import requests
import logging
import base64
import os
import traceback
import argparse
import sys


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


def send_text(text: str) -> bool:
    """Just sends message to telegram.

    All "send_" methods will not print anything during job.
    Use 'TGCLI_DEBUG' enviroment variable to see error messages.

    Args:
        text (str): Message body.

    Returns:
        bool: False in case of connection problem.
    """
    try:
        return _send({"method": "send_text", "data": {"text": text}})
    except Exception as e:
        _debug("%s: %s" % (e, traceback.format_exc()))

    return False


def send_file(filepath: str, text: str = None, filename: str = None) -> bool:
    """Read file from your system and send it to telegram.

    Type of this file will be automaticly recognized from filename extension.
    Images (ex. .png) will be sent as photo.
    Videos (ex. .mp4) will be sent as video.
    Other types will be sent as document.

    All "send_" methods will not print anything during job.
    Use 'TGCLI_DEBUG' enviroment variable to see error messages.

    Be careful, file must be accessible by specified path.

    Args:
        filepath (str): Path to the file to be read.
        text (str, optional): Caption for this file. Defaults to None.
        filename (str, optional): This name will be displayed in telegram.
            In case of None, filename will be taken as basename of filepath.

    Returns:
        bool: False in case of file reading error or connection problem.
    """
    if not os.path.isfile(filepath):
        _debug("File '%s' was not found!" % filepath)
        return False

    try:
        with open(filepath, "rb") as f:
            data = f.read()
        filename = filename or filepath

        return send_bytes(os.path.basename(filepath), data, text)

    except Exception as e:
        _debug("%s: %s" % (e, traceback.format_exc()))

    return False


def send_bytes(filename: str, data: bytes, text: str = None) -> bool:
    """Send bytes to telegram as file.

    Example:
        img = np.zeros((200, 200, 3), dtype=np.uint8)
        cv2.putText(img, "HI TGCLI", (25, 110), 3, 1, (200, 100, 0), 2)
        send_bytes("file.jpg", cv2.imencode(".jpg", img)[1])

    Type of this file will be automaticly recognized from filename extension.
    Images (ex. .png) will be sent as photo.
    Videos (ex. .mp4) will be sent as video.
    Other types will be sent as document.

    All "send_" methods will not print anything during job.
    Use 'TGCLI_DEBUG' enviroment variable to see error messages.

    Args:
        filename (str): This name will be displayed in telegram.
        text (str, optional): Caption for this file. Defaults to None.

    Returns:
        bool: False in case of file reading error or connection problem.
    """
    try:
        return _send(
            {
                "method": "send_file",
                "data": {
                    "text": text or "",
                    "filename": filename,
                    "filecontent": base64.b64encode(bytes(data)).decode(
                        "utf-8"
                    ),
                },
            }
        )
    except Exception as e:
        _debug("%s: %s" % (e, traceback.format_exc()))

    return False


def _debug(text: str):
    if TGCLI_DEBUG:
        logging.getLogger("tgcli").error(text)


def _send(data: dict) -> bool:
    return (
        requests.post(
            _get_connection_string(), json=data, timeout=TGCLI_SEND_TIMEOUT
        ).status_code
        == 200
    )


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


def _run_from_stdin():
    MAX_MESSAGE_LEN = 4096
    msg_text = ""

    for line in sys.stdin:
        if len(msg_text) + len(line) > MAX_MESSAGE_LEN:
            send_text(msg_text)
            msg_text = ""
        msg_text += line

    if msg_text:
        send_text(msg_text)

    sys.exit(0)


def _parse_args():
    description_str = """
CLI for telegram server. You can send file or message.

Examples:
    $ tgcli "Hi tgcli"
    $ tgcli -f ./image.jpg
    $ cat file.txt | tgcli

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

    return parser.parse_args()


def _run_from_args():
    args = _parse_args()
    if not args.filepath and not args.text:
        print("--filename/-f or text required!")
        sys.exit(1)

    if args.filepath:
        if not os.path.isfile(args.filepath):
            print("File '%s' doesn't exist!" % args.filepath)
            sys.exit(1)
        send_file(args.filepath, args.text, args.filename)
    else:
        send_text(args.text)

    sys.exit(0)


def main():
    if len(sys.argv) == 1:
        _run_from_stdin()
    else:
        _run_from_args()


if __name__ == "__main__":
    main()
