import time
import statistics
import logging
import os
import io
import argparse

from utils import str_to_interval

import psutil
import GPUtil
import schedule
import matplotlib.pyplot as plt
import matplotlib

import tgcli

matplotlib.pyplot.switch_backend("Agg")


class SystemMonitor:
    KEEP_LAST_MINUTES = 60
    UPDATE_GPU_DATA_INTERVAL = 0.25

    def __init__(self):
        self._hist = {"mem": [], "gpu_mem": [], "cpu": [], "gpu": []}
        self._current_gpu_hist = {"gpu": [], "gpu_mem": []}

        self._has_gpu = bool(GPUtil.getGPUs())

        self._scheduler = schedule.Scheduler()
        self._scheduler.every(1).minutes.do(self.update_minute)
        if self._has_gpu:
            self._scheduler.every(self.UPDATE_DATA_INTERVAL).seconds.do(
                self.update_gpu_data
            )
            self._gpu_mem_total = 0

        # Disable matplotlib spam...
        logging.getLogger("matplotlib").setLevel(logging.WARNING)

    def update_minute(self):
        curr_time = time.time()

        def get_usage(metric_name):
            if metric_name == "cpu":
                cpu_usage = psutil.getloadavg()[0] / os.cpu_count() * 100
                return cpu_usage
            if metric_name == "mem":
                return psutil.virtual_memory().used

            if self._has_gpu and (
                metric_name == "gpu" or metric_name == "gpu_mem"
            ):
                return statistics.mean(self._current_gpu_hist[metric_name])

            return None

        if len(self._hist["mem"]) >= self.KEEP_LAST_MINUTES:
            for metric_name in self._hist.keys():
                self._hist[metric_name] = self._hist[metric_name][
                    : self.KEEP_LAST_MINUTES - 1
                ]

        for metric_name in self._hist.keys():
            self._hist[metric_name].append([curr_time, get_usage(metric_name)])

        if self._has_gpu:
            for metric_name in self._current_gpu_hist.keys():
                self._current_gpu_hist[metric_name] = []

    def update_gpu_data(self):
        if self._has_gpu:
            gpus = GPUtil.getGPUs()
            mem, load, mem_total = 0, 0, 0
            for gpu in gpus:
                mem += gpu.memoryUsed
                load += gpu.load
                mem_total += gpu.memoryTotal

            self._gpu_mem_total = mem_total
            self._current_gpu_hist["gpu"].append(load / len(gpus) * 100)
            self._current_gpu_hist["mem"].append(mem)

    def get_scheduler(self):
        return self._scheduler

    def _format_hist(self, hist):
        return [
            # [time.strftime("%H:%M:%S", time.gmtime(t)), float(v)]
            [time.strftime("%H:%M:%S", time.gmtime(t)), float(v)]
            for [t, v] in hist
        ]

    def get_plot(self):
        def draw(cpu, mem, gpu=None, gpu_mem=None):
            cpu = self._format_hist(cpu)
            mem = self._format_hist(mem)

            if gpu:
                gpu = self._format_hist(gpu)
            if gpu_mem:
                gpu_mem = self._format_hist(gpu_mem)

            charts_count = 2 if gpu_mem is None else 3

            fig, axs = plt.subplots(charts_count, 1)

            fig.subplots_adjust(hspace=0.5)
            fig.set_figheight(10)
            fig.set_figwidth(15)

            fig.patch.set_facecolor("white")

            for ax in axs:
                ax.grid(True)
                plt.sca(ax)
                step = min(5, len(cpu))
                plt.xticks(range(0, len(cpu), step), rotation=45)

            axs[0].plot(*zip(*cpu), label="CPU", color="blue")
            if gpu:
                axs[0].plot(*zip(*gpu), label="GPU", color="red")
            axs[0].legend()
            axs[0].set_ylim(0, 100)
            axs[0].yaxis.set_major_formatter("{x:1.0f}%")
            axs[0].set_title("CPU/GPU usage")

            axs[1].set_ylim(
                0, psutil.virtual_memory().total / 1024 / 1024 / 1024 + 0.5
            )
            mem = [[t, v / 1024 / 1024 / 1024] for (t, v) in mem]
            axs[1].plot(*zip(*mem), color="orange")
            axs[1].yaxis.set_major_formatter("{x:1.2f} Gb")
            axs[1].set_title("Sys Memory")

            if gpu_mem:
                axs[2].set_ylim(0, self._gpu_mem_total + 0.5)
                gpu_mem = [[t, v / 1024 / 1024 / 1024] for (t, v) in gpu_mem]
                axs[2].plot(*zip(*gpu_mem), color="green")
                axs[2].yaxis.set_major_formatter("{x:1.2f} Gb")
                axs[2].set_title("GPU Memory")

        if len(self._hist["cpu"]) <= 1:
            return None

        if self._has_gpu:
            draw(
                self._hist["cpu"],
                self._hist["mem"],
                self._hist["gpu"],
                self._hist["gpu_mem"],
            )
        else:
            draw(self._hist["cpu"], self._hist["mem"])

        buf = io.BytesIO()
        plt.savefig(buf, format="png")
        buf.seek(0)

        plt.close()
        return buf


def publish_system(bytesio):
    if bytesio is None:
        return

    tgcli.send_bytes("chart.png", bytesio.read())
    bytesio.close()


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "interval",
        nargs="?",
        default="30m",
        type=str,
        help="Interval in human format. ex. '10m', '1h 30m', '1m 30s'",
    )

    args = parser.parse_args()

    interval = str_to_interval(args.interval)
    sm = SystemMonitor()
    sm_scheduler = sm.get_scheduler()

    main_scheduler = schedule.Scheduler()
    main_scheduler.every(interval).seconds.do(
        lambda: publish_system(sm.get_plot())
    )

    while True:
        sm_scheduler.run_pending()
        main_scheduler.run_pending()
        time.sleep(0.1)


if __name__ == "__main__":
    main()
