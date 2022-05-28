from __future__ import annotations

# VERSION variable MUST be on the 4th line always
VERSION = 1.24

try:  # installing and importing all the needed packages
    import math
    import json
    import os
    import time
    from abc import ABC, abstractmethod
    from threading import Thread
    from typing import List, Dict
    import subprocess
    from abc import ABC, abstractmethod
    import platform
    import sys
    import logging


    def install(package):
        os.system(f"{sys.executable} -m pip install {package}")


    def uninstall(package):
        os.system(f"{sys.executable} -m pip uninstall {package}")


    try:
        from colorama import init
    except ModuleNotFoundError:
        install("colorama")
        from colorama import init
    finally:
        init()

    try:
        import requests
    except ModuleNotFoundError:
        install("requests")
        import requests

    try:
        from pathlib import Path as Pathlib
    except ModuleNotFoundError:
        install("pathlib")
        from pathlib import Path as Pathlib

    try:
        from datetime import datetime
    except ModuleNotFoundError:
        install("datetime")
        from datetime import datetime

    try:
        import uuid
    except ModuleNotFoundError:
        install("uuid")
        import uuid

    try:
        import hashlib
    except ModuleNotFoundError:
        install("hashlib")
        import hashlib

except Exception as e:
    print(e)
    print("The overlay will attempt to run but is more likely to encounter issues")

# Todo: Remove error messages with ctrlc
# Todo: sort the public methods before the private ones for better readability
# Todo: add this config system I just take the highest stars, fkdr, bblr, and wlr and winstreak, make that 100% and then figure out where everyone else sits based on that scale
# Todo: add an option to change this
# Todo: Move most important classes to top
# Todo: display different top message depending on client

MOJANG_API_PLAYER_LIMIT = 10


# Misc standalone classes which make the code more readable ========================================================= #
class Colours:
    PINK = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    GOLD = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    ENDC = '\033[0m'

    @staticmethod
    def get_stat_colour(index: int):
        if index < 1000:
            return ""
        elif index < 3000:
            return "\033[33m"
        elif index < 7500:
            return "\033[93m"
        elif index < 15000:
            return "\033[91m"
        elif index < 30000:
            return "\033[95m"
        elif index < 100000:
            return "\033[94m"
        elif index < 500000:
            return "\033[96m"

        return "\033[92m"


class Client:
    Lunar: str = "Make sure you have Auto Who enabled in Hypixel Mods"
    Badlion: str = "Make sure you have Auto Who enabled"
    Minecraft: str = "You need to have either an Auto Who mod installed or run /who everytime you join a new queue"


class APIStatus:
    UNKNOWN = Colours.BOLD + "Unknown" + Colours.ENDC
    REACHABLE = Colours.BOLD + Colours.GREEN + "Reachable" + Colours.ENDC
    UNREACHABLE = Colours.BOLD + Colours.RED + "Unreachable" + Colours.ENDC


class ConfigManager:
    def __init__(self):
        self.config_folder = str(Pathlib.home()) + os.sep + "PyOverlay"
        self.config_path = self.config_folder + os.sep + "config"

    def save_api_key(self, api_key):
        self._assure_config_exists()
        with open(self.config_path, "w") as f_:
            f_.write(api_key)

    def get_api_key(self):
        self._assure_config_exists()
        if not os.path.isfile(self.config_path):
            open(self.config_path, "w").close()
            return None
        with open(self.config_path, "r") as f_:
            data = f_.read().strip("\n")
            if data != "":
                return data
        return None

    def _assure_config_exists(self):
        if not os.path.exists(self.config_folder):
            os.makedirs(self.config_folder)

        if not os.path.isfile(self.config_path):
            whatver = open(self.config_path, "w")
            whatver.write("")
            whatver.close()


