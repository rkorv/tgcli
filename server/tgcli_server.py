import logging
import base64
import time
import argparse
import os
import io
import gc
import traceback
from typing import Any, Dict, AnyStr, List

from easydict import EasyDict as edict

import uvicorn
from fastapi import FastAPI, HTTPException

from telegram import (
    Update,
    ParseMode,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    CallbackContext,
    Updater,
    ExtBot,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackQueryHandler,
)

import schedule
from easydict import EasyDict as edict


default_cfg = {
    "debug": False,
    "bot": {"token": "", "chat": ""},
    "api": {"host": "0.0.0.0", "port": 4444},
}


def setup_logger(cfg: dict):
    logger = logging.getLogger()
    logger_level = logging.DEBUG if cfg.debug else logging.INFO
    logger.setLevel(logger_level)

    def add_channel(ch):
        ch.setLevel(logger_level)
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s][%(name)s]: %(message)s"
        )
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    ch = logging.StreamHandler()
    add_channel(ch)

    return logger


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--token",
        "-t",
        default=None,
        type=str,
        help="Telegram bot token.",
    )
    parser.add_argument(
        "--chat",
        "-c",
        default=None,
        type=str,
        help="Chat id for telegram.",
    )

    return parser.parse_args()


def update_cfg(cfg, args) -> dict:
    """Update default cfg by cfg file and eviroment variables."""

    cfg = edict(cfg)

    if args.chat:
        cfg.bot.chat = str(args.chat).strip()
    cfg.bot.chat = os.environ.get("TGCLI_CHAT", cfg.bot.chat)

    if args.token:
        cfg.bot.token = str(args.token).strip()
    cfg.bot.token = os.environ.get("TGCLI_TOKEN", cfg.bot.token)

    # Debug is not a part of args just for compact cli
    cfg.debug = bool(os.environ.get("TGCLI_DEBUG", cfg.debug))

    # API can't be part of args because of Python API. To keep it easy to
    # use and avoid init functions, default port and host should be used
    # there. In case of port overlapping, just replace them by evironment.
    cfg.api.host = os.environ.get("TGCLI_HOST", cfg.api.host)
    cfg.api.port = int(os.environ.get("TGCLI_PORT", cfg.api.port))

    if not cfg.bot.chat.strip():
        print("[ERROR] Can't read chat id: '%s'" % cfg.bot.chat)

    if not cfg.bot.token.strip():
        print("[ERROR] Can't read token: '%s'" % cfg.bot.token)
        exit(1)

    return cfg


class API:
    """
    --->
    {
        "method": "send",
        "data": {
            "text": "",
            "filename": "",
            "filecontent": "",
            "keyboard_choice": [],
            "markdown": false,
            "reply_to_id": ""
        }
    }
    <---
    {
        "status": "ok",
        "data": {
            "message_id": "25"
        }
    }
    --->
    {
        "method": "get_replies",
        "data": {
            "message_ids": ["25"]
        }
    }
    <---
    {
        "status": "ok",
        "data": {
            "replies": {
                "25": ["one", "another_one"]
            },
        }
    }
    <---
    {
        "status": "none",
        "data": {
            "replies": {}
        }
    }
    """

    api = FastAPI()
    tg_bot = None

    @staticmethod
    def _handle_send(data: Dict[AnyStr, Any]):
        args = {
            "text": "",
            "filename": "",
            "filecontent": "",
            "keyboard_choice": [],
            "markdown": False,
            "reply_to_id": "",
        }
        args.update(data)

        message_id = API.tg_bot.send(**args)
        if message_id is None:
            raise HTTPException(status_code=500, detail="Something went wrong")

        return {"status": "ok", "data": {"message_id": str(message_id)}}

    @staticmethod
    def _handle_get_replies(data: Dict[AnyStr, Any]):
        args = {
            "message_ids": [],
        }
        args.update(data)

        replies = API.tg_bot.get_replies(**args)
        return {"status": "ok", "data": {"replies": replies}}

    @api.post("/")
    async def root(req: Dict[AnyStr, Any] = None):
        if not req or b"method" not in req.keys():
            raise HTTPException(
                status_code=404, detail="'method' keyword was not found"
            )

        data = req.get(b"data", {})
        if not data:
            raise HTTPException(status_code=400, detail="data was not found")

        ret = {"status": "unknown_error"}
        if req[b"method"] == "send":
            ret = API._handle_send(data)
        elif req[b"method"] == "get_replies":
            ret = API._handle_get_replies(data)
        else:
            raise HTTPException(status_code=404, detail="Unknown method")

        if ret["status"] != "ok":
            raise HTTPException(status_code=500, detail="Something went wrong")

        return ret

    def __init__(self, cfg: dict, tg_bot: ExtBot):
        self.cfg = cfg
        API.tg_bot = tg_bot
        self._logger = logging.getLogger(self.__class__.__name__)

    def run(self):
        uvicorn.run(
            self.api, host=self.cfg.host, port=self.cfg.port, log_level="error"
        )


