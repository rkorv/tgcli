import logging
import base64
import json
import os
import io
import traceback
from threading import Lock
from typing import Any, Dict, AnyStr, List

from easydict import EasyDict as edict

import uvicorn
from fastapi import FastAPI, HTTPException

from telegram import Update
from telegram.ext import CallbackContext, Updater, ExtBot, CommandHandler

from utils import load_cfg, update_cfg, parse_args, setup_logger

default_cfg = {
    "debug": False,
    "token": "",
    "auth": {"mode": "userlist", "users": [], "password": ""},
    "api": {"host": "0.0.0.0", "port": 4444},
}


class API:
    """
    {
        "method": "send_file",
        "data": {
            "text": "",
            "filename": "",
            "filecontent": ""
        }
    }
    {
        "method": "send_text",
        "data": {
            "text": ""
        }
    }

    Return:
    {
        "status": "ok"
    }
    """

    api = FastAPI()
    tg_bot = None

    @staticmethod
    def _handle_file(data: Dict[AnyStr, Any]):
        if "filename" not in data:
            raise HTTPException(
                status_code=400, detail="filename was not found"
            )
        if "filecontent" not in data:
            raise HTTPException(
                status_code=400, detail="filecontent was not found"
            )

        API.tg_bot.send_file(
            data["filename"], data["filecontent"], data.get("text", None)
        )
        return {"status": "ok"}

    @staticmethod
    def _handle_text(data: Dict[AnyStr, Any]):
        if "text" not in data:
            raise HTTPException(status_code=400, detail="text was not found")

        API.tg_bot.send_text(data["text"])
        return {"status": "ok"}

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
        if req[b"method"] == "send_file":
            ret = API._handle_file(data)
        elif req[b"method"] == "send_text":
            ret = API._handle_text(data)
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
        uvicorn.run(self.api, host=self.cfg.host, port=self.cfg.port)


