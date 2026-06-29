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

# Timing Windows (in seconds) - StepMania Judge 4 alignment
TIMING_PERFECT = 0.043   # +/- 43ms (matches StepMania Excellent)
TIMING_GREAT = 0.090     # +/- 90ms (matches StepMania Great)
TIMING_GOOD = 0.135      # +/- 135ms (matches StepMania Decent)
TIMING_OK = 0.180        # +/- 180ms (matches StepMania Way Off)

# Score Values
SCORE_PERFECT = 1000
SCORE_GREAT = 500
SCORE_GOOD = 200
SCORE_MISS = 0

# Default Configurations
DEFAULT_SETTINGS = {
    "theme": "DDR-Retro",
    "audio_offset": 0.0,
    "assist_tick": False,
    "proportional_scoring": False,
    "miss_penalty": 0,
    "playback_speed": 1.0,
    "character": "Miku",
    "character_p2": "Beat Bot",
    "character_p3": "Beat Bot",
    "character_p4": "Beat Bot",
    "game_mode": "Solo",  # "Solo", "Co-Op", "Versus", "FNF"
    "players": 1,
    "show_console": False,
    "music_volume": 0.8,
    "sfx_volume": 0.7,
    "device_p1": "Keyboard",
    "device_p2": "Keyboard",
    "device_p3": "Gamepad",
    "device_p4": "Gamepad",
    "keys_p1": {
        "left": [97, 1073741904],          # A, Left Arrow
        "down": [115, 1073741905],         # S, Down Arrow
        "up": [119, 1073741906],           # W, Up Arrow
        "right": [100, 1073741903],        # D, Right Arrow
    },
    "keys_p2": {
        "left": [1073741904, 0],  # Left Arrow, Unassigned
        "down": [1073741905, 0],  # Down Arrow, Unassigned
        "up": [1073741906, 0],    # Up Arrow, Unassigned
        "right": [1073741903, 0], # Right Arrow, Unassigned
    },
    "keys_p3": {
        "left": [105, 0],         # I, Unassigned
        "down": [107, 0],         # K, Unassigned
        "up": [111, 0],           # O, Unassigned
        "right": [108, 0],        # L, Unassigned
    },
    "keys_p4": {
        "left": [1073741916, 0],  # Numpad 4, Unassigned
        "down": [1073741917, 0],  # Numpad 5, Unassigned
        "up": [1073741920, 0],    # Numpad 8, Unassigned
        "right": [1073741918, 0], # Numpad 6, Unassigned
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
                    
                    # Ensure keys_p1 to keys_p4 are upgraded to list format [Set1, Set2]
                    for p in [1, 2, 3, 4]:
                        k_key = f"keys_p{p}"
                        if k_key in self.data:
                            for dir_name in ["left", "down", "up", "right"]:
                                val = self.data[k_key].get(dir_name)
                                if val is not None and not isinstance(val, list):
                                    self.data[k_key][dir_name] = [val, 0]
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
    def audio_offset(self):
        return self.data.get("audio_offset", 0.0)

    @audio_offset.setter
    def audio_offset(self, val):
        self.data["audio_offset"] = float(val)
        self.save()
    @property
    def assist_tick(self):
        return self.data.get("assist_tick", False)

    @assist_tick.setter
    def assist_tick(self, val):
        self.data["assist_tick"] = bool(val)
        self.save()

    @property
    def proportional_scoring(self):
        return self.data.get("proportional_scoring", False)

    @proportional_scoring.setter
    def proportional_scoring(self, val):
        self.data["proportional_scoring"] = bool(val)
        self.save()

    @property
    def miss_penalty(self):
        return self.data.get("miss_penalty", 0)

    @miss_penalty.setter
    def miss_penalty(self, val):
        self.data["miss_penalty"] = int(val)
        self.save()

    @property
    def playback_speed(self):
        return self.data.get("playback_speed", 1.0)

    @playback_speed.setter
    def playback_speed(self, val):
        self.data["playback_speed"] = float(val)
        self.save()

settings = Settings()
