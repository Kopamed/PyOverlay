from __future__ import annotations

import json
import os

import requests
import logging
import time
from abc import ABC, abstractmethod
from threading import Thread
from typing import List, Dict

# Todo: fix config manager bullshit and make this work on all OSs
# Todo: Remove error messages with ctrlc
# Todo: detect path to log or ask lamooooooooooo
# Todo: sort the public methods before the private ones for better readability
# Todo: add this config system I just take the highest stars, fkdr, bblr, and wlr and winstreak, make that 100% and then figure out where everyone else sits based on that scale
# Todo: add an option to change this

# Changed:
# Sort by fkdr
# Added sleep before hypixel request to reduce chances of an error
# Added validation to API Key verification

MOJANG_API_PLAYER_LIMIT = 10


class Colors:
    PINK = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    GOLD = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class APIStatus:
    UNKNOWN = Colors.BOLD + "Unknown" + Colors.ENDC
    REACHABLE = Colors.BOLD + Colors.GREEN + "Reachable" + Colors.ENDC
    UNREACHABLE = Colors.BOLD + Colors.RED + "Unreachable" + Colors.ENDC


def ensure_dir(file_path):
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory)


class ConfigManager:  # fix this bullshit
    def __init__(self, config_path):
        self.config_path = config_path

    def save_api_key(self, api_key):
        with open(self.config_path, "w") as f:
            f.write(api_key)

    def get_api_key(self):
        if not os.path.isfile(self.config_path):
            open(self.config_path, "w").close()
        with open(self.config_path, "r") as f:
            for line in f.readlines():
                return line.strip("\n")
        return None

    def save_config(self):
        pass


class Model:
    """
    Core of the program. This class has the main logic and methods which get called by the controller when a new line is added to the log file
    """

    def __init__(self, file_path: str, api_key: str = None):
        self.api_key = api_key  # hypixel api key

        self.hypixel_api_reachable: str = APIStatus.UNKNOWN
        self.mojang_api_reachable: str = APIStatus.UNKNOWN

        self.players: List[Player] = []  # players in current lobby
        self._cache: List[Player] = []  # cache storing all the known player's data to reduce the amount of
        # requests sent to hypixel and mojang
        self._request_threads: List[Thread] = []

        self.config_manager = ConfigManager("config.txt")
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
        for player in self.players:
            if player.in_game_name == name:
                self.players.remove(player)
        self.update_view()

    def joined_new_queue(self, players: List[str]):
        self.players.clear()
        self.update_view()

        for name in players:
            player = self.is_player_in_cache(name)
            if player is not None:
                self.add_player(name)
                players.remove(name)

        split_up: List[List[str]] = []
        # since mojang can only accept lists with up to 10 usernames, we have to split the list up into multiple lists
        for index, username in enumerate(players):
            if index % MOJANG_API_PLAYER_LIMIT == 0:
                split_up.append([])

            split_up[-1].append(username)

        for section in split_up:
            t = Thread(target=self._add_listed_players_to_queue, args=(section,))
            self._request_threads.append(t)
            t.start()

    def left_queue(self):
        self.players.clear()
        self.update_view()
        # simply clear and move shit to cache

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

    def _add_player(self, player: Player):
        if not self.is_player_in_cache(player.in_game_name):
            self._cache.append(player)
        self.players.append(player)

    def _valid_key(self, api_key):
        while True:
            time.sleep(0.01)
            c = requests.get("https://api.hypixel.net/key?key=" + api_key)
            if c.status_code== 429:
                continue
            self.set_hypixel_api_reachable(True)
            return c != "" and "Invalid" not in c

    def stop(self):
        self._controller.stop()
        for player in self.players:
            player.data_download_thread.join(0.01)
        for thread in self._request_threads:
            thread.join(0.01)
        self.config_manager.save_config()
        clear_screen()
        print("saved")