class TelegramBot:

    IMG_FORMATS = [".jpg", ".jpeg", ".png"]
    VIDEO_FORMATS = [".mp4", ".avi", ".mov"]

    class Database:
        DEFAULT_PATH = "/tmp/tgcli_database.json"

        def __init__(self, db_path: str, init_users: List[str]):
            self._logger = logging.getLogger(self.__class__.__name__)
            self._db_path = db_path
            self.lock = Lock()
            self._db = {}

            try:
                if os.path.isfile(self._db_path):
                    with open(self._db_path, "r") as json_file:
                        self._db = json.load(json_file)
                else:
                    self._logger.info(
                        "Database '%s' not found. Creating" % self._db_path
                    )
                    with open(self._db_path, "w") as f:
                        f.write(json.dumps({}))
            except Exception:
                self._logger.error(
                    "Can't read or create database '%s'... Reading default at '%s'"
                    % (self._db_path, self.DEFAULT_PATH)
                )
                self._db_path = self.DEFAULT_PATH
                self._db = {}

                try:
                    if os.path.isfile(self._db_path):
                        with open(self._db_path, "r") as json_file:
                            self._db = json.load(json_file)
                except Exception:
                    self._logger.info(
                        "Can't read default database '%s'... " % self._db_path
                    )

            self._db.setdefault("users", {"active": [], "inactive": []})

            with self.lock:
                for user_id in init_users:
                    user_id = str(user_id).strip()
                    if (
                        user_id not in self._db["users"]["active"]
                        and user_id not in self._db["users"]["inactive"]
                    ):
                        self._db["users"]["active"].append(user_id)

            self._logger.info("Starting with database: %s" % self._db)
            self._save_db()

        def _save_db(self):
            with self.lock:
                with open(self._db_path, "w") as f:
                    f.write(json.dumps(self._db, indent=4))

        def is_user_valid(self, user_id: str) -> bool:
            with self.lock:
                return (
                    user_id in self._db["users"]["active"]
                    or user_id in self._db["users"]["inactive"]
                )

        def add_user(self, user_id: str) -> None:
            with self.lock:
                if (
                    user_id not in self._db["users"]["active"]
                    and user_id not in self._db["users"]["inactive"]
                ):
                    self._db["users"]["active"].append(user_id)
            self._save_db()

        def is_user_active(self, user_id: str) -> bool:
            with self.lock:
                return user_id in self._db["users"]["active"]

        def get_active_user_list(self) -> List[str]:
            with self.lock:
                return self._db["users"]["active"].copy()

        def activate_user(self, user_id: str) -> None:
            with self.lock:
                if user_id in self._db["users"]["inactive"]:
                    self._db["users"]["inactive"].remove(user_id)
                    if user_id not in self._db["users"]["active"]:
                        self._db["users"]["active"].append(user_id)
            self._save_db()

        def deactivate_user(self, user_id: str) -> None:
            with self.lock:
                if user_id in self._db["users"]["active"]:
                    self._db["users"]["active"].remove(user_id)
                    if user_id not in self._db["users"]["inactive"]:
                        self._db["users"]["inactive"].append(user_id)
            self._save_db()

    def _command_start(self, update: Update, context: CallbackContext) -> None:
        if not update.message:
            return

        user_id = str(update.message["chat"]["id"])

        if not self._db.is_user_valid(user_id):
            if self.cfg.mode == "userlist":
                update.message.reply_text(
                    "Entrance is only by userlist... Tell admin your id '%s'"
                    % user_id
                )
            else:
                update.message.reply_text(
                    "Tell admin your id '%s' or login using /password <your_password>"
                    % user_id
                )

            self._logger.warning("Unknown user '%s' tried to start" % user_id)
            return

        self._db.activate_user(user_id)
        update.message.reply_text(
            "Bot will send all messages to you. Use /stop to break it."
        )

    def _command_stop(self, update: Update, context: CallbackContext) -> None:
        if not update.message:
            return

        user_id = str(update.message["chat"]["id"])

        if not self._db.is_user_valid(user_id):
            update.message.reply_text(
                "You are not in database, but ok, you will not receive messages..."
            )

        if not self._db.is_user_active(user_id):
            update.message.reply_text(
                "You're not receiving any messages right now. Use /start to resume them."
            )

        self._db.deactivate_user(user_id)
        update.message.reply_text(
            "You will not receive any more messages. Use /start to resume them."
        )

    def _command_password(
        self, update: Update, context: CallbackContext
    ) -> None:

        if not update.message:
            return

        user_id = str(update.message["chat"]["id"])

        if self._db.is_user_valid(user_id):
            update.message.reply_text("You already have access.")
            return

        if self.cfg.mode == "userlist":
            update.message.reply_text(
                "Nice try. But auth is only by userlist... Tell admin your id '%s'"
                % user_id
            )
            self._logger.warning(
                "User '%s' tried to login password when auth mode is 'userlist'"
                % user_id
            )
            return

        if not context.args:
            update.message.reply_text(
                "Can't parse your password. Use: /password <your_password>"
            )
            return

        password = str(context.args[0]).strip()
        if self.cfg.password != password:
            update.message.reply_text("Incorrect password")
            self._logger.warning(
                "User '%s' tried to login with wrong password '%s'"
                % (user_id, password)
            )
            return

        self._db.add_user(user_id)
        update.message.reply_text(
            "You have been added to database! "
            "Use '/start' to receive messages and '/stop' to break it.",
        )
        self._logger.warning("User '%s' was added to database!" % user_id)

    def _error_handler(self, update: object, context: CallbackContext) -> None:
        self._logger.error(
            msg="Exception while handling an update:", exc_info=context.error
        )
        tb_list = traceback.format_exception(
            None, context.error, context.error.__traceback__
        )
        tb_string = "".join(tb_list)
        self._logger.error("Traceback: %s" % tb_string)

    def __init__(self, db_path: str, token: str, cfg: edict):
        self.cfg = cfg
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info("Starting with cfg: %s" % self.cfg)
        self._db = TelegramBot.Database(db_path, self.cfg.users)
        self._updater = Updater(token, use_context=True)

        dp = self._updater.dispatcher
        self.bot = self._updater.bot

        dp.add_handler(CommandHandler("start", self._command_start))
        dp.add_handler(
            CommandHandler("password", self._command_password, pass_args=True)
        )
        dp.add_handler(CommandHandler("stop", self._command_stop))
        dp.add_error_handler(self._error_handler)

        self._updater.start_polling()

    def send_text(self, text: str):
        for user_id in self._db.get_active_user_list():
            self.bot.send_message(chat_id=user_id, text=text)

    def send_file(self, filename: str, filecontent: str, text: str = None):
        method = self.bot.send_document

        ext = os.path.splitext(filename)[1]
        if ext in self.IMG_FORMATS:
            method = self.bot.send_photo
        elif ext in self.VIDEO_FORMATS:
            method = self.bot.send_video

        bio = io.BytesIO(base64.b64decode(filecontent))
        bio.name = filename
        for user_id in self._db.get_active_user_list():
            method(user_id, bio, filename=filename, caption=text)
            bio.seek(0)

    def stop(self):
        self._logger.info("Stopping telegram bot...")
        self._updater.stop()


class App:
    def __init__(self, db_path: str, cfg: edict):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.tg_bot = TelegramBot(db_path, cfg.token, cfg.auth)
        self.api = API(cfg.api, self.tg_bot)

        self._logger.info("All modules were inited")

    def run(self) -> None:
        self.api.run()

    def stop(self) -> None:
        self.tg_bot.stop()


def main():
    args = parse_args()
    cfg = update_cfg(load_cfg(args.config), default_cfg, args)
    setup_logger(cfg)

    logger = logging.getLogger()
    logger.info("Starting with cfg: %s" % cfg)

    app = App(args.database, cfg)
    app.run()
    app.stop()

    logger.info("Finished!")


if __name__ == "__main__":
    main()
