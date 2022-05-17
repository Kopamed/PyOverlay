from __future__ import annotations

import os
import logging
from datetime import datetime
from mvc import *

MINECRAFT_LOG_PATH = "/home/kopamed/.lunarclient/offline/1.8/logs/latest.log"
API_KEY = "4a35fe0c-371f-4749-8cc7-f7167c163634"


def setup_logging():
    log_name = '/home/kopamed/PyOverlay/logs/{}.log'
    ensure_dir(log_name)
    logging.basicConfig(
        filename=log_name.format(datetime.now().strftime("%d-%m-%Y_%H-%M-%S")),
        filemode='w', format='[%(asctime)s] [%(levelname)s]: %(message)s', level=logging.DEBUG)


if __name__ == "__main__":
    setup_logging()
    e = input("Are you playing on\n[1] Lunar Cliwnt 1.8.9\n[2] Minecraft/Forge\n[3] on something else")
    if "2" in e:
        MINECRAFT_LOG_PATH = "/home/kopamed/.minecraft/logs/latest.log"
    if "3" in e:
        MINECRAFT_LOG_PATH = input("Enter the path to the minecraft log file: ")
    model = Model(MINECRAFT_LOG_PATH)