class Player:
    rank_colours: dict[str, str] = {"MVP_PLUS": Colors.CYAN, "MVP": Colors.CYAN, "SUPERSTAR": Colors.GOLD,
                                    "VIP": Colors.GREEN,
                                    "VIP_PLUS": Colors.GREEN, "NON": ""}

    def __init__(self, ign: str, model: Model, uuid: str = None, nicked: bool = False):
        self._model = model

        self.in_game_name = ign
        self.uuid = uuid
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
                time.sleep(0.01) # reduces the chances of Connection Error Conection Aborted error
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
                except KeyError as first:
                    try:
                        self.rank = self.json["newPackageRank"]
                    except KeyError as second:
                        pass

                if str(self.rank) == "NONE":
                    self.rank = "NON"

                try:
                    self.party = self.json["channel"] == "PARTY"
                except KeyError as e:
                    self.party = False

                try:
                    self.finals = bw_stats["final_kills_bedwars"]
                except KeyError as e:
                    pass

                try:
                    self.wins = bw_stats["wins_bedwars"]
                except KeyError as e:
                    pass

                try:
                    self.fkdr = self.finals if bw_stats["final_deaths_bedwars"] == 0 \
                        else round(self.finals / bw_stats["final_deaths_bedwars"], 2)  # je mange des enfants
                except KeyError as e:
                    pass

                try:
                    self.wlr = self.wins if bw_stats["losses_bedwars"] == 0 \
                        else round(self.wins / bw_stats["losses_bedwars"], 2)
                except KeyError as e:
                    pass

                try:
                    self.bblr = bw_stats["beds_broken_bedwars"] if bw_stats["beds_lost_bedwars"] == 0 \
                        else round(bw_stats["beds_broken_bedwars"] / bw_stats["beds_lost_bedwars"], 2)
                except KeyError as e:
                    pass

                try:
                    self.winstreak = bw_stats["winstreak"]
                except KeyError as e:
                    pass

                try:
                    self.stars = achievements["bedwars_level"]
                except KeyError as e:
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
                except KeyError as e:
                    time.sleep(1)
            elif r.status_code == 204:  # player most likely does not exist
                self.nicked = True
                break
            else:  # codes are 429 (too many requests) amd 500 (request timed out)
                self._model.set_mojang_api_reachable(False)
                time.sleep(8)  # arbitrary number of seconds to sleep. Pulled it out of my ass

    def _get_tag_colour(self):
        if self.uuid == "54968fd589a94732b02dad8d9162175f":  # Kopamed's uuid
            return Colors.CYAN + Colors.BOLD
        elif self.nicked:
            return Colors.RED
        elif self.party:
            return Colors.BLUE

        return ""

    def _get_tag(self):
        if self.uuid == "54968fd589a94732b02dad8d9162175f":  # Kopamed's uuid
            return "DEV"
        elif self.nicked:
            return "NICK"
        elif self.party:
            return "PARTY"

        return "-" * 5

    def _get_stat_colour(self):
        if self.index < 1000:
            return ""
        elif self.index < 3000:
            return "\033[33m"
        elif self.index < 7500:
            return "\033[93m"
        elif self.index < 15000:
            return "\033[91m"
        elif self.index < 30000:
            return "\033[95m"
        elif self.index < 100000:
            return "\033[94m"
        elif self.index < 500000:
            return "\033[96m"

        return "\033[92m"

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
            stat_colour=self._get_stat_colour()
        )


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

    def __init__(self, model: Model, file_path: str):
        self._file_listener = FileListener(file_path)
        self._file_listener.attach(JoinObserver(model))
        self._file_listener.attach(LeaveObserver(model))
        self._file_listener.attach(ApiKeyObserver(model))
        self._file_listener.attach(LobbyLeaveObserver(model))
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
        with open(self.filepath, "r") as f:
            # all the lines below this line will get passed to the observers
            self._read_from_index: int = len(f.readlines())
        self.new_lines: List[str] = []  # contains all the new lines added to the file since last read

    def listen(self) -> None:
        while True:
            self.new_lines = []
            with open(self.filepath, "r") as f:
                for line in f.readlines()[self._read_from_index:]:
                    line = fix_line(line)
                    self.new_lines.append(line)
                    logging.debug("Added " + line + " to new lines")
                    self._read_from_index += 1

            if len(self.new_lines) != 0:
                self.notify()

            time.sleep(self.delay)

    def attach(self, observer: Observer) -> None:
        self._observers.append(observer)
        logging.debug(f"Attached {observer} to {self}")

    def detach(self, observer: Observer) -> None:
        self._observers.remove(observer)
        logging.debug(f"Removed {observer} from {self}")

    def notify(self) -> None:
        for observer in self._observers:
            observer.update(self)
        logging.debug(f"Update {len(self._observers)} listening to {self}")