class Model:
    """
    Core of the program. This class has the main logic and methods which get called by the controller when a new line
    is added to the log file
    """

    def __init__(self, file_path: str, client_: str, api_key: str = None):
        self.api_key = api_key  # hypixel api key
        self.client: str = client_

        self.hypixel_api_reachable: str = APIStatus.UNKNOWN
        self.mojang_api_reachable: str = APIStatus.UNKNOWN

        self._players_joined = 0
        self._players_left = 0

        self.players: List[Player] = []  # players in current lobby
        self._cache: List[Player] = []  # cache storing all the known player's data to reduce the amount of
        # requests sent to hypixel and mojang
        self._request_threads: List[Thread] = []

        self.config_manager = ConfigManager()
        self._view = View(self)
        self._controller = Controller(self, file_path)
        self._controller.run()

        if self.api_key is None:
            if self.config_manager.get_api_key() is not None:
                self.api_key = self.config_manager.get_api_key()

        if self.api_key is not None:
            if not self._valid_key(self.api_key):
                self.api_key = None

        self.update_view()

    def update_view(self):
        self.players.sort(key=lambda x: x.index, reverse=True)  # Todo: add an option to change this
        if self.api_key is not None:
            self._view.stat_table()
        else:
            self._view.no_api_key()

    def is_player_in_cache(self, name: str) -> Player | None:
        for player in self._cache:
            if player.in_game_name == name:
                return player
        return None

    def add_player(self, name: str) -> None:
        if self.is_player_in_cache(name) is not None:
            self._add_player(self.is_player_in_cache(name))
        else:
            self._add_player(Player(name, self))
        self.update_view()

    def remove_player(self, name: str):
        self._players_left += 1
        for player in self.players:
            if player.in_game_name == name:
                self.players.remove(player)
        self.update_view()

    def joined_new_queue(self, joined_players: List[str]):
        self._reset_queue()

        for name in joined_players:
            player = self.is_player_in_cache(name)
            if player is not None:
                logging.debug(name + " was in cache")
                self.add_player(name)
                joined_players.remove(name)

        split_up: List[List[str]] = []
        # since mojang can only accept lists with up to 10 usernames, we have to split the list up into multiple lists
        for index, username in enumerate(joined_players):
            if index % MOJANG_API_PLAYER_LIMIT == 0:
                split_up.append([])

            split_up[-1].append(username)

        for section in split_up:
            t = Thread(target=self._add_listed_players_to_queue, args=(section,))
            self._request_threads.append(t)
            logging.debug("Started mass stat request: " + str(section))
            t.start()

    def left_queue(self):
        self._reset_queue()

    def broken_api_key(self):
        self.api_key = None
        self.update_view()

    def new_api_key(self, api_key):
        self.api_key = api_key
        self.config_manager.save_api_key(api_key)
        self.update_view()

    def player_updated(self, player):
        if player in self.players:
            self.update_view()

    def is_api_key_working(self):
        return self.api_key is not None

    def set_hypixel_api_reachable(self, is_it: bool):
        if is_it:
            self.hypixel_api_reachable = APIStatus.REACHABLE
        else:
            self.hypixel_api_reachable = APIStatus.UNREACHABLE

    def set_mojang_api_reachable(self, is_it: bool):
        if is_it:
            self.mojang_api_reachable = APIStatus.REACHABLE
        else:
            self.mojang_api_reachable = APIStatus.UNREACHABLE

    def players_cached(self) -> int:
        return len(self._cache)

    def get_queue_liquidity(self):
        if self._players_joined == 0:
            return self._players_left
        return round(self._players_left / self._players_joined, 2)

    def get_average_index(self):
        if len(self.players) == 0:
            return 0
        index = 0
        for player in self.players:
            index += player.index ** 2

        index = round(math.sqrt(index / len(self.players)))
        return index

    def stop(self):
        self._controller.stop()
        for player in self.players:
            player.data_download_thread.join(0.01)
        for thread in self._request_threads:
            thread.join(0.01)
        clear_screen()
        print("saved")

    def _add_player(self, player: Player):
        self._players_joined += 1
        if not self.is_player_in_cache(player.in_game_name):
            self._cache.append(player)
        self.players.append(player)

    def _valid_key(self, api_key):
        while True:
            time.sleep(0.01)
            c = requests.get("https://api.hypixel.net/key?key=" + api_key)
            if c.status_code == 429:
                continue
            self.set_hypixel_api_reachable(True)
            return c != "" and "Invalid" not in c

    def _add_listed_players_to_queue(self, split_up: List[str]):
        headers = {"Content-Type": "application/json"}
        while True:
            r = requests.post("https://api.mojang.com/profiles/minecraft", headers=headers, json=split_up)
            self.set_mojang_api_reachable(True)
            if r.status_code == 200:
                data = json.loads(r.text)
                for player_data in data:
                    player_name_returned: str = player_data["name"]
                    player_uuid: str = player_data["id"]
                    for player_name in split_up:
                        if player_name.lower() == player_name_returned.lower():
                            self._add_player(Player(player_name, self, player_uuid))
                            split_up.remove(player_name)
                            break

                if len(split_up) != 0:
                    for left_over_name in split_up:
                        self._add_player(Player(left_over_name, self, nicked=True))
                break
            else:  # codes are 429 (too many requests) amd 500 (request timed out)
                self.set_mojang_api_reachable(False)
                time.sleep(8)  # arbitrary number of seconds to sleep. Pulled it out of my ass

    def _reset_queue(self):
        self._players_joined = 0
        self._players_left = 0
        self.players.clear()
        self.update_view()


