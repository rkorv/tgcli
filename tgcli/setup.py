from distutils.core import setup


setup(
    name="tgcli",
    version="1.0",
    description="TGCLI - send messages and files to telegram",
    py_modules=["tgcli"],
    entry_points={"console_scripts": ["tgcli=tgcli:main"]},
    install_requires=["requests"],
)
