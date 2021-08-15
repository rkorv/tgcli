import argparse
import os
import time

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import tgcli


class Handler(FileSystemEventHandler):
    patterns = []

    @staticmethod
    def on_any_event(event):
        if event.is_directory:
            return None
        elif event.event_type == "created":
            tgcli.send_file(
                event.src_path, "File '%s' was created..." % event.src_path
            )
        elif event.event_type == "modified":
            tgcli.send_file(
                event.src_path, "File '%s' was changed..." % event.src_path
            )


def run_onchange(args):
    handler = Handler()

    observer = Observer()
    observer.schedule(handler, args.dirpath, recursive=False)
    observer.start()

    while True:
        time.sleep(1)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dirpath",
        "-d",
        required=True,
        type=str,
        help="Path to directory",
    )

    args = parser.parse_args()

    if not os.path.isdir(args.dirpath):
        print(
            "File '%s' doesn't exist, but we will wait until it appear..."
            % args.dirpath
        )

    run_onchange(args)


if __name__ == "__main__":
    main()