class Player:
    rank_colours: dict[str, str] = {"MVP_PLUS": Colours.CYAN, "MVP": Colours.CYAN, "SUPERSTAR": Colours.GOLD,
                                    "VIP": Colours.GREEN,
                                    "VIP_PLUS": Colours.GREEN, "NON": ""}

    def __init__(self, ign: str, model_: Model, uuid_: str = None, nicked: bool = False):
        self._model = model_

        self.in_game_name = ign
        self.uuid = uuid_
        self.json = {}
        self.data_downloaded = False

        self.nicked: bool = nicked
        self.rank = "NON"
        self.index: int = 0
        self.party: bool = False
        self.stars: int = 0
        self.winstreak: int = 0
        self.fkdr: float = 0
        self.wlr: float = 0
        self.bblr: float = 0
        self.wins: int = 0
        self.finals: int = 0

        self.data_download_thread = Thread(target=self._populate_player_data)
        self.data_download_thread.start()

    def to_string(self, form: str) -> str:
        return form.format(
            self.rank_colours[self.rank], self.in_game_name,
            self._get_tag_colour(), self._get_tag(),
            self.stars,
            self.winstreak,
            self.fkdr,
            self.wlr,
            self.bblr,
            self.wins,
            self.finals,
            stat_colour=Colours.get_stat_colour(self.index)
        )

    def _populate_player_data(self):
        """
        Method which requests data from the hypixel api and fuck
        :param self: Player whose  data you want to populate
        :return:
        """
        while not self.data_downloaded:
            if self.nicked:
                return

            if self.uuid is None:
                self._download_uuid()

            while True:
                while not self._model.is_api_key_working():
                    time.sleep(0.5)
                time.sleep(0.01)  # reduces the chances of Connection Error Conection Aborted error
                # https://stackoverflow.com/questions/52051989/requests-exceptions-connectionerror-connection-aborted
                # -connectionreseterro
                r = requests.get(f"https://api.hypixel.net/player?key={self._model.api_key}&uuid={self.uuid}")
                self._model.set_hypixel_api_reachable(True)
                if r.status_code == 403:  # code returned when your api key is incorrect
                    self._model.broken_api_key()
                elif r.status_code == 429:  # rate limit code
                    self._model.set_hypixel_api_reachable(False)
                    time.sleep(2)  # arbitrary number of seconds to sleep. Pulled it out of my ass
                elif r.status_code == 200:
                    raw_data = json.loads(r.text)

                    if not raw_data["success"]:
                        continue  # back to the while loop if hypickle says that success was false

                    self.json = raw_data["player"]
                    if self.json is None:  # json is null when the player does not exist
                        self.nicked = True
                    break

            self.data_downloaded = True

            if self.data_downloaded and not self.nicked:  # ensuring we have the player's data
                bw_stats = self.json["stats"]["Bedwars"]
                achievements = self.json["achievements"]

                try:
                    self.rank = self.json["monthlyPackageRank"]
                except KeyError:
                    try:
                        self.rank = self.json["newPackageRank"]
                    except KeyError:
                        pass

                if str(self.rank) == "NONE":
                    self.rank = "NON"

                try:
                    self.party = self.json["channel"] == "PARTY"
                except KeyError:
                    self.party = False

                try:
                    self.finals = bw_stats["final_kills_bedwars"]
                except KeyError:
                    pass

                try:
                    self.wins = bw_stats["wins_bedwars"]
                except KeyError:
                    pass

                try:
                    self.fkdr = self.finals if bw_stats["final_deaths_bedwars"] == 0 \
                        else round(self.finals / bw_stats["final_deaths_bedwars"], 2)  # je mange des enfants
                except KeyError:
                    pass

                try:
                    self.wlr = self.wins if bw_stats["losses_bedwars"] == 0 \
                        else round(self.wins / bw_stats["losses_bedwars"], 2)
                except KeyError:
                    pass

                try:
                    self.bblr = bw_stats["beds_broken_bedwars"] if bw_stats["beds_lost_bedwars"] == 0 \
                        else round(bw_stats["beds_broken_bedwars"] / bw_stats["beds_lost_bedwars"], 2)
                except KeyError:
                    pass

                try:
                    self.winstreak = bw_stats["winstreak"]
                except KeyError:
                    pass

                try:
                    self.stars = achievements["bedwars_level"]
                except KeyError:
                    pass

                self.index = self.stars * self.fkdr ** 2

        self._model.player_updated(self)

    def _download_uuid(self):
        """
        Fetches the uuid for the player from the mojang api
        :return:
        """
        while True:
            r = requests.get("https://api.mojang.com/users/profiles/minecraft/" + self.in_game_name)
            self._model.set_mojang_api_reachable(True)
            if r.status_code == 200:
                try:
                    self.uuid = json.loads(r.text)["id"]
                    break
                except KeyError:
                    time.sleep(1)
            elif r.status_code == 204:  # player most likely does not exist
                self.nicked = True
                break
            else:  # codes are 429 (too many requests) amd 500 (request timed out)
                self._model.set_mojang_api_reachable(False)
                time.sleep(8)  # arbitrary number of seconds to sleep. Pulled it out of my ass

    def _get_tag_colour(self):
        if self.uuid == "54968fd589a94732b02dad8d9162175f":  # Kopamed's uuid
            return Colours.CYAN + Colours.BOLD
        elif self.nicked:
            return Colours.RED
        elif self.party:
            return Colours.BLUE

        return ""

    def _get_tag(self):
        if self.uuid == "54968fd589a94732b02dad8d9162175f":  # Kopamed's uuid
            return "DEV"
        elif self.nicked:
            return "NICK"
        elif self.party:
            return "PARTY"

        return "-" * 5


