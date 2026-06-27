import os
import json
import sys

# Paths
if getattr(sys, 'frozen', False):
    # Packaged in executable (PyInstaller)
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Normal Python run
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SONGS_DIR = os.path.join(BASE_DIR, "songs")
CHARACTERS_DIR = os.path.join(BASE_DIR, "characters")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

# Ensure directories exist
os.makedirs(SONGS_DIR, exist_ok=True)
os.makedirs(CHARACTERS_DIR, exist_ok=True)

# Screen Settings
SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 768
FPS = 120  # High frame rate for responsive gameplay

# Timing Windows (in seconds)
TIMING_PERFECT = 0.022   # +/- 22ms
TIMING_GREAT = 0.045     # +/- 45ms
TIMING_GOOD = 0.090      # +/- 90ms
TIMING_OK = 0.135        # +/- 135ms

# Score Values
SCORE_PERFECT = 1000
SCORE_GREAT = 500
SCORE_GOOD = 200
SCORE_MISS = 0

# Default Configurations
DEFAULT_SETTINGS = {
    "theme": "DDR-Retro",
    "character": "Miku",
    "character_p2": "Beat Bot",
    "character_p3": "Beat Bot",
    "character_p4": "Beat Bot",
    "game_mode": "Solo",  # "Solo", "Co-Op", "Versus", "FNF", "Guitar Hero", "Karaoke"
    "players": 1,
    "show_console": False,
    "music_volume": 0.8,
    "sfx_volume": 0.7,
    "device_p1": "Keyboard",
    "device_p2": "Keyboard",
    "device_p3": "Gamepad",
    "device_p4": "Gamepad",
    "microphone_p1": -1,
    "microphone_p2": -1,
    "microphone_p3": -1,
    "microphone_p4": -1,
    "keys_p1": {
        "left": 97,          # A
        "down": 115,         # S
        "up": 119,           # W
        "right": 100,        # D
    },
    "keys_p2": {
        "left": 1073741904,  # Left Arrow
        "down": 1073741905,  # Down Arrow
        "up": 1073741906,    # Up Arrow
        "right": 1073741903, # Right Arrow
    },
    "keys_p3": {
        "left": 105,         # I
        "down": 107,         # K
        "up": 111,           # O
        "right": 108,        # L
    },
    "keys_p4": {
        "left": 1073741916,  # Numpad 4
        "down": 1073741917,  # Numpad 5
        "up": 1073741920,    # Numpad 8
        "right": 1073741918, # Numpad 6
    },
    "guitar_keys_p1": {
        "green": 97,
        "red": 115,
        "yellow": 100,
        "blue": 102,
        "orange": 103,
        "strum": 32,
        "whammy": 306,
        "tilt": 308
    },
    "guitar_keys_p2": {
        "green": 104,
        "red": 106,
        "yellow": 107,
        "blue": 108,
        "orange": 59,
        "strum": 13,
        "whammy": 305,
        "tilt": 307
    },
    "guitar_keys_p3": {
        "green": 105,        # I
        "red": 111,          # O
        "yellow": 112,       # P
        "blue": 91,          # [
        "orange": 93,          # ]
        "strum": 305,         # RCTRL
        "whammy": 308,         # LALT
        "tilt": 306
    },
    "guitar_keys_p4": {
        "green": 1073741913,  # Numpad 1
        "red": 1073741914,    # Numpad 2
        "yellow": 1073741915,  # Numpad 3
        "blue": 1073741916,    # Numpad 4
        "orange": 1073741917,  # Numpad 5
        "strum": 1073741922,   # Numpad Enter
        "whammy": 307,          # RALT
        "tilt": 305
    },
    "gamepad": {
        "enabled": True,
        "left": 13,
        "down": 14,
        "up": 11,
        "right": 12,
        "is_axis": False
    },
    "gamepad_p1": {
        "left": {"type": "button", "id": 2},
        "down": {"type": "button", "id": 0},
        "up": {"type": "button", "id": 3},
        "right": {"type": "button", "id": 1}
    },
    "gamepad_p2": {
        "left": {"type": "button", "id": 2},
        "down": {"type": "button", "id": 0},
        "up": {"type": "button", "id": 3},
        "right": {"type": "button", "id": 1}
    },
    "gamepad_p3": {
        "left": {"type": "button", "id": 2},
        "down": {"type": "button", "id": 0},
        "up": {"type": "button", "id": 3},
        "right": {"type": "button", "id": 1}
    },
    "gamepad_p4": {
        "left": {"type": "button", "id": 2},
        "down": {"type": "button", "id": 0},
        "up": {"type": "button", "id": 3},
        "right": {"type": "button", "id": 1}
    }
}

