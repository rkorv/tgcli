from distutils.core import setup


setup(
    name="tgcli_toolbox",
    version="1.0",
    description="TGCLI - send messages and files to telegram",
    packages=["."],
    entry_points={
        "console_scripts": [
            "tgcli_monitor_file=tgcli_monitor_file:main",
            "tgcli_monitor_dir=tgcli_monitor_dir:main",
            "tgcli_monitor_tail=tgcli_monitor_tail:main",
        ]
    },
    install_requires=["parsedatetime", "watchdog", "schedule"],
)
