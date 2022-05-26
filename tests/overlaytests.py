from __future__ import annotations


try:
    import subprocess
    from abc import ABC, abstractmethod
    from pathlib import Path as p
    import platform
    import os
    import sys
    import unittest


    def install(package):
        os.system(f"{sys.executable} -m pip install {package}")

    def uninstall(package):
        os.system(f"{sys.executable} -m pip uninstall {package}")

    try:
        from colorama import init
    except ModuleNotFoundError:
        install("colorama")
    finally:
        init()

except Exception as e:
    print(e)


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
        return "\.lunarclient\offline\\1.8\logs\latest.log"

    def get_badlion_path(self):
        return "\AppData\Roaming\.minecraft\logs\\blclient\minecraft\latest.log"

    def get_mc_path(self):
        return "\AppData\Roaming\.minecraft\logs\latest.log"


class DarwinPaths(Paths):
    def get_lunar_path(self):
        return "/.lunarclient/offline/1.8/logs/latest.log"

    def get_badlion_path(self):
        return "/Library/Application Support/minecraft/logs/blclient/minecraft/latest.log"

    def get_mc_path(self):
        return "/Library/Application Support/minecraft/logs/latest.log"


def get_paths() -> Paths | None:
    if platform.system() == "Linux":
        return LinuxPaths()
    elif platform.system() == "Darwin":
        return DarwinPaths()
    elif platform.system() == "Windows":
        return WindowsPaths()

    return None


def clear():
    os.system('cls||clear')


base_c = "\033[{0}m"

print()
for i in range(91, 97):
    print(base_c.format(i), "This is some coloured text", i)
print('\033[0m', "Ended colour")

print("Is that text coloured? https://imgur.com/csEehY8 (Colours do NOT have to be exactly the same). Press enter to "
      "continue")
input()

paths = get_paths()
h = str(p.home())
print()
print("Log for default mc does", "" if os.path.exists(h + paths.get_mc_path()) else "not", "exist:", h + paths.get_mc_path())
print("Log for Lunar does", "" if os.path.exists(h + paths.get_lunar_path()) else "not", "exist:", h + paths.get_lunar_path())
print("Log for Badlion does", "" if os.path.exists(h + paths.get_badlion_path()) else "not", "exist:", h + paths.get_badlion_path())

print("Are the statements above true? Press enter to clear the terminal screen")
input()
clear()
print("The screen has just been cleared! There should be nothing on the terminal screen apart from these few lines which werent here before. Is that correct?")
print("If something did not go as expected, please report to the thread in #pyoverlay. Press enter to finish")
input()