class Settings:
    def __init__(self):
        self.data = DEFAULT_SETTINGS.copy()
        self.load()
        self.SONGS_DIR = SONGS_DIR
        self.CHARACTERS_DIR = CHARACTERS_DIR
        self.BASE_DIR = BASE_DIR
        self.SETTINGS_FILE = SETTINGS_FILE
        self.SCORE_PERFECT = SCORE_PERFECT
        self.SCORE_GREAT = SCORE_GREAT
        self.SCORE_GOOD = SCORE_GOOD
        self.SCORE_MISS = SCORE_MISS

    def load(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    loaded = json.load(f)
                    # Merge loaded settings into default structures
                    for k, v in loaded.items():
                        if isinstance(v, dict) and k in self.data:
                            self.data[k].update(v)
                        else:
                            self.data[k] = v
            except Exception as e:
                print(f"Error loading settings: {e}")
                self.data = DEFAULT_SETTINGS.copy()
        else:
            self.save()

    def save(self):
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    @property
    def show_console(self):
        return self.data.get("show_console", False)

    @show_console.setter
    def show_console(self, val):
        self.data["show_console"] = bool(val)
        self.save()

    @property
    def theme(self):
        return self.data.get("theme", "DDR-Retro")

    @theme.setter
    def theme(self, val):
        self.data["theme"] = val
        self.save()

    @property
    def music_volume(self):
        return self.data.get("music_volume", 0.8)

    @music_volume.setter
    def music_volume(self, val):
        self.data["music_volume"] = max(0.0, min(1.0, val))
        self.save()

    @property
    def sfx_volume(self):
        return self.data.get("sfx_volume", 0.7)

    @sfx_volume.setter
    def sfx_volume(self, val):
        self.data["sfx_volume"] = max(0.0, min(1.0, val))
        self.save()

    @property
    def keys_p1(self):
        return self.data.get("keys_p1", DEFAULT_SETTINGS["keys_p1"])

    @keys_p1.setter
    def keys_p1(self, val):
        self.data["keys_p1"] = val
        self.save()

    @property
    def keys_p2(self):
        return self.data.get("keys_p2", DEFAULT_SETTINGS["keys_p2"])

    @keys_p2.setter
    def keys_p2(self, val):
        self.data["keys_p2"] = val
        self.save()

    @property
    def guitar_keys_p1(self):
        return self.data.get("guitar_keys_p1", DEFAULT_SETTINGS["guitar_keys_p1"])

    @guitar_keys_p1.setter
    def guitar_keys_p1(self, val):
        self.data["guitar_keys_p1"] = val
        self.save()

    @property
    def guitar_keys_p2(self):
        return self.data.get("guitar_keys_p2", DEFAULT_SETTINGS["guitar_keys_p2"])

    @guitar_keys_p2.setter
    def guitar_keys_p2(self, val):
        self.data["guitar_keys_p2"] = val
        self.save()

    # Fallback property for single player compatibility
    @property
    def keys(self):
        return self.keys_p1

    @keys.setter
    def keys(self, val):
        self.keys_p1 = val

    @property
    def gamepad(self):
        return self.data.get("gamepad", DEFAULT_SETTINGS["gamepad"])

    @gamepad.setter
    def gamepad(self, val):
        self.data["gamepad"] = val
        self.save()

    @property
    def gamepad_p1(self):
        return self.data.get("gamepad_p1", DEFAULT_SETTINGS["gamepad_p1"])

    @gamepad_p1.setter
    def gamepad_p1(self, val):
        self.data["gamepad_p1"] = val
        self.save()

    @property
    def gamepad_p2(self):
        return self.data.get("gamepad_p2", DEFAULT_SETTINGS["gamepad_p2"])

    @gamepad_p2.setter
    def gamepad_p2(self, val):
        self.data["gamepad_p2"] = val
        self.save()

    @property
    def gamepad_p3(self):
        return self.data.get("gamepad_p3", DEFAULT_SETTINGS["gamepad_p3"])

    @gamepad_p3.setter
    def gamepad_p3(self, val):
        self.data["gamepad_p3"] = val
        self.save()

    @property
    def gamepad_p4(self):
        return self.data.get("gamepad_p4", DEFAULT_SETTINGS["gamepad_p4"])

    @gamepad_p4.setter
    def gamepad_p4(self, val):
        self.data["gamepad_p4"] = val
        self.save()

    @property
    def character(self):
        return self.data.get("character", "Miku")

    @character.setter
    def character(self, val):
        self.data["character"] = val
        self.save()

    @property
    def character_p2(self):
        return self.data.get("character_p2", "Beat Bot")

    @character_p2.setter
    def character_p2(self, val):
        self.data["character_p2"] = val
        self.save()

    @property
    def character_p3(self):
        return self.data.get("character_p3", "Beat Bot")

    @character_p3.setter
    def character_p3(self, val):
        self.data["character_p3"] = val
        self.save()

    @property
    def character_p4(self):
        return self.data.get("character_p4", "Beat Bot")

    @character_p4.setter
    def character_p4(self, val):
        self.data["character_p4"] = val
        self.save()

    @property
    def device_p1(self):
        return self.data.get("device_p1", "Keyboard")

    @device_p1.setter
    def device_p1(self, val):
        self.data["device_p1"] = val
        self.save()

    @property
    def device_p2(self):
        return self.data.get("device_p2", "Keyboard")

    @device_p2.setter
    def device_p2(self, val):
        self.data["device_p2"] = val
        self.save()

    @property
    def device_p3(self):
        return self.data.get("device_p3", "Gamepad")

    @device_p3.setter
    def device_p3(self, val):
        self.data["device_p3"] = val
        self.save()

    @property
    def device_p4(self):
        return self.data.get("device_p4", "Gamepad")

    @device_p4.setter
    def device_p4(self, val):
        self.data["device_p4"] = val
        self.save()

    @property
    def keys_p3(self):
        return self.data.get("keys_p3", DEFAULT_SETTINGS["keys_p3"])

    @keys_p3.setter
    def keys_p3(self, val):
        self.data["keys_p3"] = val
        self.save()

    @property
    def keys_p4(self):
        return self.data.get("keys_p4", DEFAULT_SETTINGS["keys_p4"])

    @keys_p4.setter
    def keys_p4(self, val):
        self.data["keys_p4"] = val
        self.save()

    @property
    def guitar_keys_p3(self):
        return self.data.get("guitar_keys_p3", DEFAULT_SETTINGS["guitar_keys_p3"])

    @guitar_keys_p3.setter
    def guitar_keys_p3(self, val):
        self.data["guitar_keys_p3"] = val
        self.save()

    @property
    def guitar_keys_p4(self):
        return self.data.get("guitar_keys_p4", DEFAULT_SETTINGS["guitar_keys_p4"])

    @guitar_keys_p4.setter
    def guitar_keys_p4(self, val):
        self.data["guitar_keys_p4"] = val
        self.save()

    @property
    def game_mode(self):
        return self.data.get("game_mode", "Solo")

    @game_mode.setter
    def game_mode(self, val):
        self.data["game_mode"] = val
        self.save()

    @property
    def players(self):
        return self.data.get("players", 1)

    @players.setter
    def players(self, val):
        self.data["players"] = int(val)
        self.save()

    @property
    def microphone_p1(self):
        return self.data.get("microphone_p1", -1)

    @microphone_p1.setter
    def microphone_p1(self, val):
        self.data["microphone_p1"] = int(val)
        self.save()

    @property
    def microphone_p2(self):
        return self.data.get("microphone_p2", -1)

    @microphone_p2.setter
    def microphone_p2(self, val):
        self.data["microphone_p2"] = int(val)
        self.save()

    @property
    def microphone_p3(self):
        return self.data.get("microphone_p3", -1)

    @microphone_p3.setter
    def microphone_p3(self, val):
        self.data["microphone_p3"] = int(val)
        self.save()

    @property
    def microphone_p4(self):
        return self.data.get("microphone_p4", -1)

    @microphone_p4.setter
    def microphone_p4(self, val):
        self.data["microphone_p4"] = int(val)
        self.save()

settings = Settings()
