import argparse
import subprocess
import os
import time

import schedule

import tgcli

from utils import str_to_interval


def _publish_tail(filepath, lines):
    if not os.path.isfile(filepath):
        print("[ERROR] no such file '%s'" % filepath)
        return

    with subprocess.Popen(
        ["tail", "-n", str(lines), filepath],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as f:
        text = ""
        line = f.stdout.read()
        if line:
            text += line.decode("utf-8") + "\n"

    tgcli.send(
        text="Tail for file '```%s```':\n---\n```\n%s\n```" % (filepath, text),
        markdown=True,
    )


def main():
    description_str = """
Send tail of file.

Examples:
    $ tgcli_monitor_tail ./logs.txt 10m -l 30

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
        default="30m",
        type=str,
        help="Interval in human format. ex. '10m', '1h 30m', '1m 30s'",
    )
    parser.add_argument(
        "--lines",
        "-l",
        default=30,
        type=int,
        help="Lines count",
    )

    args = parser.parse_args()

    interval = str_to_interval(args.interval)
    if os.path.isdir(args.filepath):
        print("[ERROR] '%s' This is a directory!" % args.filepath)
        return

    main_scheduler = schedule.Scheduler()
    main_scheduler.every(interval).seconds.do(
        _publish_tail, filepath=args.filepath, lines=args.lines
    )
    main_scheduler.run_all()

    while True:
        main_scheduler.run_pending()
        time.sleep(0.1)


if __name__ == "__main__":
    main()
