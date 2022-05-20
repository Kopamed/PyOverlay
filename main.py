from __future__ import annotations

import os
import logging
from datetime import datetime
from mvc import *
from pathlib import Path as p
import platform


class Paths(ABC):
    @abstractmethod
    def get_lunar_path(self):
        pass

    @abstractmethod
    def get_badlion_path(self):
        pass

    @abstractmethod
    def get_mc_path(self):
        pass


class LinuxPaths(Paths):
    def get_lunar_path(self):
        return "/.lunarclient/offline/1.8/logs/latest.log"

    def get_badlion_path(self):
        return "/.minecraft/logs/blclient/minecraft/latest.log"

    def get_mc_path(self):
        return "/.minecraft/logs/latest.log"


class WindowsPaths(Paths):
    def get_lunar_path(self):
        return "\AppData\Roaming\lunarclient\offline\\1.8\logs\latest.log"

    def get_badlion_path(self):
        return "\AppData\Roaming\.minecraft\logs\\blclient\minecraft\latest.log"

    def get_mc_path(self):
        return "\AppData\Roaming\.minecraft\logs\latest.log"


class DarwinPaths(Paths):
    def get_lunar_path(self):
        return "/Libraries/Application Support/lunarclient/offline/1.8/logs/latest.log"

    def get_badlion_path(self):
        return "/Libraries/Application Support/minecraft/logs/blclient/minecraft/latest.log"

    def get_mc_path(self):
        return "/Libraries/Application Support/minecraft/logs/latest.log"


def get_paths() -> Paths | None:
    if platform.system() == "Linux":
        return LinuxPaths()
    elif platform.system() == "Darwin":
        return DarwinPaths()
    elif platform.system() == "Windows":
        return WindowsPaths()

    return None


def setup_logging():
    log_name = '/home/kopamed/PyOverlay/logs/{}.log'
    ensure_dir(log_name)
    logging.basicConfig(
        filename=log_name.format(datetime.now().strftime("%d-%m-%Y_%H-%M-%S")),
        filemode='w', format='[%(asctime)s] [%(levelname)s]: %(message)s', level=logging.DEBUG)


if __name__ == "__main__":
    setup_logging()
    mc_log_path = str(p.home())
    paths = get_paths()
    e = input("Are you playing on\n[1] Lunar Client 1.8.9\n[2] Badlion Client\n[3] Minecraft/Forge\n[4] Something "
              "else/I use a custom directory for minecraft\n")
    if "1" in e:
        mc_log_path += paths.get_lunar_path()
    elif "2" in e:
        mc_log_path += paths.get_badlion_path()
    elif "3" in e:
        mc_log_path += paths.get_mc_path()
    else:
        print("Enter the path to your minecraft log file. The default one is", str(p.home()) + paths.get_mc_path())
        mc_log_path = input()

    model = Model(mc_log_path)
