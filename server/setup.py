from distutils.core import setup


setup(
    name="tgcli_server",
    version="1.0",
    description="TGCLI server - receive messages from tgcli and forward to telegram bot.",
    entry_points={"console_scripts": ["tgcli_server=tgcli_server:main"]},
    packages=["."],
    install_requires=[
        "schedule",
        "python-telegram-bot",
        "easydict",
        "parsedatetime",
        "fastapi",
        "uvicorn",
    ],
)
