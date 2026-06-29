import os
import json
import time
import datetime
from config import BASE_DIR

PROFILE_FILE = os.path.join(BASE_DIR, "profile.json")

ACHIEVEMENTS = {
    "first_steps": {
        "name": "First Steps",
        "description": "Completed your first song!",
        "unlock_tagline": "Step Starter",
        "unlock_theme": None
    },
    "combo_master": {
        "name": "Combo Master",
        "description": "Reached a combo of 100+!",
        "unlock_tagline": "Combo King",
        "unlock_theme": None
    },
    "clean_sheet": {
        "name": "Clean Sheet",
        "description": "Achieved a Full Combo!",
        "unlock_tagline": "Untouchable",
        "unlock_theme": None
    },
    "speedrunner": {
        "name": "Speedrunner",
        "description": "Completed a song at 1.5x speed or more!",
        "unlock_tagline": "Super Sonic",
        "unlock_theme": None
    },
    "retro_rhythm": {
        "name": "Retro Rhythm",
        "description": "Played the song Retro Beat!",
        "unlock_tagline": "8-Bit DJ",
        "unlock_theme": "Retro-Pixel"
    },
    "decathlete": {
        "name": "Decathlete",
        "description": "Played 10 or more songs!",
        "unlock_tagline": "Marathon Runner",
        "unlock_theme": "Minimalist"
    }
}

AVATARS = [
    {"id": "headphones", "char": "🎧", "name": "Audio Head"},
    {"id": "gamepad", "char": "🎮", "name": "Game Pad"},
    {"id": "lightning", "char": "⚡", "name": "Volt"},
    {"id": "paw", "char": "🐾", "name": "Paws"},
    {"id": "fire", "char": "🔥", "name": "Spitfire"},
    {"id": "crown", "char": "👑", "name": "Royalty"}
]