def clear_screen(fnc=None):
    def wrapper(*args):
        ret = fnc(*args)
        print("\x1b[2J\x1b[H", end="")
        return ret

    return wrapper


class View:
    def __init__(self, model: Model):
        self._model = model

    def runtime_stats(self):
        print(Colors.GOLD + "Make sure you have Auto Who enabled in Hypixel Mods" + Colors.ENDC)
        print("Players cached: " + Colors.BOLD + str(self._model.players_cached()) + Colors.ENDC)
        print("Mojang: " + str(self._model.mojang_api_reachable))
        print("Hypixel: " + str(self._model.hypixel_api_reachable))
        print("Hypixel API key: ", end="")
        if self._model.api_key is None:
            print(Colors.BOLD + Colors.RED + "Not found!" + Colors.ENDC)
        else:
            print(
                Colors.CYAN + self._model.api_key[:int(len(self._model.api_key) / 2)] +
                ("*" * int(len(self._model.api_key) / 2)) + Colors.ENDC
            )

    @clear_screen
    def no_api_key(self):
        self.runtime_stats()
        print(Colors.RED + "No API key found! Run "
              + Colors.ENDC + Colors.BOLD + "/api new"
              + Colors.RED + " on hypixel to generate a key"
              + Colors.ENDC)

    def _sep_line(self, header):
        split_up_header = header.split("│")
        for index, content in enumerate(split_up_header):
            split_up_header[index] = "─" * len(content)
        print("┼".join(i for i in split_up_header))

    @clear_screen
    def stat_table(self):
        self.runtime_stats()

        form = "{:^16} │ {:^5} │ {:^4} │ {:^4} │ {:^6} │ {:^6} │ {:^6} │ {:^5} │ {:^5}"
        header = form.format("Name", "Tag", "Star", "WS", "FKDR", "WLR", "BBLR", "Wins", "Finals")
        print(header)
        self._sep_line(header)

        form = "{}{:^16}{end} │ {}{:^5}{end} │ {stat_colour}{:^4}{end} │ {stat_colour}{:^4}{end} │ {stat_colour}{" \
               ":^6}{end} │ {stat_colour}{:^6}{end} │ {stat_colour}{:^6}{end} │ {stat_colour}{:^5}{end} │ {" \
               "stat_colour}{:^5}{end}".replace("{end}", Colors.ENDC)

        if len(self._model.players) == 0:
            print("{:^l}".replace("l", str(len(header))).format(
                Colors.GOLD + Colors.BOLD + "No players found" + Colors.ENDC))
        else:
            for player in self._model.players:
                print(player.to_string(form))


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

    def __init__(self, model: Model):
        self._model = model

    @abstractmethod
    def update(self, observable: FileListener) -> None:
        pass


class JoinObserver(FileObserver):
    """
    Will read through the lines to determine if any new players have joined
    """

    def __init__(self, model: Model):
        super().__init__(model)

    def update(self, observable: FileListener) -> None:
        for line in observable.new_lines:
            if line.lower().startswith("online: "):
                logging.debug("Joined lobby!")
                self._model.joined_new_queue(line.strip("ONLINE: ").split(", "))
            elif " has joined" in line.lower():
                name = line.split(" ")[0]
                self._model.add_player(name)


class LeaveObserver(FileObserver):
    """
    Will read through the lines to determine if any players have left
    """

    def __init__(self, model: Model):
        super().__init__(model)

    def update(self, observable: FileListener) -> None:
        for line in observable.new_lines:
            if " has quit!" in line:
                name = line.split(" ")[0]
                logging.debug(name + " has left the lobby")
                self._model.remove_player(name)


class LobbyLeaveObserver(FileObserver):
    """
    Will read through the lines to determine if player has left the queuing lobby
    """

    def __init__(self, model: Model):
        super().__init__(model)

    def update(self, observable: FileListener) -> None:
        for line in observable.new_lines:
            if "joined the lobby!" in line:  # to change
                self._model.left_queue()


class ApiKeyObserver(FileObserver):
    """
    Will read through the lines to determine if the game has started
    """

    def __init__(self, model: Model):
        super().__init__(model)

    def update(self, observable: FileListener) -> None:
        for line in observable.new_lines:
            if line.startswith("Your new API key is"):  # to change
                api_key = line.split(" ")[-1]
                self._model.new_api_key(api_key)