def fix_line(line: str) -> str:
    """
    Removes clutter from a minecraft log line
    :param line: The line you wish to clean from clutter
    :return: cleaned line
    """
    return line.split("] ")[-1].strip("\n")


class Controller:
    """
    Class to make setting up the file listener and adding observers to it a 1-liner
    """

    def __init__(self, model_: Model, file_path: str):
        self._file_listener = FileListener(file_path)
        self._file_listener.attach(JoinObserver(model_))
        self._file_listener.attach(LeaveObserver(model_))
        self._file_listener.attach(ApiKeyObserver(model_))
        self._file_listener.attach(LobbyLeaveObserver(model_))
        self._file_listener_thread = Thread(target=self._file_listener.listen)

    def run(self):
        self._file_listener_thread.start()

    def stop(self):
        self._file_listener_thread.join(0.1)


class Observable(ABC):
    """
    Interface for Observers to observe
    """

    @abstractmethod
    def attach(self, observer: Observer) -> None:
        """
        :param observer: Observer which will be notified upon a change
        :return: None
        """
        pass

    @abstractmethod
    def detach(self, observer: Observer) -> None:
        """
        :param observer: Observer you wish to stop listening
        :return: None
        """
        pass

    @abstractmethod
    def notify(self) -> None:
        """
        Alerts all the observers attached
        :return:
        """
        pass