class ProfileManager:
    def __init__(self):
        self.profile = None
        self.load()

    def exists(self):
        return self.profile is not None

    def load(self):
        if os.path.exists(PROFILE_FILE):
            try:
                with open(PROFILE_FILE, "r", encoding="utf-8") as f:
                    self.profile = json.load(f)
                # Ensure all required structures exist
                if "scores" not in self.profile:
                    self.profile["scores"] = {}
                if "stats" not in self.profile:
                    self.profile["stats"] = {}
                if "achievements" not in self.profile:
                    self.profile["achievements"] = []
                if "unlocked_themes" not in self.profile:
                    self.profile["unlocked_themes"] = ["DDR-Retro", "Futuristic", "Kawaii-Pink", "Neko-Pixel"]
                else:
                    for t in ["DDR-Retro", "Futuristic", "Kawaii-Pink", "Neko-Pixel"]:
                        if t not in self.profile["unlocked_themes"]:
                            self.profile["unlocked_themes"].append(t)
                if "unlocked_taglines" not in self.profile:
                    self.profile["unlocked_taglines"] = ["Beginner"]
                if "unlocked_skins" not in self.profile:
                    self.profile["unlocked_skins"] = ["default"]
                if "avatar" not in self.profile:
                    self.profile["avatar"] = "headphones"
                if "tagline" not in self.profile:
                    self.profile["tagline"] = "Beginner"
                
                # Fill missing default stats
                default_stats = {
                    "songs_played": 0,
                    "total_play_time_seconds": 0,
                    "highest_combo_ever": 0,
                    "total_perfects": 0,
                    "total_greats": 0,
                    "total_goods": 0,
                    "total_misses": 0,
                    "average_accuracy": 0.0,
                    "last_played": []
                }
                for k, v in default_stats.items():
                    if k not in self.profile["stats"]:
                        self.profile["stats"][k] = v
            except Exception as e:
                print(f"Error loading profile: {e}")
                self.profile = None
        else:
            self.profile = None

    def create_profile(self, name, avatar):
        self.profile = {
            "player_name": name,
            "avatar": avatar,
            "tagline": "Beginner",
            "scores": {},
            "stats": {
                "songs_played": 0,
                "total_play_time_seconds": 0,
                "highest_combo_ever": 0,
                "total_perfects": 0,
                "total_greats": 0,
                "total_goods": 0,
                "total_misses": 0,
                "average_accuracy": 0.0,
                "last_played": []
            },
            "achievements": [],
            "unlocked_themes": ["DDR-Retro", "Futuristic", "Kawaii-Pink", "Neko-Pixel"],
            "unlocked_taglines": ["Beginner"],
            "unlocked_skins": ["default"]
        }
        self.save()

    def save(self):
        if self.profile:
            try:
                with open(PROFILE_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.profile, f, indent=4)
            except Exception as e:
                print(f"Error saving profile: {e}")

    def update_after_gameplay(self, song_title, difficulty, results, playback_speed):
        if not self.profile:
            return []

        stats = self.profile["stats"]
        scores = self.profile["scores"]

        # 1. Update basic counts
        stats["songs_played"] += 1
        dur = results.get("duration", 60.0)
        stats["total_play_time_seconds"] += int(dur)
        
        perf = results.get("perfects", 0)
        grt = results.get("greats", 0)
        gd = results.get("goods", 0)
        ms = results.get("misses", 0)
        
        stats["total_perfects"] += perf
        stats["total_greats"] += grt
        stats["total_goods"] += gd
        stats["total_misses"] += ms

        if results.get("max_combo", 0) > stats["highest_combo_ever"]:
            stats["highest_combo_ever"] = results["max_combo"]

        # Calculate accuracy for this session
        total_notes = perf + grt + gd + ms
        session_acc = 0.0
        if total_notes > 0:
            session_acc = (perf * 100 + grt * 75 + gd * 40) / total_notes
        
        # Cumulative average accuracy
        all_notes = stats["total_perfects"] + stats["total_greats"] + stats["total_goods"] + stats["total_misses"]
        if all_notes > 0:
            stats["average_accuracy"] = round((stats["total_perfects"] * 100 + stats["total_greats"] * 75 + stats["total_goods"] * 40) / all_notes, 2)

        # 2. Update last played
        last_played = stats.get("last_played", [])
        last_played.insert(0, {
            "title": song_title,
            "difficulty": difficulty,
            "score": results.get("score", 0),
            "grade": results.get("grade", "F"),
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        })
        stats["last_played"] = last_played[:10]  # Keep last 10

        # 3. Update top scores per song + difficulty
        score_key = f"{song_title.lower().replace(' ', '_')}_{difficulty.lower()}"
        current_best = scores.get(score_key)
        
        is_full_combo = (ms == 0 and total_notes > 0)
        is_all_perfect = (perf == total_notes and total_notes > 0)
        
        new_score = results.get("score", 0)
        if current_best is None or new_score > current_best.get("best_score", 0):
            scores[score_key] = {
                "title": song_title,
                "difficulty": difficulty,
                "best_score": new_score,
                "best_accuracy": round(session_acc, 2),
                "grade": results.get("grade", "F"),
                "max_combo": results.get("max_combo", 0),
                "full_combo": is_full_combo,
                "all_perfect": is_all_perfect,
                "perfects": perf,
                "greats": grt,
                "goods": gd,
                "misses": ms,
                "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            }

        # 4. Check achievements
        newly_unlocked = []
        
        # first_steps
        if "first_steps" not in self.profile["achievements"]:
            newly_unlocked.append("first_steps")
            
        # combo_master
        if results.get("max_combo", 0) >= 100 and "combo_master" not in self.profile["achievements"]:
            newly_unlocked.append("combo_master")
            
        # clean_sheet
        if is_full_combo and "clean_sheet" not in self.profile["achievements"]:
            newly_unlocked.append("clean_sheet")
            
        # speedrunner
        if playback_speed >= 1.5 and "speedrunner" not in self.profile["achievements"]:
            newly_unlocked.append("speedrunner")
            
        # retro_rhythm
        if "retro_beat" in song_title.lower() and "retro_rhythm" not in self.profile["achievements"]:
            newly_unlocked.append("retro_rhythm")
            
        # decathlete
        if stats["songs_played"] >= 10 and "decathlete" not in self.profile["achievements"]:
            newly_unlocked.append("decathlete")

        # Process new unlocks
        for ach_id in newly_unlocked:
            self.profile["achievements"].append(ach_id)
            info = ACHIEVEMENTS[ach_id]
            if info["unlock_tagline"] and info["unlock_tagline"] not in self.profile["unlocked_taglines"]:
                self.profile["unlocked_taglines"].append(info["unlock_tagline"])
            if info["unlock_theme"] and info["unlock_theme"] not in self.profile["unlocked_themes"]:
                self.profile["unlocked_themes"].append(info["unlock_theme"])

        self.save()
        return newly_unlocked

    def get_avatar_char(self):
        if not self.profile:
            return "🎧"
        av_id = self.profile.get("avatar", "headphones")
        for av in AVATARS:
            if av["id"] == av_id:
                return av["char"]
        return "🎧"

    def get_top_10_scores(self):
        if not self.profile:
            return []
        # Sort all best scores by best_score descending
        all_scores = list(self.profile["scores"].values())
        all_scores.sort(key=lambda x: x.get("best_score", 0), reverse=True)
        return all_scores[:10]

profile_manager = ProfileManager()