class TelegramBot:

    IMG_FORMATS = [".jpg", ".jpeg", ".png"]
    VIDEO_FORMATS = [".mp4", ".avi", ".mov"]

    SAVE_REPLIES_DAYS = 2
    SAVE_REPLIES_SEC = SAVE_REPLIES_DAYS * 24 * 60 * 60

    def _command_start(self, update: Update, context: CallbackContext) -> None:
        if not update.message:
            return

        chat_id = str(update.message["chat"]["id"])

        if chat_id != self.cfg.chat:
            update.message.reply_text(
                "You should restart bot with your chat id: '%s'." % chat_id
            )
            self._logger.warning("Unknown user '%s' tried to start" % chat_id)
            return

        update.message.reply_text(
            "Everything is fine... Bot will send all messages to you..."
        )

    def _message_handler(
        self, update: Update, context: CallbackContext
    ) -> None:
        source_msg = update.message.reply_to_message
        if not source_msg:
            return None

        message_id = str(source_msg.message_id)
        if message_id not in self._replies_map:
            self._replies_map[message_id] = []
        self._replies_map[message_id].append(
            {
                "ts": time.time(),
                "message_id": str(update.message.message_id),
                "text": update.message.text,
            }
        )

        self._scheduler.run_pending()

    def _reply_handler(self, update: Update, context: CallbackContext) -> None:
        msg = update.callback_query.message
        self.bot.edit_message_text(
            chat_id=self.cfg.chat,
            message_id=msg.message_id,
            text=msg.text + "\n---\nGot answer: " + update.callback_query.data,
            reply_markup=None,
        )

        message_id = str(msg.message_id)
        if message_id not in self._replies_map:
            self._replies_map[message_id] = []
        self._replies_map[message_id].append(
            {
                "ts": time.time(),
                "message_id": message_id,
                "text": update.callback_query.data,
            }
        )

        self._scheduler.run_pending()

    def _error_handler(self, update: object, context: CallbackContext) -> None:
        self._logger.error(
            msg="Exception while handling an update:", exc_info=context.error
        )
        tb_list = traceback.format_exception(
            None, context.error, context.error.__traceback__
        )
        tb_string = "".join(tb_list)
        self._logger.error("Traceback: %s" % tb_string)

    def __init__(self, cfg: edict):
        self.cfg = cfg
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info("Starting with cfg: %s" % self.cfg)

        self._updater = Updater(self.cfg.token, use_context=True)

        dp = self._updater.dispatcher
        self.bot = self._updater.bot

        dp.add_handler(CommandHandler("start", self._command_start))
        dp.add_error_handler(self._error_handler)
        dp.add_handler(
            MessageHandler(
                Filters.reply
                & Filters.text
                & ~Filters.command
                & ~Filters.update.edited_message,
                self._message_handler,
            )
        )
        dp.add_handler(CallbackQueryHandler(self._reply_handler))

        self._scheduler = schedule.Scheduler()
        self._scheduler.every(1).days.do(self._remove_old_replies)

        self._replies_map = {}
        self._updater.start_polling()

    def _remove_old_replies(self):
        new_map = {}
        keep_after_ts = time.time() - self.SAVE_REPLIES_SEC
        for k in self._replies_map:
            new_list = [
                v for v in self._replies_map[k] if v["ts"] > keep_after_ts
            ]

            if new_list:
                new_map[k] = new_map

        self._replies_map = new_map
        gc.collect()

    def _get_keyboard(self, keyboard_choice: List[str]):
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(text=text, callback_data=text)]
                for text in keyboard_choice
            ]
        )

    def get_replies(self, message_ids: List[str]) -> Dict:
        new_map = {}

        for message_id in message_ids:
            message_id = str(message_id)
            if message_id in self._replies_map:
                new_map[message_id] = self._replies_map[message_id]
                del self._replies_map[message_id]

        return new_map

    def send(
        self,
        text: str = "",
        filename: str = "unknown",
        filecontent: str = "",
        markdown: bool = False,
        keyboard_choice: List[str] = [],
        reply_to_id: str = "",
    ) -> str:
        if not self.cfg.chat:
            return None

        parse_mode = ParseMode.MARKDOWN if markdown else None

        reply_to_id = int(reply_to_id) if reply_to_id else None
        filecontent = filecontent or None
        text = text or None
        reply_markup = (
            None if not keyboard_choice else self._get_keyboard(keyboard_choice)
        )

        if filecontent is None:
            if text is None:
                return None

            msg = self.bot.send_message(
                chat_id=self.cfg.chat,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                reply_to_message_id=reply_to_id,
            )
            return msg.message_id

        bio = io.BytesIO(base64.b64decode(filecontent))

        method = self.bot.send_document
        if filename and str(filename).find(".") != -1:
            ext = os.path.splitext(filename)[1]
            if ext in self.IMG_FORMATS:
                method = self.bot.send_photo
            elif ext in self.VIDEO_FORMATS:
                method = self.bot.send_video

            bio.name = filename

        msg = method(
            self.cfg.chat,
            bio,
            filename=filename,
            reply_markup=reply_markup,
            caption=text,
            reply_to_message_id=reply_to_id,
        )
        bio.close()

        return msg.message_id

    def stop(self):
        self._logger.info("Stopping telegram bot...")
        self._updater.stop()


class App:
    def __init__(self, cfg: edict):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.tg_bot = TelegramBot(cfg.bot)
        self.api = API(cfg.api, self.tg_bot)

        self._logger.info("All modules were inited")

    def run(self) -> None:
        self.api.run()

    def stop(self) -> None:
        self.tg_bot.stop()


def main():
    args = parse_args()
    cfg = update_cfg(default_cfg, args)
    setup_logger(cfg)

    logger = logging.getLogger()
    logger.info("Starting with cfg: %s" % cfg)

    app = App(cfg)
    app.run()
    app.stop()

    logger.info("Finished!")


if __name__ == "__main__":
    main()
