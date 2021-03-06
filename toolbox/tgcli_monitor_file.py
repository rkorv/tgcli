import argparse
import os
import time

import schedule
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

import tgcli

from utils import str_to_interval


def _send_file(filepath, text):
    with open(filepath, "rb") as f:
        return tgcli.send(
            text, filename=os.path.basename(filepath), data=f.read()
        )


def run_interval(args):
    interval = str_to_interval(args.interval)
    main_scheduler = schedule.Scheduler()
    main_scheduler.every(interval).seconds.do(
        _send_file,
        filepath=args.filepath,
        text="File '%s' on interval '%s'" % (args.filepath, args.interval),
    )
    main_scheduler.run_all()

    while True:
        main_scheduler.run_pending()
        time.sleep(0.1)


class Handler(PatternMatchingEventHandler):
    patterns = []

    @staticmethod
    def on_any_event(event):
        if event.is_directory:
            return None
        elif event.event_type == "created" or event.event_type == "modified":
            _send_file(
                event.src_path, "File '%s' was changed..." % event.src_path
            )


def run_onchange(args):
    handler = Handler()
    full_path = os.path.abspath(args.filepath)
    handler.patterns.append(os.path.realpath(full_path))

    observer = Observer()
    observer.schedule(handler, os.path.dirname(full_path), recursive=False)
    observer.start()

    while True:
        time.sleep(1)


def main():
    description_str = """
Send file on interval.

Examples:
    $ tgcli_monitor_file ./my_file.txt 10m

# On change:
    $ tgcli_monitor_file ./my_file.txt

"""
    parser = argparse.ArgumentParser(
        description=description_str,
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "filepath",
        type=str,
        help="Path to file",
    )
    parser.add_argument(
        "interval",
        nargs="?",
        default="onchange",
        type=str,
        help="""You can use 'onchange' here or interval in human format.
        ex. '10m', '1h 30m', '1m 30s' (Default: 'onchange')""",
    )

    args = parser.parse_args()

    if not os.path.isfile(args.filepath):
        print(
            "File '%s' doesn't exist, but we will wait until it appear..."
            % args.filepath
        )

    if args.interval == "onchange":
        run_onchange(args)
    else:
        run_interval(args)


if __name__ == "__main__":
    main()