class FileListener(Observable):
    """
    A class which can be listened to with observers, notifying observers of any new lines added to a file
    """

    _observers: List[Observer] = []

    def __init__(self, filepath: str, delay: float = 0.1):
        self.filepath: str = filepath
        self.delay = delay
        with open(self.filepath, "r") as f_:
            # all the lines below this line will get passed to the observers
            self._read_from_index: int = len(f_.readlines())
        self.new_lines: List[str] = []  # contains all the new lines added to the file since last read

    def listen(self) -> None:
        while True:
            self.new_lines = []
            with open(self.filepath, "r") as f_:
                for line in f_.readlines()[self._read_from_index:]:
                    line = fix_line(line)
                    self.new_lines.append(line)
                    # logging.debug("Added " + line + " to new lines")
                    self._read_from_index += 1

            if len(self.new_lines) != 0:
                self.notify()

            time.sleep(self.delay)

    def attach(self, observer: Observer) -> None:
        self._observers.append(observer)
        # logging.debug(f"Attached {observer} to {self}")

    def detach(self, observer: Observer) -> None:
        self._observers.remove(observer)
        # logging.debug(f"Removed {observer} from {self}")

    def notify(self) -> None:
        for observer in self._observers:
            observer.update(self)
        # logging.debug(f"Update {len(self._observers)} listening to {self}")


def clear_screen(fnc=None):
    def wrapper(*args):
        os.system('cls' if os.name == 'nt' else 'clear')
        ret = fnc(*args)
        return ret

    return wrapper


class View:
    def __init__(self, model_: Model):
        self._model = model_

    def runtime_stats(self):
        print(Colours.CYAN + Colours.BOLD + "PyOverlay" + Colours.BLUE + " v" + str(VERSION) + Colours.ENDC
              + " | " + Colours.GOLD + self._model.client + Colours.ENDC)
        print("Players cached: " + Colours.BOLD + str(self._model.players_cached()) + Colours.ENDC)
        print("Mojang: " + str(self._model.mojang_api_reachable))
        print("Hypixel: " + str(self._model.hypixel_api_reachable))
        print("Hypixel API key: ", end="")
        if self._model.api_key is None:
            print(Colours.BOLD + Colours.RED + "Not found!" + Colours.ENDC)
        else:
            print(
                Colours.CYAN + self._model.api_key[:int(len(self._model.api_key) / 2)] +
                ("*" * int(len(self._model.api_key) / 2)) + Colours.ENDC
            )

    @clear_screen
    def no_api_key(self):
        self.runtime_stats()
        print(Colours.RED + "No API key found! Run "
              + Colours.ENDC + Colours.BOLD + "/api new"
              + Colours.RED + " on hypixel to generate a key"
              + Colours.ENDC)

    @clear_screen
    def stat_table(self):
        self.runtime_stats()

        if len(self._model.players) > 1:
            index = self._model.get_average_index()
            print("Lobby liquidity: {:<4} | Lobby index: {}".format(
                self._model.get_queue_liquidity(),
                Colours.get_stat_colour(index) + str(index) + Colours.ENDC)
            )

        form = "{:^16} │ {:^5} │ {:^4} │ {:^4} │ {:^6} │ {:^6} │ {:^6} │ {:^5} │ {:^5}"
        header = form.format("Name", "Tag", "Star", "WS", "FKDR", "WLR", "BBLR", "Wins", "Finals")
        print(header)
        self._sep_line(header)

        form = "{}{:^16}{end} │ {}{:^5}{end} │ {stat_colour}{:^4}{end} │ {stat_colour}{:^4}{end} │ {stat_colour}{" \
               ":^6}{end} │ {stat_colour}{:^6}{end} │ {stat_colour}{:^6}{end} │ {stat_colour}{:^5}{end} │ {" \
               "stat_colour}{:^5}{end}".replace("{end}", Colours.ENDC)

        if len(self._model.players) == 0:
            print("{:^l}".replace("l", str(len(header))).format(
                Colours.GOLD + Colours.BOLD + "No players found" + Colours.ENDC))
        else:
            for player in self._model.players:
                print(player.to_string(form))

    @staticmethod
    def _sep_line(header):
        split_up_header = header.split("│")
        for index, content in enumerate(split_up_header):
            split_up_header[index] = "─" * len(content)
        print("┼".join(i for i in split_up_header))


