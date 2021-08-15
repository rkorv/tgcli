import argparse
import logging
import sys
import os
import json

from easydict import EasyDict as edict


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
        "--auth_mode",
        "-a",
        default="userlist",
        choices=["userlist", "password"],
        type=str,
        help="""'userlist' opens access only for users from the configuration
            file, 'password' allows you to connect both: users from list and
            anyone who knows the password.""",
    )
    parser.add_argument(
        "--auth_password",
        "-p",
        default=None,
        type=str,
        help="System password. Only for 'password' auth type",
    )
    parser.add_argument(
        "--token",
        "-t",
        default=None,
        type=str,
        help="Telegram bot token.",
    )
    parser.add_argument(
        "--config",
        "-c",
        default="/workspace/tgcli_config.json",
        type=str,
        help="Telegram bot token.",
    )
    parser.add_argument(
        "--database",
        "-d",
        default="/workspace/tgcli_database.json",
        type=str,
        help="Telegram bot token.",
    )

    return parser.parse_args()


def _merge(destination: dict, source: dict):
    for key, value in source.items():
        if isinstance(value, dict):
            node = destination.setdefault(key, {})
            _merge(node, value)
        else:
            destination[key] = value

    return destination


def _update_cfg(default_cfg: dict, cfg: dict) -> dict:
    """Merge 'cfg' arg to 'default_cfg'."""
    merged_cfg = _merge(dict(default_cfg), dict(cfg))
    return edict(merged_cfg)


def load_cfg(cfg_path) -> dict:
    """Just load cfg file or exit from the app."""
    cfg = {}
    print("Loading cfg from: %s" % cfg_path)
    if os.path.isfile(cfg_path):
        with open(cfg_path) as json_file:
            cfg = json.load(json_file)
    else:
        print("[WARNING] Config not found! Loading with default.")

    return cfg


def update_cfg(cfg, default_cfg, args) -> dict:
    """Update default cfg by cfg file and eviroment variables."""

    cfg = _update_cfg(default_cfg, cfg)

    if args.auth_password is not None:
        new_password = str(args.auth_password).strip()
        if not new_password:
            print("[ERROR] Can't read password: '%s'" % args.auth_password)
            sys.exit(1)
        cfg.auth.password = args.auth_password

    cfg.auth.mode = args.auth_mode
    if cfg.auth.mode == "password" and not cfg.auth.password.strip():
        print("[ERROR] Can't read password: '%s'" % cfg.auth.password)
        exit(1)

    if cfg.auth.mode == "password":
        print("[INFO] Starting with password: '%s'" % cfg.auth.password)
    else:
        print("[INFO] Starting with userlist: %s" % cfg.auth.users)

    # Debug is not a part of args just for compact cli
    cfg.debug = bool(os.environ.get("TGCLI_DEBUG", cfg.debug))

    # API can't be part of args because of Python API. To keep it easy to
    # use and avoid init functions, default port and host should be used
    # there. In case of port overlapping, just replace them by evironment.
    cfg.api.host = os.environ.get("TGCLI_HOST", cfg.api.host)
    cfg.api.port = int(os.environ.get("TGCLI_PORT", cfg.api.port))
    cfg.token = os.environ.get("TGCLI_TOKEN", cfg.token)

    if args.token:
        cfg.token = args.token

    return cfg