class Observer(ABC):
    """
    The Observer interface declares the update method, used by subjects.
    """

    @abstractmethod
    def update(self, observable: Observable) -> None:
        """
        Receive update from subject.
        """
        pass


class FileObserver(Observer):
    """
    Extends the observable class to allow FileListeners to pass through
    """

    def __init__(self, model_: Model):
        self._model = model_

    @abstractmethod
    def update(self, observable: FileListener) -> None:
        pass


class JoinObserver(FileObserver):
    """
    Will read through the lines to determine if any new players have joined
    """

    def __init__(self, model_: Model):
        super().__init__(model_)

    def update(self, observable: FileListener) -> None:
        for line in observable.new_lines:
            if line.lower().startswith("online: "):
                logging.info("Joined new queue!")
                self._model.joined_new_queue(line.strip("ONLINE: ").split(", "))
            elif " has joined" in line.lower():
                name = line.split(" ")[0]
                logging.info(name + "joined the queue!")
                self._model.add_player(name)


class LeaveObserver(FileObserver):
    """
    Will read through the lines to determine if any players have left
    """

    def __init__(self, model_: Model):
        super().__init__(model_)

    def update(self, observable: FileListener) -> None:
        for line in observable.new_lines:
            if " has quit!" in line:
                name = line.split(" ")[0]
                logging.info(name + " has left the queue")
                self._model.remove_player(name)


class LobbyLeaveObserver(FileObserver):
    """
    Will read through the lines to determine if player has left the queuing lobby
    """

    def __init__(self, model_: Model):
        super().__init__(model_)

    def update(self, observable: FileListener) -> None:
        for line in observable.new_lines:
            if "joined the lobby!" in line:  # to change
                logging.info("Left the queue!")
                self._model.left_queue()


class ApiKeyObserver(FileObserver):
    """
    Will read through the lines to determine if the game has started
    """

    def __init__(self, model_: Model):
        super().__init__(model_)

    def update(self, observable: FileListener) -> None:
        for line in observable.new_lines:
            if line.startswith("Your new API key is"):  # to change
                api_key = line.split(" ")[-1]
                logging.info("New API key found: " + api_key)
                self._model.new_api_key(api_key)


# Classes and functions required for initialization ================================================================== #
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


def setup_logging():
    log_name = str(Pathlib.home()) + '/PyOverlay/logs/{}.log'
    ensure_dir(log_name)
    logging.basicConfig(
        filename=log_name.format(datetime.now().strftime("%d-%m-%Y_%H-%M-%S")),
        filemode='w', format='[%(asctime)s] [%(levelname)s]: %(message)s', level=logging.DEBUG)


def ensure_dir(file_path):
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory)


def register_launch():
    """
       Sends a get request to the server so I can keep track of how many times PyOverlay has been run
       :return:
       """
    mac_addr_unhashed = ':'.join(['{:02x}'.format((uuid.getnode() >> ele) & 0xff)
                                  for ele in range(0, 8 * 6, 8)][::-1])
    mac_addr_hashed = hashlib.sha512(str(mac_addr_unhashed).encode("utf-8")).hexdigest()
    while True:
        try:
            paths_request = requests.get("https://launchtracker.raventeam.repl.co/paths")
            if paths_request.status_code != 200:
                continue

            target_to_post = ""

            for line in paths_request.text.split("\n"):
                if line.startswith("PyOverlay"):
                    target_to_post = line.split(" ~ ")[-1]

            r = requests.post("https://launchtracker.raventeam.repl.co" + target_to_post,
                              json={"hashedMacAddr": mac_addr_hashed, "version": VERSION})
            if r.status_code == 200:
                break
        except Exception as error:
            logging.error(error)


if __name__ == "__main__":
    launch_register_thread = Thread(target=register_launch)
    setup_logging()

    print("\033[96m", end="")
    print("""    ____        ____                  __           
   / __ \__  __/ __ \_   _____  _____/ /___ ___  __
  / /_/ / / / / / / / | / / _ \/ ___/ / __ `/ / / /
 / ____/ /_/ / /_/ /| |/ /  __/ /  / / /_/ / /_/ / 
/_/    \__, /\____/ |___/\___/_/  /_/\__,_/\__, /  
      /____/                              /____/""" + Colours.BLUE + " v" + str(VERSION) + "\033[0m")

    latest_py_overlay = requests.get(
        "https://raw.githubusercontent.com/Kopamed/PyOverlay/main/PyOverlay.py")
    if latest_py_overlay.status_code == 200:
        latest_py_overlay = latest_py_overlay.text
        latest_version = float(latest_py_overlay.split("\n")[3].split(" = ")[-1])

        if latest_version > VERSION:
            print(
                f"An update is available. Would you like to update PyOverlay from "
                f"version {VERSION} to  {latest_version}? [Y/n]")

            if "n" not in input().lower():
                with open("PyOverlay.py", "w") as f:
                    f.write(latest_py_overlay)
                print("Update complete! Please re-run PyOverlay")
                sys.exit(0)

    mc_log_path = str(Pathlib.home())
    client = ""
    paths = get_paths()

    clients = []
    if os.path.exists(mc_log_path + paths.get_mc_path()):
        clients.append("Minecraft/Forge")
    if os.path.exists(mc_log_path + paths.get_lunar_path()):
        clients.append("Lunar Client")
    if os.path.exists(mc_log_path + paths.get_badlion_path()):
        clients.append("Badlion Client")

    launch_register_thread.start()
    while True:
        mc_log_path = str(Pathlib.home())
        print("The following clients have been found on your computer:",
              "None" if len(clients) == 0 else ", ".join(i for i in clients))
        e = input("Are you playing on\n[1] Lunar Client 1.8.9\n[2] Badlion Client\n[3] Minecraft/Forge\n[4] Something "
                  "else/I use a custom directory for minecraft\n")
        if "1" in e:
            mc_log_path += paths.get_lunar_path()
            client = Client.Lunar
        elif "2" in e:
            mc_log_path += paths.get_badlion_path()
            client = Client.Badlion
        elif "3" in e:
            mc_log_path += paths.get_mc_path()
            client = Client.Minecraft
        else:
            print("Enter the path to your minecraft log file. The default one is",
                  str(Pathlib.home()) + paths.get_mc_path())
            client = Client.Minecraft
            mc_log_path = input()

        if os.path.exists(mc_log_path):
            break
        else:
            print(f"The log file {mc_log_path} was not found!")

    model = Model(mc_log_path, client)
    launch_register_thread.join()
