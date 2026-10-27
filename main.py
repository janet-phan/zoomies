import os
os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"
os.environ["SDL_JOYSTICK_RAWINPUT"] = "0"
import pygame
import sys
import json
import shutil
import threading
import time
import wave
import struct
import math
import random
import subprocess

# Import game modules
import zipfile
from sm_parser import SMParser
from config import settings, SCREEN_WIDTH, SCREEN_HEIGHT, FPS, TIMING_PERFECT, TIMING_GREAT, TIMING_GOOD
from input_manager import input_manager
from theme_manager import theme_manager
from sound_helper import sound_helper
from song_analyzer import SongAnalyzer
from gameplay import Gameplay
from editor import ChartEditor
from profile_manager import profile_manager, ACHIEVEMENTS, AVATARS
from celebration import CelebrationSystem

def render_truncated_text(font, text, max_width, color):
    if font.size(text)[0] <= max_width:
        return font.render(text, True, color)
    for i in range(len(text), 0, -1):
        truncated = text[:i] + "..."
        if font.size(truncated)[0] <= max_width:
            return font.render(truncated, True, color)
    return font.render("...", True, color)

def draw_wrapped_text(surface, font, text, color, x, y, max_width, line_spacing=5):
    words = text.split(" ")
    lines = []
    current_line = []
    for word in words:
        test_line = " ".join(current_line + [word])
        if font.size(test_line)[0] <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))
        
    curr_y = y
    for line in lines:
        line_surf = font.render(line, True, color)
        surface.blit(line_surf, (x, curr_y))
        curr_y += font.get_linesize() + line_spacing
    return curr_y

def draw_wrapped_text_centered(surface, font, text, color, cx, y, max_width, line_spacing=5):
    words = text.split(" ")
    lines = []
    current_line = []
    for word in words:
        test_line = " ".join(current_line + [word])
        if font.size(test_line)[0] <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))
        
    curr_y = y
    for line in lines:
        line_surf = font.render(line, True, color)
        surface.blit(line_surf, (cx - line_surf.get_width() // 2, curr_y))
        curr_y += font.get_linesize() + line_spacing
    return curr_y

class App:
    def __init__(self):
        pygame.init()
        pygame.display.init()
        pygame.font.init()
        
        # Initialize screen
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Zoomies - Beat Generation Rhythm Game")
        
        # Set window icon
        try:
            base_path = getattr(sys, '_MEIPASS', settings.BASE_DIR)
            icon_path = os.path.join(base_path, "zoomies_icon.png")
            if not os.path.exists(icon_path):
                icon_path = os.path.join(settings.BASE_DIR, "zoomies_icon.png")
            if os.path.exists(icon_path):
                icon_surf = pygame.image.load(icon_path)
                pygame.display.set_icon(icon_surf)
        except Exception as e:
            print(f"Could not load window icon: {e}")
        
        self.clock = pygame.Clock()
        input_manager.refresh_joysticks()
        self.apply_console_visibility()
        self.running = True
        
        # State Management
        # "TITLE", "SONG_SELECT", "ANALYZING", "GAMEPLAY", "RESULTS", "SETTINGS", "REMAP", "EDITOR", "PROFILE_CREATION", "PROFILE_STATS"
        self.state = "PROFILE_CREATION" if not profile_manager.exists() else "TITLE"
        self.celebration = CelebrationSystem(SCREEN_WIDTH, SCREEN_HEIGHT)
        self.profile_creation_name = ""
        self.profile_creation_avatar_idx = 0
        
        self.taglines = [
            "When the beat hits... the zoomies begin.",
            "No thoughts. Just rhythm.",
            "Hit the beat. Chase the laser.",
            "The rhythm got the cat.",
            "Warning: May cause uncontrollable dancing.",
            "Powered by caffeine and chaos.",
            "Four arrows. Infinite zoomies.",
            "Catch the beat before it escapes!",
            "Perfect timing. Questionable self-control.",
            "Stay on beat. Avoid the furniture.",
            "Where every combo has orange cat energy.",
            "Dance first. Think later.",
            "Keep calm and hit the arrows.",
            "Miss a beat? Pretend it was jazz.",
            "From nap... to max speed in 0.2 seconds.",
            "The floor is your keyboard.",
            "Warning: Side effects include head bobbing.",
            "Easy to learn. Hard to master.",
            "One more song.",
            "Feel the beat.",
            "Find your rhythm.",
            "Perfect isn't required. Style is.",
            "Arcade rhythm, modern zoomies."
        ]
        self.loading_tips = [
            "🐾 Hydration improves rhythm. Probably.",
            "🐾 Cats have excellent timing. Be more like a cat.",
            "🐾 The arrows are coming. They don't know mercy.",
            "🐾 Missing one note doesn't count if nobody saw it.",
            "🐾 Professional cat supervision not included."
        ]
        import random
        self.active_tagline = random.choice(self.taglines)
        self.active_tip = random.choice(self.loading_tips)
        self.last_tagline_state = "TITLE"
        self.last_tip_state = "ANALYZING"
        self.practice_start_measure = 0
        self.practice_end_measure = 8
        
        # Menu Indices
        self.title_index = 0
        self.title_options = ["PLAY", "PROFILE & STATS", "SETTINGS", "EXIT"]
        self.newly_unlocked_achievements = []
        self.achievement_banner_timer = 0.0
        self.mode_index = 0
        self.mode_options = ["SOLO", "CO-OP", "VERSUS", "FNF", "PRACTICE"]
        self.fnf_match_types = ["AI vs Human", "Human vs Human", "Human vs AI", "AI vs AI"]
        self.fnf_match_type_index = 0
        
        # Lobby Inline Typing / Editing
        self.lobby_edit_mode = None
        self.lobby_edit_buffer = ""
        pygame.key.set_repeat(350, 30)
        
        self.settings_index = 0
        self.settings_scroll_y = 0
        self.settings_options = [
            "PLAYERS",
            "GAME MODE",
            "P1 CHARACTER",
            "P2 CHARACTER",
            "THEME",
            "MUSIC VOLUME",
            "SFX VOLUME",
            "REMAP P1 KEYBOARD (DDR)",
            "REMAP P2 KEYBOARD (DDR)",
            "BACK"
        ]
        
        # Scan cheering characters
        self.characters_list = ["Beat Bot"]
        self.scan_characters()
        
        # Verify selected character exists
        if settings.character not in self.characters_list:
            settings.character = "Miku" if "Miku" in self.characters_list else self.characters_list[0]
        self.character_index = self.characters_list.index(settings.character)
        
        if settings.character_p2 not in self.characters_list:
            settings.character_p2 = "Beat Bot" if "Beat Bot" in self.characters_list else self.characters_list[0]
        self.character_p2_index = self.characters_list.index(settings.character_p2)

        self.song_index = 0
        self.songs_list = []
        self.display_list = []
        self.expanded_groups = set()
        self.cover_cache = {}
        self.difficulty_index = 1  # Default to Medium
        self.difficulties = ["Easy", "Medium", "Hard", "Harder", "Crazy", "Dynamic", "Custom"]
        
        # Audio Analysis Thread State
        self.analyzer = SongAnalyzer()
        self.analysis_thread = None
        self.analysis_error = None
        self.analysis_progress_text = "Idle..."
        self.analysis_success_data = None
        self.spinner_angle = 0
        
        # Details Card Dynamic Positions
        self.diff_box_y = 340
        self.btn_y = 550
        self.density_y = 500
        self.warning_notification = ""
        self.warning_notification_timer = 0.0

        # Scan songs folder
        self.scan_songs()
        
        # Synthesize and analyze a default retro beat song if library is empty
        if not self.songs_list:
            self.generate_default_song()
            
        self.update_difficulties_list()
        
        # Gameplay Session
        self.gameplay = None
        
        # Chart Editor Session
        self.editor = None
        
        # Results Session
        self.results_data = None
        
        # Key Remap state
        self.remap_target_dir = None  # "left", "down", "up", "right"
        self.remap_target_device = "keyboard"  # "keyboard" or "gamepad"
        self.remap_step = 0  # 0: Left, 1: Down, 2: Up, 3: Right
        self.remap_directions = ["left", "down", "up", "right"]
        self.remap_info_text = "Press any key/button..."

        # Init sounds
        sound_helper.init_sounds()

        # Title screen background particles (drifting cat paws/heads)
        self.title_particles = []
        for _ in range(16):
            self.title_particles.append({
                "x": random.randint(0, SCREEN_WIDTH),
                "y": random.randint(0, SCREEN_HEIGHT),
                "speed_y": random.uniform(-60, -20),
                "speed_x": random.uniform(-10, 10),
                "type": random.choice(["paw", "face"]),
                "size": random.randint(18, 32),
                "alpha": random.randint(25, 75),
                "wobble_speed": random.uniform(1.2, 2.8),
                "wobble_amp": random.uniform(6, 14),
                "start_time": random.uniform(0, 100)
            })

    def scan_songs(self):
        """Scans the songs directory recursively for JSON beatmaps, groups, and cover arts."""
        self.songs_list = []
        if not os.path.exists(settings.SONGS_DIR):
            os.makedirs(settings.SONGS_DIR)
            
        # Clear cover cache
        self.cover_cache = {}
        
        # Traverse songs directory recursively
        for root, dirs, files in os.walk(settings.SONGS_DIR):
            for file_name in files:
                if file_name.endswith(".json"):
                    json_path = os.path.join(root, file_name)
                    try:
                        with open(json_path, "r", encoding="utf-8") as file:
                            data = json.load(file)
                            # Verify it has charts
                            if "charts" in data and "title" in data:
                                # Determine group name from folder path
                                rel_path = os.path.relpath(root, settings.SONGS_DIR)
                                if rel_path == "." or rel_path == "":
                                    group_name = "Default Album"
                                else:
                                    parts = rel_path.split(os.sep)
                                    group_name = parts[0]
                                
                                data["group"] = group_name
                                data["json_path"] = json_path
                                
                                # Search for cover art image in the same directory (root)
                                json_basename = os.path.splitext(file_name)[0]
                                cover_image_path = None
                                valid_exts = [".png", ".jpg", ".jpeg"]
                                
                                # 1. Check same base name as json
                                for ext in valid_exts:
                                    test_path = os.path.join(root, json_basename + ext)
                                    if os.path.exists(test_path):
                                        cover_image_path = test_path
                                        break
                                
                                # 2. Check general names like cover, jacket, banner, album
                                if not cover_image_path:
                                    for name in ["cover", "jacket", "banner", "album", "folder"]:
                                        for ext in valid_exts:
                                            for case_name in [name, name.upper(), name.capitalize()]:
                                                test_path = os.path.join(root, case_name + ext)
                                                if os.path.exists(test_path):
                                                    cover_image_path = test_path
                                                    break
                                            if cover_image_path:
                                                break
                                        if cover_image_path:
                                            break
                                            
                                # 3. Fallback: check one directory level up if we are inside GroupName/SongName/
                                if not cover_image_path and len(rel_path.split(os.sep)) > 1:
                                    parent_dir = os.path.dirname(root)
                                    for name in ["cover", "jacket", "banner", "album", "folder"]:
                                        for ext in valid_exts:
                                            for case_name in [name, name.upper(), name.capitalize()]:
                                                test_path = os.path.join(parent_dir, case_name + ext)
                                                if os.path.exists(test_path):
                                                    cover_image_path = test_path
                                                    break
                                            if cover_image_path:
                                                break
                                        if cover_image_path:
                                            break
                                            
                                data["cover_path"] = cover_image_path
                                self.songs_list.append(data)
                    except Exception as e:
                        print(f"Error reading song map {file_name}: {e}")
                        
        # Sort alphabetically by title
        self.songs_list = sorted(self.songs_list, key=lambda x: x["title"])
        
        # Build display list
        self.build_display_list()
        
        # Auto-expand the first group if expanded_groups is empty
        if self.songs_list and not self.expanded_groups:
            grouped_keys = sorted(list(set(s.get("group", "Default Album") for s in self.songs_list)))
            if grouped_keys:
                self.expanded_groups.add(grouped_keys[0])
                self.build_display_list()

    def build_display_list(self):
        """Builds a flat list of display items (groups & songs) for selection screen."""
        self.display_list = []
        
        # Group songs by their group name
        grouped = {}
        for song in self.songs_list:
            grp = song.get("group", "Default Album")
            if grp not in grouped:
                grouped[grp] = []
            grouped[grp].append(song)
            
        # Sort group names alphabetically
        sorted_groups = sorted(grouped.keys())
        
        for grp in sorted_groups:
            group_songs = grouped[grp]
            # Group item
            self.display_list.append({
                "type": "group",
                "name": grp,
                "count": len(group_songs),
                "songs": group_songs
            })
            
            # If group is expanded, append its songs
            if grp in self.expanded_groups:
                for song in group_songs:
                    self.display_list.append({
                        "type": "song",
                        "song": song,
                        "group": grp
                    })
                    
        # Append Upload Custom Song option at the end
        self.display_list.append({
            "type": "upload"
        })

    def scan_characters(self):
        """Scans characters directory for folders containing a cheer image."""
        if not os.path.exists(settings.CHARACTERS_DIR):
            os.makedirs(settings.CHARACTERS_DIR, exist_ok=True)
            
        for name in os.listdir(settings.CHARACTERS_DIR):
            path = os.path.join(settings.CHARACTERS_DIR, name)
            if os.path.isdir(path):
                # Check for cheer image
                has_image = False
                for ext in ["png", "jpg", "jpeg"]:
                    if os.path.exists(os.path.join(path, f"cheer.{ext}")):
                        has_image = True
                        break
                if has_image:
                    self.characters_list.append(name)

    def generate_default_song(self):
        """Generates a retro drum loop wav and maps it dynamically if library is empty."""
        print("No songs found in songs library. Generating a default synth beat loop...")
        wav_path = os.path.join(settings.SONGS_DIR, "Retro_Beat.wav")
        json_path = os.path.join(settings.SONGS_DIR, "Retro_Beat.json")
        
        try:
            self._synthesize_default_wav(wav_path)
            self.analyzer.analyze_song(wav_path, json_path)
            self.scan_songs()
        except Exception as e:
            print(f"Error generating default song: {e}")

    def _synthesize_default_wav(self, filepath):
        sr = 44100
        bpm = 120.0
        beat_dur = 60.0 / bpm  # 0.5 seconds
        num_beats = 64  # 32 seconds total
        
        with wave.open(filepath, "w") as wav_file:
            wav_file.setnchannels(2)
            wav_file.setsampwidth(2)  # 16-bit PCM
            wav_file.setframerate(sr)
            
            # Kick drum sweep: 150Hz -> 40Hz
            kick_dur = 0.15
            kick_samples = int(sr * kick_dur)
            kick_data = []
            for i in range(kick_samples):
                t = i / sr
                freq = 150.0 - (110.0 * (t / kick_dur))
                val = math.sin(2 * math.pi * freq * t) * math.exp(-t * 22)
                kick_data.append(val)
                
            # Snare drum noise burst
            snare_dur = 0.18
            snare_samples = int(sr * snare_dur)
            snare_data = []
            for i in range(snare_samples):
                t = i / sr
                val = random.uniform(-1.0, 1.0) * math.exp(-t * 18) * 0.4
                snare_data.append(val)
                
            # Hi-hat tick noise burst
            hat_dur = 0.04
            hat_samples = int(sr * hat_dur)
            hat_data = []
            for i in range(hat_samples):
                t = i / sr
                val = random.uniform(-1.0, 1.0) * math.exp(-t * 120) * 0.2
                hat_data.append(val)
                
            # Build and write frames
            for beat in range(num_beats):
                beat_samples = int(sr * beat_dur)
                for i in range(beat_samples):
                    sample_val = 0.0
                    
                    # Kick on 1 and 3 (0 and 2 mod 4)
                    if beat % 2 == 0:
                        if i < len(kick_data):
                            sample_val += kick_data[i]
                            
                    # Snare on 2 and 4 (1 and 3 mod 4)
                    if beat % 2 == 1:
                        if i < len(snare_data):
                            sample_val += snare_data[i]
                            
                    # Hi-hat on offbeat (eighth note)
                    half_beat = beat_samples // 2
                    if i >= half_beat:
                        hat_idx = i - half_beat
                        if hat_idx < len(hat_data):
                            sample_val += hat_data[hat_idx]
                            
                    sample_val = max(-1.0, min(1.0, sample_val)) * 0.7
                    int_val = int(sample_val * 32767)
                    frame = struct.pack("<hh", int_val, int_val)
                    wav_file.writeframesraw(frame)

    def run(self):
        dt = 0
        while self.running:
            # Main game loop limit FPS
            dt = self.clock.tick(FPS) / 1000.0  # seconds
            
            try:
                self.handle_events()
                self.update(dt)
                self.draw()
            except Exception as e:
                import traceback
                self.error_traceback = traceback.format_exc()
                self.state = "ERROR_SCREEN"
                try:
                    pygame.mixer.music.stop()
                except:
                    pass
            
        pygame.quit()
        sys.exit()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return

            if self.state == "DIFFICULTY_SELECT_OVERLAY":
                if event.type == pygame.KEYDOWN:
                    key = event.key
                    
                    p1_up = settings.keys_p1.get("up", [])
                    p1_down = settings.keys_p1.get("down", [])
                    p1_confirm = [pygame.K_RETURN, pygame.K_SPACE]
                    if not isinstance(p1_up, list): p1_up = [p1_up]
                    if not isinstance(p1_down, list): p1_down = [p1_down]
                    
                    p2_up = settings.keys_p2.get("up", [])
                    p2_down = settings.keys_p2.get("down", [])
                    p2_confirm = [pygame.K_KP_ENTER, pygame.K_TAB, pygame.K_f]
                    if not isinstance(p2_up, list): p2_up = [p2_up]
                    if not isinstance(p2_down, list): p2_down = [p2_down]
                    
                    if key == pygame.K_ESCAPE:
                        sound_helper.play_back()
                        self.state = "SONG_SELECT"
                        continue
                        
                    if not self.p1_ready:
                        if key in p1_up:
                            self.p1_diff_index = (self.p1_diff_index - 1) % len(self.difficulties)
                            sound_helper.play_select()
                        elif key in p1_down:
                            self.p1_diff_index = (self.p1_diff_index + 1) % len(self.difficulties)
                            sound_helper.play_select()
                        elif key in p1_confirm:
                            sound_helper.play_select()
                            self.p1_ready = True
                    else:
                        if key == pygame.K_BACKSPACE:
                            sound_helper.play_back()
                            self.p1_ready = False
                            
                    if settings.players == 2:
                        if not self.p2_ready:
                            if key in p2_up:
                                self.p2_diff_index = (self.p2_diff_index - 1) % len(self.difficulties)
                                sound_helper.play_select()
                            elif key in p2_down:
                                self.p2_diff_index = (self.p2_diff_index + 1) % len(self.difficulties)
                                sound_helper.play_select()
                            elif key in p2_confirm:
                                sound_helper.play_select()
                                self.p2_ready = True
                        else:
                            if key == pygame.K_LSHIFT or key in p2_confirm:
                                sound_helper.play_back()
                                self.p2_ready = False
                                
                    if self.p1_ready and self.p2_ready:
                        self.start_gameplay_from_overlay()
                    continue

            if self.state == "ERROR_SCREEN":
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.state = "TITLE"
                    self.gameplay = None
                    self.editor = None
                    try:
                        pygame.mixer.music.load(os.path.join(settings.SONGS_DIR, self.songs_list[self.song_index]["audio"]))
                        pygame.mixer.music.play(-1)
                    except:
                        pass
                continue

            if self.state == "CALIBRATION":
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        sound_helper.play_back()
                        self.state = "SETTINGS"
                        continue
                    elif event.key == pygame.K_RETURN:
                        if self.calib_taps:
                            avg_offset = sum(self.calib_taps) / len(self.calib_taps)
                            settings.audio_offset = avg_offset
                            print(f"Saved audio offset: {avg_offset:.4f}s")
                        sound_helper.play_select()
                        self.state = "SETTINGS"
                        continue
                    elif event.key in [pygame.K_SPACE, pygame.K_d, pygame.K_f, pygame.K_j, pygame.K_k]:
                        self.register_calibration_tap()
                        continue
                elif event.type == pygame.JOYBUTTONDOWN:
                    if event.button == 1: # B button
                        sound_helper.play_back()
                        self.state = "SETTINGS"
                        continue
                    elif event.button == 0: # A button
                        self.register_calibration_tap()
                        continue
                continue

            # --- MENU NAVIGATION KEYS ---
            if self.state in ["TITLE", "SONG_SELECT", "SETTINGS", "RESULTS"]:
                if event.type == pygame.KEYDOWN:
                    if event.key in [pygame.K_UP, pygame.K_w]:
                        self.trigger_direction("up")
                        continue
                    elif event.key in [pygame.K_DOWN, pygame.K_s]:
                        self.trigger_direction("down")
                        continue
                    elif event.key in [pygame.K_LEFT, pygame.K_a]:
                        self.trigger_direction("left")
                        continue
                    elif event.key in [pygame.K_RIGHT, pygame.K_d]:
                        self.trigger_direction("right")
                        continue
                    elif event.key in [pygame.K_RETURN, pygame.K_SPACE]:
                        self.trigger_confirm()
                        continue
                    elif event.key == pygame.K_ESCAPE:
                        self.trigger_back()
                        continue

            # Mouse click/scroll detection
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    mx, my = event.pos
                    self.handle_mouse_click(mx, my)
                    continue
                elif self.state == "SONG_SELECT" and event.button in [4, 5]:
                    mx, my = pygame.mouse.get_pos()
                    if mx >= 500:
                        dir_scroll = -1 if event.button == 4 else 1
                        if self.difficulties:
                            self.difficulty_index = (self.difficulty_index + dir_scroll) % len(self.difficulties)
                        sound_helper.play_select()
                    else:
                        dir_scroll = -1 if event.button == 4 else 1
                        self.song_index = (self.song_index + dir_scroll) % len(self.display_list)
                        self.update_difficulties_list()
                        sound_helper.play_select()
                    continue
                elif self.state == "PROFILE_STATS" and event.button in [4, 5]:
                    dir_scroll = -1 if event.button == 4 else 1
                    self.profile_scroll_idx = max(0, self.profile_scroll_idx + dir_scroll)
                    sound_helper.play_select()
                    continue
                elif self.state == "EDITOR" and event.button in [4, 5]:
                    self.editor.handle_scroll(event.button)
                    continue
                elif self.state == "SETTINGS" and event.button in [4, 5]:
                    dir_scroll = -1 if event.button == 4 else 1
                    opts = self.get_settings_options()
                    self.settings_index = (self.settings_index + dir_scroll) % len(opts)
                    while opts[self.settings_index].startswith("---"):
                        self.settings_index = (self.settings_index + dir_scroll) % len(opts)
                    # Scroll active index into view (maximum 12 visible items)
                    if self.settings_index < self.settings_scroll_y:
                        self.settings_scroll_y = self.settings_index
                    elif self.settings_index >= self.settings_scroll_y + 12:
                        self.settings_scroll_y = self.settings_index - 11
                    sound_helper.play_select()
                    continue

            # --- GAMEPLAY KEYS & GAMEPADS ROUTING ---
            if self.state == "GAMEPLAY" and self.gameplay:
                if event.type in [pygame.KEYDOWN, pygame.KEYUP]:
                    is_down = (event.type == pygame.KEYDOWN)
                    key = event.key
                    
                    if is_down and key == pygame.K_ESCAPE:
                        self.trigger_back()
                        continue
                        
                    if is_down and key == pygame.K_F7:
                        settings.assist_tick = not settings.assist_tick
                        sound_helper.play_select()
                        self.gameplay.assist_tick_notif_timer = 2.0
                        continue
                    
                    # Distribute inputs to keyboard-controlled players
                    for p_idx in range(self.gameplay.players_count):
                        p_num = p_idx + 1
                        device = getattr(settings, f"device_p{p_num}", "Keyboard")
                        if device == "Keyboard":
                            # DDR/FNF modes
                            p_keys = getattr(settings, f"keys_p{p_num}", {})
                            for dir_idx, dir_name in enumerate(["left", "down", "up", "right"]):
                                mapped_val = p_keys.get(dir_name)
                                if isinstance(mapped_val, list):
                                    if key in mapped_val:
                                        self.gameplay.trigger_input(dir_idx, is_down, p_idx)
                                        break
                                else:
                                    if key == mapped_val:
                                        self.gameplay.trigger_input(dir_idx, is_down, p_idx)
                                        break
                                    
                elif event.type in [pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP]:
                    is_down = (event.type == pygame.JOYBUTTONDOWN)
                    btn_id = event.button
                    
                    # Find which player maps to this gamepad ID (event.joy)
                    joystick_players = [idx for idx in range(self.gameplay.players_count) if getattr(settings, f"device_p{idx+1}") == "Gamepad"]
                    if joystick_players:
                        if len(joystick_players) == 1:
                            p_idx = joystick_players[0]
                        else:
                            if event.joy < len(joystick_players):
                                p_idx = joystick_players[event.joy]
                            else:
                                continue
                        p_num = p_idx + 1
                        gp_settings = getattr(settings, f"gamepad_p{p_num}", {})
                            
                        for dir_name in gp_settings.keys():
                            map_val = gp_settings.get(dir_name)
                            if isinstance(map_val, dict) and map_val.get("type") == "button":
                                if btn_id == map_val.get("id"):
                                    self.process_gamepad_gameplay_input(p_idx, dir_name, is_down)
                                        
                elif event.type == pygame.JOYHATMOTION:
                    x, y = event.value
                    
                    # Find which player maps to this gamepad ID (event.joy)
                    joystick_players = [idx for idx in range(self.gameplay.players_count) if getattr(settings, f"device_p{idx+1}") == "Gamepad"]
                    if joystick_players:
                        if len(joystick_players) == 1:
                            p_idx = joystick_players[0]
                        else:
                            if event.joy < len(joystick_players):
                                p_idx = joystick_players[event.joy]
                            else:
                                continue
                        p_num = p_idx + 1
                        gp_settings = getattr(settings, f"gamepad_p{p_num}", {})
                            
                        for dir_name in gp_settings.keys():
                            map_val = gp_settings.get(dir_name)
                            if isinstance(map_val, dict) and map_val.get("type") == "hat":
                                target_hat = map_val.get("hat_idx", 0)
                                if event.hat == target_hat:
                                    target_val = map_val.get("value")
                                    is_active = False
                                    if target_val[0] != 0 and x == target_val[0]:
                                        is_active = True
                                    if target_val[1] != 0 and y == target_val[1]:
                                        is_active = True
                                    self.process_gamepad_gameplay_input(p_idx, dir_name, is_active)
                                        
                elif event.type == pygame.JOYAXISMOTION:
                    axis_val = event.value
                    
                    # Find which player maps to this gamepad ID (event.joy)
                    joystick_players = [idx for idx in range(self.gameplay.players_count) if getattr(settings, f"device_p{idx+1}") == "Gamepad"]
                    if joystick_players:
                        if len(joystick_players) == 1:
                            p_idx = joystick_players[0]
                        else:
                            if event.joy < len(joystick_players):
                                p_idx = joystick_players[event.joy]
                            else:
                                continue
                        p_num = p_idx + 1
                        gp_settings = getattr(settings, f"gamepad_p{p_num}", {})
                            
                        for dir_name in gp_settings.keys():
                            map_val = gp_settings.get(dir_name)
                            if isinstance(map_val, dict) and map_val.get("type") == "axis":
                                target_axis = map_val.get("axis_idx")
                                if event.axis == target_axis:
                                    target_sign = map_val.get("sign")
                                    is_active = (axis_val * target_sign > 0.5)
                                    self.process_gamepad_gameplay_input(p_idx, dir_name, is_active)
                continue

            # --- EDITOR STATE EVENT HANDLING ---
            if self.state == "EDITOR":
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        # Clear selection if active
                        if self.editor.selection_start is not None or self.editor.selection_end is not None:
                            self.editor.selection_start = None
                            self.editor.selection_end = None
                            sound_helper.play_back()
                        else:
                            if self.editor.playing:
                                self.editor.toggle_play()
                            
                            pygame.mixer.music.stop()
                            
                            # Save current song details to re-select
                            current_filename = self.editor.song_filename
                            final_diff = self.editor.difficulty
                            self.editor = None
                            sound_helper.play_back()
                            
                            # Re-scan songs to update stats/metadata instantly
                            self.scan_songs()
                            for idx, s in enumerate(self.songs_list):
                                if s["filename"] == current_filename:
                                    self.song_index = idx
                                    break
                                    
                            self.update_difficulties_list()
                            if final_diff in self.difficulties:
                                self.difficulty_index = self.difficulties.index(final_diff)
                            self.state = "SONG_SELECT"
                    else:
                        self.editor.handle_key_down(event)
                elif event.type == pygame.KEYUP:
                    self.editor.handle_key_up(event.key)
                continue

            # --- PROFILE CREATION STATE EVENT HANDLING ---
            if self.state == "PROFILE_CREATION":
                if event.type == pygame.KEYDOWN:
                    if event.key in [pygame.K_RETURN, pygame.K_KP_ENTER]:
                        name = self.profile_creation_name.strip()
                        if name:
                            avatar_id = AVATARS[self.profile_creation_avatar_idx]["id"]
                            profile_manager.create_profile(name, avatar_id)
                            profile_manager.load()
                            sound_helper.play_select()
                            self.state = "TITLE"
                            self.title_index = 0
                    elif event.key == pygame.K_BACKSPACE:
                        self.profile_creation_name = self.profile_creation_name[:-1]
                        sound_helper.play_select()
                    elif event.key == pygame.K_TAB:
                        self.profile_creation_avatar_idx = (self.profile_creation_avatar_idx + 1) % len(AVATARS)
                        sound_helper.play_select()
                    elif event.unicode:
                        if len(self.profile_creation_name) < 15 and (event.unicode.isalnum() or event.unicode in " _-"):
                            self.profile_creation_name += event.unicode
                            sound_helper.play_select()
                continue

            # --- PROFILE STATS STATE EVENT HANDLING ---
            if self.state == "PROFILE_STATS":
                if event.type == pygame.KEYDOWN:
                    if event.key in [pygame.K_ESCAPE, pygame.K_BACKSPACE]:
                        self.trigger_back()
                    elif event.key in [pygame.K_LEFT, pygame.K_a]:
                        tabs = ["stats", "scores", "achievements"]
                        curr_idx = tabs.index(self.profile_tab)
                        self.profile_tab = tabs[(curr_idx - 1) % len(tabs)]
                        self.profile_scroll_idx = 0
                        sound_helper.play_select()
                    elif event.key in [pygame.K_RIGHT, pygame.K_d]:
                        tabs = ["stats", "scores", "achievements"]
                        curr_idx = tabs.index(self.profile_tab)
                        self.profile_tab = tabs[(curr_idx + 1) % len(tabs)]
                        self.profile_scroll_idx = 0
                        sound_helper.play_select()
                    elif event.key in [pygame.K_UP, pygame.K_w]:
                        self.profile_scroll_idx = max(0, self.profile_scroll_idx - 1)
                        sound_helper.play_select()
                    elif event.key in [pygame.K_DOWN, pygame.K_s]:
                        self.profile_scroll_idx += 1
                        sound_helper.play_select()
                continue

            # --- LOBBY INLINE EDIT STATE EVENT HANDLING (INTERCEPT BEFORE INPUT MANAGER) ---
            if self.state == "LOBBY" and getattr(self, "lobby_edit_mode", None) is not None:
                if event.type == pygame.KEYDOWN:
                    if event.key in [pygame.K_RETURN, pygame.K_KP_ENTER]:
                        try:
                            val = int(self.lobby_edit_buffer) if self.lobby_edit_buffer else 0
                        except ValueError:
                            val = 0
                        total_m = self.get_selected_song_total_measures()
                        if self.lobby_edit_mode == "practice_start_measure":
                            val = max(0, min(total_m, val))
                            self.practice_start_measure = val
                            if self.practice_start_measure >= self.practice_end_measure:
                                self.practice_end_measure = min(total_m, self.practice_start_measure + 1)
                        elif self.lobby_edit_mode == "practice_end_measure":
                            val = max(self.practice_start_measure + 1, min(total_m, val))
                            self.practice_end_measure = val
                        self.lobby_edit_mode = None
                        sound_helper.play_select()
                    elif event.key == pygame.K_ESCAPE:
                        self.lobby_edit_mode = None
                        sound_helper.play_back()
                    elif event.key == pygame.K_BACKSPACE:
                        self.lobby_edit_buffer = self.lobby_edit_buffer[:-1]
                        sound_helper.play_select()
                    elif event.unicode.isdigit():
                        if len(self.lobby_edit_buffer) < 5:
                            self.lobby_edit_buffer += event.unicode
                            sound_helper.play_select()
                continue

            # --- REMAP STATE EVENT HANDLING (INTERCEPT BEFORE INPUT MANAGER) ---
            if self.state == "REMAP":
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    if getattr(self, "active_remap_cell", None) is not None:
                        input_manager.cancel_remap()
                        self.active_remap_cell = None
                        sound_helper.play_back()
                    else:
                        input_manager.cancel_remap()
                        sound_helper.play_back()
                        self.state = getattr(self, "remap_return_state", "SETTINGS")
                    continue
                
                # Clear keybind if DELETE or BACKSPACE is pressed during active cell remap
                if getattr(self, "active_remap_cell", None) is not None and event.type == pygame.KEYDOWN and event.key in [pygame.K_DELETE, pygame.K_BACKSPACE]:
                    input_manager.cancel_remap()
                    direction, set_idx = self.active_remap_cell
                    p_num = int(self.remap_mode[1])
                    
                    if "gamepad" in self.remap_mode:
                        prop_name = f"gamepad_p{p_num}"
                        new_gp = getattr(settings, prop_name).copy()
                        new_gp[direction] = {} # Clear gamepad binding
                        setattr(settings, prop_name, new_gp)
                    else:
                        prop_name = f"keys_p{p_num}"
                        new_keys = getattr(settings, prop_name).copy()
                        if isinstance(new_keys[direction], list):
                            new_keys[direction][set_idx] = 0
                        else:
                            new_keys[direction] = [0, 0]
                        setattr(settings, prop_name, new_keys)
                        
                    self.active_remap_cell = None
                    sound_helper.play_select()
                    continue

            # Feed to input manager (abstracts keyboard and controller events)
            input_result = input_manager.handle_event(event)

            # --- SONG SELECT QUICK EDITOR SHORTCUT ---
            if self.state == "SONG_SELECT" and event.type == pygame.KEYDOWN and event.key == pygame.K_e:
                if self.display_list and self.song_index < len(self.display_list):
                    item = self.display_list[self.song_index]
                    if item["type"] == "song":
                        self.start_chart_editor()
                    continue

            # --- SONG SELECT QUICK DELETE SHORTCUT ---
            if self.state == "SONG_SELECT" and event.type == pygame.KEYDOWN and event.key == pygame.K_DELETE:
                if self.display_list and self.song_index < len(self.display_list):
                    item = self.display_list[self.song_index]
                    if item["type"] == "song":
                        selected_song = item["song"]
                        if selected_song["filename"] != "Retro_Beat.wav":
                            self.delete_song(selected_song)
                    continue

            # Toggle Fullscreen with F11
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                pygame.display.toggle_fullscreen()
                continue

            # Confirm and Back event detection
            is_confirm = False
            is_back = False
            
            if event.type == pygame.KEYDOWN:
                if event.key in [pygame.K_RETURN, pygame.K_SPACE]:
                    is_confirm = True
                elif event.key == pygame.K_ESCAPE:
                    is_back = True
            
            # Gamepad controls: button 0 (A) is confirm, button 1 (B) is back
            if event.type == pygame.JOYBUTTONDOWN:
                if event.button == 0:
                    is_confirm = True
                elif event.button == 1:
                    is_back = True

            if is_confirm:
                self.trigger_confirm()
                continue
                
            if is_back:
                self.trigger_back()
                continue

            if input_result:
                direction, is_down, is_keyboard, input_desc = input_result
                
                # Gameplay input needs both pressed (is_down=True) and released (is_down=False) events
                if self.state == "GAMEPLAY" and self.gameplay:
                    # Map direction string to index: left=0, down=1, up=2, right=3
                    dir_map = {"left": 0, "down": 1, "up": 2, "right": 3}
                    if direction in dir_map:
                        self.gameplay.trigger_input(dir_map[direction], is_down)
                else:
                    # Menus only trigger on DOWN press
                    if is_down:
                        self.trigger_direction(direction)

    def trigger_direction(self, direction):
        if self.state == "TITLE":
            if direction == "up":
                self.title_index = (self.title_index - 1) % len(self.title_options)
                sound_helper.play_select()
            elif direction == "down":
                self.title_index = (self.title_index + 1) % len(self.title_options)
                sound_helper.play_select()
                
        elif self.state == "MODE_SELECT":
            if direction == "left":
                self.mode_index = (self.mode_index - 1) % len(self.mode_options)
                sound_helper.play_select()
            elif direction == "right":
                self.mode_index = (self.mode_index + 1) % len(self.mode_options)
                sound_helper.play_select()
                
        elif self.state == "LOBBY":
            items = self.get_lobby_items()
            if items:
                if direction == "up":
                    self.lobby_selection_index = (self.lobby_selection_index - 1) % len(items)
                    sound_helper.play_select()
                elif direction == "down":
                    self.lobby_selection_index = (self.lobby_selection_index + 1) % len(items)
                    sound_helper.play_select()
                elif direction == "left":
                    self.adjust_lobby_setting(-1)
                elif direction == "right":
                    self.adjust_lobby_setting(1)
                
        elif self.state == "SONG_SELECT":
            if not self.display_list:
                return
            if direction == "up":
                self.song_index = (self.song_index - 1) % len(self.display_list)
                self.update_difficulties_list()
                sound_helper.play_select()
            elif direction == "down":
                self.song_index = (self.song_index + 1) % len(self.display_list)
                self.update_difficulties_list()
                sound_helper.play_select()
            elif direction == "left":
                self.difficulty_index = (self.difficulty_index - 1) % len(self.difficulties)
                sound_helper.play_select()
            elif direction == "right":
                self.difficulty_index = (self.difficulty_index + 1) % len(self.difficulties)
                sound_helper.play_select()
                
        elif self.state == "SETTINGS":
            opts = self.get_settings_options()
            if direction == "up":
                self.settings_index = (self.settings_index - 1) % len(opts)
                while opts[self.settings_index].startswith("---"):
                    self.settings_index = (self.settings_index - 1) % len(opts)
                sound_helper.play_select()
            elif direction == "down":
                self.settings_index = (self.settings_index + 1) % len(opts)
                while opts[self.settings_index].startswith("---"):
                    self.settings_index = (self.settings_index + 1) % len(opts)
                sound_helper.play_select()
            elif direction == "left":
                self.adjust_setting(-1)
            elif direction == "right":
                self.adjust_setting(1)
                
            # Scroll active index into view (maximum 12 visible items)
            if self.settings_index < self.settings_scroll_y:
                self.settings_scroll_y = self.settings_index
            elif self.settings_index >= self.settings_scroll_y + 12:
                self.settings_scroll_y = self.settings_index - 11

    def trigger_confirm(self):
        if self.state == "TITLE":
            opt = self.title_options[self.title_index]
            if opt == "PLAY":
                sound_helper.play_select()
                self.state = "MODE_SELECT"
                self.mode_index = 0
            elif opt == "PROFILE & STATS":
                sound_helper.play_select()
                self.state = "PROFILE_STATS"
                self.profile_tab = "stats"
                self.profile_scroll_idx = 0
            elif opt == "SETTINGS":
                sound_helper.play_select()
                self.state = "SETTINGS"
            elif opt == "EXIT":
                self.running = False
                
        elif self.state == "MODE_SELECT":
            sound_helper.play_select()
            mode = self.mode_options[self.mode_index]
            if mode == "PRACTICE":
                settings.game_mode = "Practice"
                settings.players = 1
                self.state = "SONG_SELECT"
                self.build_display_list()
                self.song_index = min(self.song_index, len(self.display_list) - 1) if self.display_list else 0
                self.update_difficulties_list()
            else:
                self.lobby_selection_index = 0
                self.state = "LOBBY"
            
        elif self.state == "LOBBY":
            items = self.get_lobby_items()
            if self.lobby_selection_index < len(items):
                item = items[self.lobby_selection_index]
                if item["type"] == "link":
                    sound_helper.play_select()
                    self.start_key_remapping(item["action_mode"])
                elif item["type"] == "value" and item["key"] in ["practice_start_measure", "practice_end_measure"]:
                    # Toggle inline editing on confirm click / enter
                    sound_helper.play_select()
                    self.lobby_edit_mode = item["key"]
                    self.lobby_edit_buffer = str(getattr(self, item["key"]))
                elif item["type"] == "action" and item["action"] == "start":
                    # Save setup settings
                    mode = self.mode_options[self.mode_index]
                    sound_helper.play_select()
                    
                    if mode == "PRACTICE":
                        self.start_gameplay_from_overlay()
                    else:
                        if mode == "SOLO":
                            settings.game_mode = "Solo"
                            settings.players = 1
                        elif mode == "CO-OP":
                            settings.game_mode = "Co-Op"
                            settings.players = 2
                        elif mode == "VERSUS":
                            settings.game_mode = "Versus"
                            settings.players = 2
                        elif mode == "FNF":
                            settings.game_mode = "FNF"
                            settings.players = 2
                            
                        # Also configure devices
                        active_match = self.fnf_match_types[self.fnf_match_type_index] if mode == "FNF" else ""
                        p1_is_human = True if mode != "FNF" else ("Human" in active_match.split(" vs ")[0])
                        p2_is_human = True if mode != "FNF" else ("Human" in active_match.split(" vs ")[1])
                        
                        if not p1_is_human:
                            settings.device_p1 = "Keyboard"
                        if not p2_is_human:
                            settings.device_p2 = "Keyboard"
                            
                        # Proceed to Song Select
                        self.state = "SONG_SELECT"
                        self.build_display_list()
                        self.song_index = min(self.song_index, len(self.display_list) - 1) if self.display_list else 0
                        self.update_difficulties_list()
                    
        elif self.state == "SONG_SELECT":
            if not self.display_list or self.song_index >= len(self.display_list):
                return
                
            item = self.display_list[self.song_index]
            if item["type"] == "group":
                grp_name = item["name"]
                if grp_name in self.expanded_groups:
                    self.expanded_groups.remove(grp_name)
                else:
                    self.expanded_groups.add(grp_name)
                self.build_display_list()
                sound_helper.play_select()
                # Ensure song_index is clamped safely in new list
                self.song_index = min(self.song_index, len(self.display_list) - 1)
                self.update_difficulties_list()
            elif item["type"] == "song":
                selected_song = item["song"]
                selected_diff = self.difficulties[self.difficulty_index]
                chk_diff = "Medium" if selected_diff == "Dynamic" else selected_diff
                
                # Check if the chart is empty/uncreated
                if len(selected_song["charts"].get(chk_diff, [])) == 0:
                    sound_helper.play_back()
                    self.warning_notification = "You need to create and save the song level first!"
                    self.warning_notification_timer = 3.0
                    return
                    
                sound_helper.play_select()
                self.p1_diff_index = self.difficulty_index
                self.p2_diff_index = self.difficulty_index
                
                if settings.game_mode == "Practice":
                    self.lobby_selection_index = 0
                    self.state = "LOBBY"
                    total_m = self.get_selected_song_total_measures()
                    self.practice_start_measure = 0
                    self.practice_end_measure = total_m
                else:
                    if settings.players == 1:
                        self.start_gameplay_from_overlay()
                    else:
                        self.p1_ready = False
                        self.p2_ready = False if settings.players == 2 else True
                        self.state = "DIFFICULTY_SELECT_OVERLAY"
            else:
                self.trigger_song_upload()
                
        elif self.state == "SETTINGS":
            opts = self.get_settings_options()
            opt = opts[self.settings_index]
            if opt == "BACK":
                sound_helper.play_back()
                self.state = "TITLE"
            elif opt == "CALIBRATE LATENCY":
                sound_helper.play_select()
                self.start_calibration()
            elif "REMAP" in opt:
                p_num = int(opt[7])
                sound_helper.play_select()
                if "KEYBOARD" in opt:
                    self.start_key_remapping(f"p{p_num}_ddr")
                elif "GAMEPAD" in opt:
                    self.start_key_remapping(f"p{p_num}_gamepad")
            else:
                self.adjust_setting(1)
                
        elif self.state == "RESULTS":
            # Confirm returns to Song Select
            sound_helper.play_select()
            self.state = "SONG_SELECT"
            
        elif self.state == "GAMEPLAY" and self.gameplay:
            if self.gameplay.paused:
                # SPACE/ENTER resumes gameplay
                self.gameplay.toggle_pause()

    def trigger_back(self):
        if self.state == "MODE_SELECT":
            sound_helper.play_back()
            self.state = "TITLE"
        elif self.state == "LOBBY":
            sound_helper.play_back()
            if settings.game_mode == "Practice":
                self.state = "SONG_SELECT"
            else:
                self.state = "MODE_SELECT"
        elif self.state == "SONG_SELECT":
            sound_helper.play_back()
            if settings.game_mode == "Practice":
                self.state = "MODE_SELECT"
            else:
                self.state = "LOBBY"
        elif self.state == "PROFILE_STATS":
            sound_helper.play_back()
            self.state = "TITLE"
        elif self.state == "SETTINGS":
            sound_helper.play_back()
            self.state = "TITLE"
        elif self.state == "RESULTS":
            sound_helper.play_back()
            self.state = "SONG_SELECT"
        elif self.state == "GAMEPLAY" and self.gameplay:
            if self.gameplay.paused:
                # If paused, ESC exits to song selection
                pygame.mixer.music.stop()
                self.gameplay.clean_up()
                self.gameplay = None
                sound_helper.play_back()
                self.state = "SONG_SELECT"
            else:
                # Pause gameplay
                self.gameplay.toggle_pause()

    def start_calibration(self):
        self.state = "CALIBRATION"
        self.calib_bpm = 100
        self.calib_beat_interval = 60.0 / self.calib_bpm # 0.6 seconds
        self.calib_start_time = time.time()
        self.calib_taps = []
        self.calib_flash = 0.0
        self.calib_last_beat_index = -1
        self.calib_msg = "Listen to the metronome and TAP exactly on the beat!"

    def register_calibration_tap(self):
        t_elapsed = time.time() - self.calib_start_time
        beat_idx = round(t_elapsed / self.calib_beat_interval)
        expected_t = beat_idx * self.calib_beat_interval
        diff = t_elapsed - expected_t
        if abs(diff) < self.calib_beat_interval * 0.5:
            self.calib_taps.append(diff)
            if len(self.calib_taps) > 12:
                self.calib_taps.pop(0) # Keep last 12 taps
            sound_helper.play_hit()
            self.calib_flash = 0.8 # Visual flash feedback

    def is_dark_theme(self, theme):
        return theme in ["DDR-Retro", "Retro-Pixel", "Futuristic", "Neko-Pixel"]

    def get_key_name_str(self, key_val):
        if not key_val or key_val == 0:
            return "---"
        if isinstance(key_val, dict):
            t = key_val.get("type")
            if t == "button":
                return f"BTN {key_val.get('id')}"
            elif t == "hat":
                val = key_val.get("value")
                dir_desc = "LEFT" if val[0] < 0 else "RIGHT" if val[0] > 0 else "DOWN" if val[1] < 0 else "UP"
                return f"DPAD {dir_desc}"
            elif t == "axis":
                return f"AXIS {key_val.get('axis_idx')}{'+' if key_val.get('sign', 1) > 0 else '-'}"
            return "BIND"
        
        name = pygame.key.name(key_val).upper()
        replacements = {
            "LEFT ARROW": "LEFT",
            "RIGHT ARROW": "RIGHT",
            "UP ARROW": "UP",
            "DOWN ARROW": "DOWN",
            "LEFT SUPER": "LWIN",
            "RIGHT SUPER": "RWIN",
            "LEFT CTRL": "LCTRL",
            "RIGHT CTRL": "RCTRL",
            "LEFT SHIFT": "LSHIFT",
            "RIGHT SHIFT": "RSHIFT",
            "LEFT ALT": "LALT",
            "RIGHT ALT": "RALT",
            "CAPS LOCK": "CAPS",
            "PAGE UP": "PGUP",
            "PAGE DOWN": "PGDN",
            "KEYPAD 4": "NUM 4",
            "KEYPAD 5": "NUM 5",
            "KEYPAD 6": "NUM 6",
            "KEYPAD 8": "NUM 8",
            "KEYPAD ENTER": "NUM ENTER",
        }
        for k, v in replacements.items():
            if k in name:
                name = name.replace(k, v)
        return name

    def update_difficulties_list(self):
        if not self.display_list or self.song_index >= len(self.display_list):
            self.difficulties = ["Easy", "Medium", "Hard", "Harder", "Crazy", "Dynamic", "Custom"]
            self.difficulty_index = self.difficulty_index % len(self.difficulties)
            return
            
        item = self.display_list[self.song_index]
        if item["type"] != "song":
            self.difficulties = ["Easy", "Medium", "Hard", "Harder", "Crazy", "Dynamic", "Custom"]
            self.difficulty_index = self.difficulty_index % len(self.difficulties)
            return
            
        selected_song = item["song"]
        base_diffs = ["Easy", "Medium", "Hard", "Harder", "Crazy", "Dynamic"]
        charts = selected_song.get("charts", {})
        custom_diffs = [k for k in charts.keys() if k not in base_diffs]
        
        def sort_custom_key(val):
            parts = val.split()
            if len(parts) < 2:
                return 999
            try:
                return int(parts[1])
            except ValueError:
                return 999
        custom_diffs.sort(key=sort_custom_key)
        
        self.difficulties = base_diffs + custom_diffs
        self.difficulty_index = self.difficulty_index % len(self.difficulties)

    def get_settings_options(self):
        opts = []
        # Gameplay Settings
        opts.append("--- GAMEPLAY SETTINGS ---")
        opts.append("PLAYERS")
        opts.append("GAME MODE")
        
        # Add dynamic player settings based on active players count
        for p in range(1, settings.players + 1):
            opts.append(f"--- PLAYER {p} CONFIG ---")
            opts.append(f"P{p} CHARACTER")
            
            allowed = ["Keyboard", "Gamepad"]
            curr_dev = getattr(settings, f"device_p{p}", "Keyboard")
            if curr_dev not in allowed:
                setattr(settings, f"device_p{p}", allowed[0])
            
            opts.append(f"P{p} DEVICE")
                
            dev = getattr(settings, f"device_p{p}", "Keyboard")
            if dev == "Keyboard":
                opts.append(f"REMAP P{p} KEYBOARD")
            elif dev == "Gamepad":
                opts.append(f"REMAP P{p} GAMEPAD")
                
        # UI Settings
        opts.append("--- UI & TIMING ---")
        opts.append("THEME")
        opts.append("AUDIO OFFSET")
        opts.append("CALIBRATE LATENCY")
        opts.append("PROPORTIONAL SCORING")
        opts.append("MISS PENALTY")
        opts.append("PLAYBACK SPEED")
        
        # Sound/Graphics Settings
        opts.append("--- SOUND & GRAPHICS ---")
        opts.append("MUSIC VOLUME")
        opts.append("SFX VOLUME")
        opts.append("ASSIST TICK")
        opts.append("SHOW CONSOLE")
        
        opts.append("BACK")
        return opts

    def get_player_char(self, p_num):
        if p_num == 1: return settings.character
        elif p_num == 2: return settings.character_p2
        elif p_num == 3: return settings.character_p3
        elif p_num == 4: return settings.character_p4
        return "Beat Bot"
        
    def set_player_char(self, p_num, val):
        if p_num == 1: settings.character = val
        elif p_num == 2: settings.character_p2 = val
        elif p_num == 3: settings.character_p3 = val
        elif p_num == 4: settings.character_p4 = val
        
    def get_player_dev(self, p_num):
        dev = getattr(settings, f"device_p{p_num}", "Keyboard")
        if dev == "Gamepad":
            gamepad_players = []
            for p in range(1, settings.players + 1):
                if getattr(settings, f"device_p{p}") == "Gamepad":
                    gamepad_players.append(p)
            if p_num in gamepad_players:
                gamepad_idx = gamepad_players.index(p_num)
                if gamepad_idx < len(input_manager.joysticks):
                    joy_name = input_manager.joysticks[gamepad_idx].get_name()
                    if len(joy_name) > 20:
                        joy_name = joy_name[:17] + "..."
                    return f"Gamepad ({joy_name})"
            return "Gamepad (Not Connected)"
        elif dev == "Keyboard":
            return "Keyboard"
        return dev

    def set_player_dev(self, p_num, val):
        setattr(settings, f"device_p{p_num}", val)

    def apply_console_visibility(self):
        if getattr(sys, "frozen", False) and sys.platform == "win32":
            try:
                import ctypes
                hwnd = ctypes.windll.kernel32.GetConsoleWindow()
                if hwnd:
                    if settings.show_console:
                        ctypes.windll.user32.ShowWindow(hwnd, 5) # SW_SHOW
                    else:
                        ctypes.windll.user32.ShowWindow(hwnd, 0) # SW_HIDE
            except Exception as e:
                print(f"Error adjusting console visibility: {e}")

    def adjust_setting(self, dir_val):
        opts = self.get_settings_options()
        opt = opts[self.settings_index]
        
        if opt == "MUSIC VOLUME":
            settings.music_volume = max(0.0, min(1.0, settings.music_volume + dir_val * 0.1))
            sound_helper.play_select()
        elif opt == "SFX VOLUME":
            settings.sfx_volume = max(0.0, min(1.0, settings.sfx_volume + dir_val * 0.1))
            sound_helper.update_volumes()
            sound_helper.play_select()
        elif opt == "SHOW CONSOLE":
            settings.show_console = not settings.show_console
            self.apply_console_visibility()
            sound_helper.play_select()
        elif opt == "ASSIST TICK":
            settings.assist_tick = not settings.assist_tick
            sound_helper.play_select()
        elif opt == "THEME":
            from theme_manager import theme_manager
            all_themes = ["DDR-Retro", "Minimalist", "Retro-Pixel", "Futuristic", "Kawaii-Pink", "Neko-Pixel"]
            custom_theme_names = list(theme_manager.custom_themes.keys())
            all_themes += custom_theme_names
            
            unlocked = ["DDR-Retro"]
            if profile_manager.exists():
                unlocked = profile_manager.profile.get("unlocked_themes", ["DDR-Retro"])
            themes = [t for t in all_themes if t in unlocked or t == "DDR-Retro" or t in custom_theme_names]
            curr_idx = themes.index(settings.theme) if settings.theme in themes else 0
            settings.theme = themes[(curr_idx + dir_val) % len(themes)]
            sound_helper.play_select()
        elif opt == "AUDIO OFFSET":
            settings.audio_offset = max(-0.5, min(0.5, settings.audio_offset + dir_val * 0.005))
            sound_helper.play_select()
        elif opt == "PROPORTIONAL SCORING":
            settings.proportional_scoring = not getattr(settings, "proportional_scoring", False)
            sound_helper.play_select()
        elif opt == "MISS PENALTY":
            penalties = [0, 50, 100, 200, 500]
            curr_pen = getattr(settings, "miss_penalty", 0)
            if curr_pen not in penalties:
                curr_idx = 0
            else:
                curr_idx = penalties.index(curr_pen)
            settings.miss_penalty = penalties[(curr_idx + dir_val) % len(penalties)]
            sound_helper.play_select()
        elif opt == "PLAYBACK SPEED":
            speeds = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 4.0, 5.0]
            curr_spd = getattr(settings, "playback_speed", 1.0)
            if curr_spd not in speeds:
                curr_idx = 2
            else:
                curr_idx = speeds.index(curr_spd)
            settings.playback_speed = speeds[(curr_idx + dir_val) % len(speeds)]
            sound_helper.play_select()
        elif opt == "PLAYERS":
            settings.players = ((settings.players - 1 + dir_val) % 4) + 1
            sound_helper.play_select()
        elif opt == "GAME MODE":
            modes = ["Solo", "Co-Op", "Versus", "FNF"]
            curr_idx = modes.index(settings.game_mode) if settings.game_mode in modes else 0
            settings.game_mode = modes[(curr_idx + dir_val) % len(modes)]
            sound_helper.play_select()
        elif opt.startswith("P") and "CHARACTER" in opt:
            p_num = int(opt[1])
            curr_char = self.get_player_char(p_num)
            curr_idx = self.characters_list.index(curr_char) if curr_char in self.characters_list else 0
            new_char = self.characters_list[(curr_idx + dir_val) % len(self.characters_list)]
            self.set_player_char(p_num, new_char)
            sound_helper.play_select()
        elif opt.startswith("P") and "DEVICE" in opt:
            p_num = int(opt[1])
            devices = ["Keyboard", "Gamepad"]
            curr_dev = getattr(settings, f"device_p{p_num}", "Keyboard")
            if curr_dev not in devices:
                curr_dev = devices[0]
            curr_idx = devices.index(curr_dev)
            new_dev = devices[(curr_idx + dir_val) % len(devices)]
            self.set_player_dev(p_num, new_dev)
            sound_helper.play_select()

    def delete_song(self, song):
        """Deletes the audio file and JSON chart map for a song."""
        if song.get("filename") == "Retro_Beat.wav":
            print("Cannot delete default song.")
            return
        try:
            # Release Pygame lock on Windows prior to file removal
            pygame.mixer.music.stop()
            try:
                pygame.mixer.music.unload()
            except:
                pass
            try:
                pygame.mixer.music.load(os.path.join(settings.SONGS_DIR, "Retro_Beat.wav"))
            except:
                pass
                
            wav_path = os.path.join(settings.SONGS_DIR, song["filename"])
            json_path = os.path.join(settings.SONGS_DIR, song["filename"].rsplit(".", 1)[0] + ".json")
            
            if os.path.exists(wav_path):
                os.remove(wav_path)
            if os.path.exists(json_path):
                os.remove(json_path)
                
            sound_helper.play_back()
            self.scan_songs()
            self.build_display_list()
            
            if self.display_list:
                self.song_index = min(self.song_index, len(self.display_list) - 1)
            else:
                self.song_index = 0
            self.update_difficulties_list()
                
            print(f"Successfully deleted song: {song['title']}")
        except Exception as e:
            print(f"Error deleting song: {e}")

    def load_profiles_db(self):
        profile_path = os.path.join(settings.BASE_DIR, "profiles.json")
        default_db = {
            "play_count": 0,
            "hours_played": 0.0,
            "total_steps": 0,
            "overall_accuracy": 0.0,
            "unlocked_achievements": []
        }
        if os.path.exists(profile_path):
            try:
                with open(profile_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading profiles: {e}")
        return default_db

    def save_profiles_db(self, db):
        profile_path = os.path.join(settings.BASE_DIR, "profiles.json")
        try:
            with open(profile_path, "w", encoding="utf-8") as f:
                json.dump(db, f, indent=4)
        except Exception as e:
            print(f"Error saving profiles: {e}")

    def update_high_score(self, song_metadata, difficulty, results):
        """Updates high scores locally in the song's JSON file."""
        total_notes = results["perfects"] + results["greats"] + results["goods"] + results["misses"]
        
        # Calculate grade & badges
        badges = []
        if total_notes > 0:
            if results["perfects"] == total_notes:
                badges.append("🐾 ALL PERFECT")
                grade = "SSS"
            elif results["misses"] == 0:
                if results["goods"] == 0:
                    badges.append("🐾 FULL COMBO")
                    grade = "S"
                else:
                    badges.append("🐾 NO MISSES")
                    grade = "A"
            else:
                accuracy = (results["perfects"] * 100 + results["greats"] * 75 + results["goods"] * 40) / total_notes
                if accuracy >= 95.0:
                    grade = "S"
                elif accuracy >= 90.0:
                    grade = "A"
                elif accuracy >= 80.0:
                    grade = "B"
                elif accuracy >= 70.0:
                    grade = "C"
                elif accuracy >= 60.0:
                    grade = "D"
                else:
                    grade = "F"
        else:
            grade = "F"
            
        results["grade"] = grade
        results["badges"] = badges
        
        if "high_scores" not in song_metadata:
            song_metadata["high_scores"] = {}
            
        current_record = song_metadata["high_scores"].get(difficulty)
        is_new_record = False
        if current_record is None or results["score"] > current_record.get("score", 0):
            is_new_record = True
            song_metadata["high_scores"][difficulty] = {
                "score": results["score"],
                "max_combo": results["max_combo"],
                "grade": grade,
                "perfects": results["perfects"],
                "greats": results["greats"],
                "goods": results["goods"],
                "misses": results["misses"],
                "badges": badges
            }
            
            # Save back to JSON
            json_path = os.path.join(settings.SONGS_DIR, song_metadata["filename"].rsplit(".", 1)[0] + ".json")
            try:
                with open(json_path, "w") as f:
                    json.dump(song_metadata, f, indent=4)
                print(f"New high score saved for {song_metadata['title']} [{difficulty}]!")
            except Exception as e:
                print(f"Error saving high score: {e}")
                
        results["is_new_record"] = is_new_record
        
        # --- PROFILE & ACHIEVEMENTS ENGINE ---
        db = self.load_profiles_db()
        db["play_count"] += 1
        db["total_steps"] += results["perfects"] + results["greats"] + results["goods"]
        db["hours_played"] += float(results.get("duration", 60.0) / 3600.0)
        
        curr_acc = (results["perfects"] * 100.0 + results["greats"] * 75.0 + results["goods"] * 40.0) / max(1, total_notes)
        db["overall_accuracy"] = float(round((db["overall_accuracy"] * (db["play_count"] - 1) + curr_acc) / db["play_count"], 2))
        
        # Check achievements
        new_unlocked = []
        
        # Achievement: Laser Pointer (Hit 100 Perfects in a single run)
        if results["perfects"] >= 100 and "Laser Pointer" not in db["unlocked_achievements"]:
            new_unlocked.append("Laser Pointer")
            
        # Achievement: 3 AM Energy (Play a song between 12 AM and 4 AM)
        import datetime
        curr_hr = datetime.datetime.now().hour
        if curr_hr >= 0 and curr_hr < 4 and "3 AM Energy" not in db["unlocked_achievements"]:
            new_unlocked.append("3 AM Energy")
            
        # Achievement: Orange Cat (Played 10 songs in total)
        if db["play_count"] >= 10 and "Orange Cat" not in db["unlocked_achievements"]:
            new_unlocked.append("Orange Cat")
            
        # Achievement: Cat Nap (Paused gameplay for > 5 minutes in a song)
        if getattr(self, "last_gameplay_pause_duration", 0.0) > 300.0 and "Cat Nap" not in db["unlocked_achievements"]:
            new_unlocked.append("Cat Nap")
            
        # Achievement: Knocked Over the Water Glass (Missed the very last note of the song)
        if results.get("missed_last_note", False) and "Knocked Over the Water Glass" not in db["unlocked_achievements"]:
            new_unlocked.append("Knocked Over the Water Glass")
            
        if new_unlocked:
            db["unlocked_achievements"].extend(new_unlocked)
            results["unlocked_achievements"] = new_unlocked
            self.save_profiles_db(db)
            print(f"Unlocked Achievements: {new_unlocked}!")
        else:
            self.save_profiles_db(db)

    def start_chart_editor(self):
        """Launches the chart editor for the selected song and difficulty."""
        if self.display_list and self.song_index < len(self.display_list):
            item = self.display_list[self.song_index]
            if item["type"] != "song":
                return
            sound_helper.play_select()
            selected_song = item["song"]
            selected_diff = self.difficulties[self.difficulty_index]
            if selected_diff == "Dynamic":
                selected_diff = "Medium"
                
            # Initialize empty chart list if not present (e.g. for new Custom difficulty)
            if selected_diff not in selected_song["charts"]:
                selected_song["charts"][selected_diff] = []
                
            self.editor = ChartEditor(selected_song, selected_diff)
            self.state = "EDITOR"

    def trigger_song_upload(self):
        """Triggers file explorer upload and background thread analysis for multiple files."""
        sound_helper.play_select()
        
        # Run filedialog in native OS picker
        selected_files = self.open_file_picker_dialog()
        if not selected_files:
            print("Song upload canceled.")
            return

        # Start analyzing state
        self.state = "ANALYZING"
        self.analysis_error = None
        self.analysis_success_data = None
        self.analysis_progress_text = "Preparing file import queue..."
        
        # Start background analysis thread
        def thread_task():
            success_count = 0
            for idx, selected_file in enumerate(selected_files):
                is_zip = selected_file.lower().endswith(".zip")
                filename = os.path.basename(selected_file)
                sanitized_filename = filename.replace(" ", "_")
                dest_path = os.path.join(settings.SONGS_DIR, sanitized_filename)
                output_json = dest_path.rsplit(".", 1)[0] + ".json"
                
                self.analysis_progress_text = f"[{idx+1}/{len(selected_files)}] Copying {filename}..."
                
                if not is_zip:
                    try:
                        shutil.copy(selected_file, dest_path)
                    except Exception as e:
                        print(f"Error copying song file: {e}")
                        continue

                temp_dir = None
                try:
                    if is_zip:
                        self.analysis_progress_text = f"[{idx+1}/{len(selected_files)}] Extracting ZIP..."
                        temp_dir = os.path.join(settings.SONGS_DIR, f"temp_unzip_{int(time.time())}_{idx}")
                        os.makedirs(temp_dir, exist_ok=True)
                        
                        with zipfile.ZipFile(selected_file, 'r') as zip_ref:
                            zip_ref.extractall(temp_dir)
                            
                        # Find audio and chart files recursively
                        chart_file = None
                        audio_file = None
                        for root_dir, dirs, files in os.walk(temp_dir):
                            for f in files:
                                f_lower = f.lower()
                                if f_lower.endswith((".sm", ".ssc")):
                                    if not chart_file or f_lower.endswith(".sm"):
                                        chart_file = os.path.join(root_dir, f)
                                elif f_lower.endswith((".mp3", ".wav", ".ogg")):
                                    audio_file = os.path.join(root_dir, f)
                                    
                        if not audio_file:
                            raise ValueError("No valid audio file (MP3/WAV/OGG) found inside ZIP.")
                            
                        audio_filename = os.path.basename(audio_file).replace(" ", "_")
                        dest_audio_path = os.path.join(settings.SONGS_DIR, audio_filename)
                        dest_json_path = dest_audio_path.rsplit(".", 1)[0] + ".json"
                        
                        shutil.copy(audio_file, dest_audio_path)
                        
                        if chart_file:
                            self.analysis_progress_text = f"[{idx+1}/{len(selected_files)}] Parsing Stepmania chart..."
                            song_data = SMParser.parse(chart_file)
                            if song_data:
                                song_data["filename"] = audio_filename
                                try:
                                    import miniaudio
                                    info = miniaudio.get_file_info(dest_audio_path)
                                    song_data["duration"] = info.duration
                                except Exception:
                                    song_data["duration"] = 120.0
                                    
                                with open(dest_json_path, "w") as f_out:
                                    json.dump(song_data, f_out, indent=4)
                                    
                                self.analysis_success_data = song_data
                                success_count += 1
                                print(f"Successfully imported Stepmania song from ZIP: {song_data['title']}")
                            else:
                                print("Stepmania parser returned None. Falling back to auto-analyzer...")
                                self.analysis_progress_text = f"[{idx+1}/{len(selected_files)}] Auto-analyzing audio..."
                                song_data = self.analyzer.analyze_song(dest_audio_path, dest_json_path)
                                self.analysis_success_data = song_data
                                success_count += 1
                        else:
                            self.analysis_progress_text = f"[{idx+1}/{len(selected_files)}] Auto-analyzing audio..."
                            song_data = self.analyzer.analyze_song(dest_audio_path, dest_json_path)
                            self.analysis_success_data = song_data
                            success_count += 1
                    else:
                        self.analysis_progress_text = f"[{idx+1}/{len(selected_files)}] Auto-analyzing audio..."
                        song_data = self.analyzer.analyze_song(dest_path, output_json)
                        self.analysis_success_data = song_data
                        success_count += 1
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    print(f"Error importing {filename}: {e}")
                    self.analysis_error = f"Error importing {filename}: {e}"
                finally:
                    if temp_dir and os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir, ignore_errors=True)
            
            # Post-import scan refresh
            self.scan_songs()
            self.update_difficulties_list()
            
            if success_count > 0:
                self.analysis_progress_text = f"Successfully imported {success_count} songs!"
                time.sleep(1.5)
                self.state = "SONG_SELECT"
            else:
                self.analysis_progress_text = "Import failed."
                
        self.analysis_thread = threading.Thread(target=thread_task)
        self.analysis_thread.start()

    def open_file_picker_dialog(self):
        # 1. Native macOS file picker via AppleScript (avoids Tkinter crashes / thread deadlocks on macOS)
        if sys.platform == "darwin":
            try:
                ascript = (
                    'tell application "System Events"\n'
                    '    activate\n'
                    '    set chosenFiles to choose file with prompt "Select Song or Stepmania Zips (MP3/WAV/ZIP)" '
                    'of type {"mp3", "wav", "ogg", "zip"} with multiple selections allowed without invisibles\n'
                    '    set outPaths to {}\n'
                    '    repeat with aFile in chosenFiles\n'
                    '        set end of outPaths to POSIX path of aFile\n'
                    '    end repeat\n'
                    '    set AppleScript\'s text item delimiters to ASCII character 10\n'
                    '    return outPaths as text\n'
                    'end tell'
                )
                res = subprocess.run(
                    ["osascript", "-e", ascript],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                if res.returncode == 0 and res.stdout.strip():
                    paths = [p.strip() for p in res.stdout.strip().split("\n") if p.strip()]
                    return paths
                return None
            except subprocess.TimeoutExpired:
                print("Native macOS file picker timed out.")
                return None
            except Exception as err:
                print(f"Error running native macOS file dialog: {err}")
                # Fall through to Tkinter fallback if AppleScript fails

        # 2. Windows / Linux file picker via Tkinter
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            file_paths = filedialog.askopenfilenames(
                title="Select Song or Stepmania Zips (MP3/WAV/ZIP)",
                filetypes=[
                    ("Supported Files", "*.mp3;*.wav;*.ogg;*.zip"),
                    ("Audio Files", "*.mp3;*.wav;*.ogg"),
                    ("Zip Files", "*.zip")
                ]
            )
            root.destroy()
            return file_paths
        except Exception as e:
            print(f"Error running native file dialog: {e}")
            return None

    def start_key_remapping(self, mode):
        self.remap_return_state = self.state
        self.state = "REMAP"
        self.remap_mode = mode  # "p1_ddr", "p2_ddr", "p3_ddr", "p4_ddr", "p1_gamepad", ...
        self.active_remap_cell = None
        self.remap_hover_cell = None
        self.remap_directions = ["left", "down", "up", "right"]

    def handle_remap_click(self, mx, my):
        w, h = SCREEN_WIDTH, SCREEN_HEIGHT
        p_num = int(self.remap_mode[1])
        is_gamepad = "gamepad" in self.remap_mode
        
        # Dimensions
        card_w = 680
        card_h = 500
        card_x = w // 2 - card_w // 2
        card_y = h // 2 - card_h // 2 - 20
        
        # Columns
        x_start_col1 = card_x + 270
        x_start_col2 = card_x + 450
        
        y_header = card_y + 75
        y_data = y_header + 40
        row_h = 38
        
        # Check cells
        for i, direction in enumerate(self.remap_directions):
            y_row = y_data + i * 46
            
            # Col 1
            cell1_w = 340 if is_gamepad else 160
            cell1_rect = pygame.Rect(x_start_col1, y_row, cell1_w, row_h)
            if cell1_rect.collidepoint(mx, my):
                self.active_remap_cell = (direction, 0)
                input_manager.start_remap(direction, self.on_remap_success)
                sound_helper.play_select()
                return
                
            # Col 2
            if not is_gamepad:
                cell2_rect = pygame.Rect(x_start_col2, y_row, 160, row_h)
                if cell2_rect.collidepoint(mx, my):
                    self.active_remap_cell = (direction, 1)
                    input_manager.start_remap(direction, self.on_remap_success)
                    sound_helper.play_select()
                    return
                    
        # Check Buttons
        reset_btn_rect = pygame.Rect(card_x + 60, card_y + card_h - 70, 220, 40)
        back_btn_rect = pygame.Rect(card_x + card_w - 280, card_y + card_h - 70, 220, 40)
        
        if reset_btn_rect.collidepoint(mx, my):
            sound_helper.play_select()
            self.reset_remapping_defaults()
            return
        elif back_btn_rect.collidepoint(mx, my):
            sound_helper.play_back()
            input_manager.cancel_remap()
            self.state = getattr(self, "remap_return_state", "SETTINGS")
            return

    def reset_remapping_defaults(self):
        p_num = int(self.remap_mode[1])
        from config import DEFAULT_SETTINGS
        if "gamepad" in self.remap_mode:
            prop_name = f"gamepad_p{p_num}"
            setattr(settings, prop_name, DEFAULT_SETTINGS[prop_name].copy())
        else:
            prop_name = f"keys_p{p_num}"
            setattr(settings, prop_name, DEFAULT_SETTINGS[prop_name].copy())

    def on_remap_success(self, result_dict):
        if not result_dict or getattr(self, "active_remap_cell", None) is None:
            return
            
        in_type = result_dict.get("type")
        if in_type == "gamepad":
            val_to_save = result_dict["map_val"]
        else:
            val_to_save = result_dict["key"]
            
        sound_helper.play_select()
        
        target_group = None
        if "gamepad" in self.remap_mode:
            target_group = "gamepad"
        else:
            target_group = "keys"
            
        p_num = int(self.remap_mode[1])
        direction, set_idx = self.active_remap_cell
        
        if target_group == "gamepad":
            prop_name = f"gamepad_p{p_num}"
            new_gp = getattr(settings, prop_name).copy()
            new_gp[direction] = val_to_save
            setattr(settings, prop_name, new_gp)
        else:
            prop_name = f"keys_p{p_num}"
            new_keys = getattr(settings, prop_name).copy()
            if not isinstance(new_keys[direction], list):
                new_keys[direction] = [new_keys[direction], 0]
            new_keys[direction][set_idx] = val_to_save
            setattr(settings, prop_name, new_keys)
            
        self.active_remap_cell = None

    def get_lobby_keys_str(self, p_num):
        dev = getattr(settings, f"device_p{p_num}", "Keyboard")
        if dev == "Gamepad":
            gp = getattr(settings, f"gamepad_p{p_num}", {})
            parts = []
            for d in ["left", "down", "up", "right"]:
                val = gp.get(d)
                parts.append(self.get_key_name_str(val))
            return " | ".join(parts)
        else:
            k = getattr(settings, f"keys_p{p_num}", {})
            parts = []
            for d in ["left", "down", "up", "right"]:
                val = k.get(d)
                if isinstance(val, list) and val:
                    parts.append(self.get_key_name_str(val[0]))
                else:
                    parts.append(self.get_key_name_str(val))
            return " | ".join(parts)

    def get_selected_song_total_measures(self):
        if not self.display_list or self.song_index >= len(self.display_list):
            return 100
        item = self.display_list[self.song_index]
        if item["type"] == "song":
            song = item["song"]
            duration = song.get("duration", 120.0)
            bpm = song.get("bpm", 120.0)
            beats = duration * (bpm / 60.0)
            return max(1, int(math.ceil(beats / 4.0)))
        return 100

    def process_gamepad_gameplay_input(self, p_idx, dir_name, is_active):
        dir_map = {"left": 0, "down": 1, "up": 2, "right": 3}
        if dir_name in dir_map:
            self.gameplay.trigger_input(dir_map[dir_name], is_active, p_idx)

    def get_lobby_items(self):
        mode = self.mode_options[self.mode_index]
        items = []
        
        if mode == "PRACTICE":
            items.append({
                "label": "P1 INPUT DEVICE",
                "type": "value",
                "value_text": settings.device_p1,
                "key": "device_p1"
            })
            items.append({
                "label": "P1 CHARACTER",
                "type": "value",
                "value_text": settings.character,
                "key": "character"
            })
            items.append({
                "label": "PLAYBACK SPEED",
                "type": "value",
                "value_text": f"{settings.playback_speed:.2f}x",
                "key": "playback_speed"
            })
            items.append({
                "label": "DIFFICULTY",
                "type": "value",
                "value_text": self.difficulties[self.p1_diff_index] if self.difficulties else "Medium",
                "key": "difficulty"
            })
            items.append({
                "label": "START MEASURE",
                "type": "value",
                "value_text": str(self.practice_start_measure),
                "key": "practice_start_measure"
            })
            items.append({
                "label": "END MEASURE",
                "type": "value",
                "value_text": str(self.practice_end_measure),
                "key": "practice_end_measure"
            })
            items.append({
                "label": "REMAP P1 KEYBOARD (DDR)",
                "type": "link",
                "action_mode": "p1_ddr",
                "value_text": self.get_lobby_keys_str(1)
            })
            items.append({
                "label": "START PRACTICE",
                "type": "action",
                "action": "start"
            })
            
        elif mode == "SOLO":
            items.append({
                "label": "P1 INPUT DEVICE",
                "type": "value",
                "value_text": settings.device_p1,
                "key": "device_p1"
            })
            items.append({
                "label": "P1 CHARACTER",
                "type": "value",
                "value_text": settings.character,
                "key": "character"
            })
            items.append({
                "label": "PLAYBACK SPEED",
                "type": "value",
                "value_text": f"{settings.playback_speed:.2f}x",
                "key": "playback_speed"
            })
            items.append({
                "label": "REMAP P1 KEYBOARD (DDR)",
                "type": "link",
                "action_mode": "p1_ddr",
                "value_text": self.get_lobby_keys_str(1)
            })
            items.append({
                "label": "PROCEED TO SONG SELECT",
                "type": "action",
                "action": "start"
            })
            
        elif mode in ["CO-OP", "VERSUS"]:
            items.append({
                "label": "P1 INPUT DEVICE",
                "type": "value",
                "value_text": settings.device_p1,
                "key": "device_p1"
            })
            items.append({
                "label": "P2 INPUT DEVICE",
                "type": "value",
                "value_text": settings.device_p2,
                "key": "device_p2"
            })
            items.append({
                "label": "P1 CHARACTER",
                "type": "value",
                "value_text": settings.character,
                "key": "character"
            })
            items.append({
                "label": "P2 CHARACTER",
                "type": "value",
                "value_text": settings.character_p2,
                "key": "character_p2"
            })
            items.append({
                "label": "REMAP P1 KEYBOARD (DDR)",
                "type": "link",
                "action_mode": "p1_ddr",
                "value_text": self.get_lobby_keys_str(1)
            })
            items.append({
                "label": "REMAP P2 KEYBOARD (DDR)",
                "type": "link",
                "action_mode": "p2_ddr",
                "value_text": self.get_lobby_keys_str(2)
            })
            items.append({
                "label": "PROCEED TO SONG SELECT",
                "type": "action",
                "action": "start"
            })
            
        elif mode == "FNF":
            match_types = ["AI vs Human", "Human vs Human", "Human vs AI", "AI vs AI"]
            active_match = match_types[getattr(self, "fnf_match_type_index", 0)]
            items.append({
                "label": "MATCH TYPE",
                "type": "value",
                "value_text": active_match,
                "key": "match_type"
            })
            
            p1_is_human = "Human" in active_match.split(" vs ")[0]
            p2_is_human = "Human" in active_match.split(" vs ")[1]
            
            items.append({
                "label": "P1 INPUT DEVICE",
                "type": "value",
                "value_text": settings.device_p1 if p1_is_human else "CPU (AI)",
                "key": "device_p1",
                "disabled": not p1_is_human
            })
            items.append({
                "label": "P2 INPUT DEVICE",
                "type": "value",
                "value_text": settings.device_p2 if p2_is_human else "CPU (AI)",
                "key": "device_p2",
                "disabled": not p2_is_human
            })
            items.append({
                "label": "P1 CHARACTER",
                "type": "value",
                "value_text": settings.character,
                "key": "character"
            })
            items.append({
                "label": "P2 CHARACTER",
                "type": "value",
                "value_text": settings.character_p2,
                "key": "character_p2"
            })
            if p1_is_human:
                items.append({
                    "label": "REMAP P1 KEYBOARD (DDR)",
                    "type": "link",
                    "action_mode": "p1_ddr",
                    "value_text": self.get_lobby_keys_str(1)
                })
            if p2_is_human:
                items.append({
                    "label": "REMAP P2 KEYBOARD (DDR)",
                    "type": "link",
                    "action_mode": "p2_ddr",
                    "value_text": self.get_lobby_keys_str(2)
                })
            items.append({
                "label": "PROCEED TO SONG SELECT",
                "type": "action",
                "action": "start"
            })
            
        return items

    def adjust_lobby_setting(self, dir_val):
        items = self.get_lobby_items()
        if self.lobby_selection_index >= len(items):
            return
        item = items[self.lobby_selection_index]
        if item["type"] != "value" or item.get("disabled", False):
            return
            
        key = item["key"]
        sound_helper.play_select()
        
        if key == "device_p1":
            devices = ["Keyboard", "Gamepad", "Mat"]
            curr_idx = devices.index(settings.device_p1)
            settings.device_p1 = devices[(curr_idx + dir_val) % len(devices)]
        elif key == "device_p2":
            devices = ["Keyboard", "Gamepad", "Mat"]
            curr_idx = devices.index(settings.device_p2)
            settings.device_p2 = devices[(curr_idx + dir_val) % len(devices)]
        elif key == "character":
            curr_idx = self.characters_list.index(settings.character) if settings.character in self.characters_list else 0
            settings.character = self.characters_list[(curr_idx + dir_val) % len(self.characters_list)]
        elif key == "character_p2":
            curr_idx = self.characters_list.index(settings.character_p2) if settings.character_p2 in self.characters_list else 0
            settings.character_p2 = self.characters_list[(curr_idx + dir_val) % len(self.characters_list)]
        elif key == "playback_speed":
            speeds = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.25, 3.5, 3.75, 4.0, 4.25, 4.5, 4.75, 5.0]
            curr_idx = speeds.index(settings.playback_speed) if settings.playback_speed in speeds else 3
            settings.playback_speed = speeds[(curr_idx + dir_val) % len(speeds)]
        elif key == "match_type":
            self.fnf_match_type_index = (self.fnf_match_type_index + dir_val) % 4
        elif key == "difficulty":
            if self.difficulties:
                self.p1_diff_index = (self.p1_diff_index + dir_val) % len(self.difficulties)
        elif key == "practice_start_measure":
            total_m = self.get_selected_song_total_measures()
            self.practice_start_measure = max(0, min(total_m, self.practice_start_measure + dir_val))
            if self.practice_start_measure >= self.practice_end_measure:
                self.practice_end_measure = min(total_m, self.practice_start_measure + 1)
        elif key == "practice_end_measure":
            total_m = self.get_selected_song_total_measures()
            self.practice_end_measure = max(self.practice_start_measure + 1, min(total_m, self.practice_end_measure + dir_val))

    def start_gameplay_from_overlay(self):
        sound_helper.play_select()
        
        # Determine player difficulties
        if settings.players == 2:
            p1_diff = self.difficulties[self.p1_diff_index]
            p2_diff = self.difficulties[self.p2_diff_index]
            selected_diffs = [p1_diff, p2_diff]
        else:
            selected_diffs = self.difficulties[self.p1_diff_index]
            
        item = self.display_list[self.song_index]
        selected_song = item["song"]
        
        # AI Opponent setup for FNF
        p_is_ai = [False] * settings.players
        if settings.game_mode == "FNF":
            active_match = self.fnf_match_types[self.fnf_match_type_index]
            p_is_ai[0] = "AI" in active_match.split(" vs ")[0]
            p_is_ai[1] = "AI" in active_match.split(" vs ")[1]
            
        # Pass practice parameters if Practice mode is active
        start_m = self.practice_start_measure if settings.game_mode == "Practice" else None
        end_m = self.practice_end_measure if settings.game_mode == "Practice" else None
        
        self.gameplay = Gameplay(
            selected_song, 
            selected_diffs, 
            settings.character, 
            player_is_ai=p_is_ai,
            practice_start_measure=start_m,
            practice_end_measure=end_m
        )
        self.state = "GAMEPLAY"

    def update(self, dt):
        self.celebration.update(dt)
        theme = settings.theme
        
        # Update warning notification timer
        if self.warning_notification_timer > 0:
            self.warning_notification_timer = max(0.0, self.warning_notification_timer - dt)
        if getattr(self, "achievement_banner_timer", 0) > 0:
            self.achievement_banner_timer = max(0.0, self.achievement_banner_timer - dt)
        
        # Check mouse hover focus
        if self.state in ["TITLE", "SONG_SELECT", "SETTINGS"]:
            mx, my = pygame.mouse.get_pos()
            self.handle_mouse_hover(mx, my)

        # Update title screen background particles
        if self.state == "TITLE":
            for p in self.title_particles:
                p["y"] += p["speed_y"] * dt
                p["start_time"] += dt
                p["x"] += (p["speed_x"] + math.sin(p["start_time"] * p["wobble_speed"]) * p["wobble_amp"] * 0.1) * dt
                if p["y"] < -50 or p["x"] < -50 or p["x"] > SCREEN_WIDTH + 50:
                    p["y"] = SCREEN_HEIGHT + 50
                    p["x"] = random.randint(0, SCREEN_WIDTH)
                    p["speed_y"] = random.uniform(-60, -20)
                    p["speed_x"] = random.uniform(-10, 10)

        # Update calibration timing
        if self.state == "CALIBRATION":
            t_elapsed = time.time() - self.calib_start_time
            curr_beat_idx = int(t_elapsed / self.calib_beat_interval)
            if curr_beat_idx > self.calib_last_beat_index:
                self.calib_last_beat_index = curr_beat_idx
                sound_helper.play_select()
                self.calib_flash = 1.0
            if self.calib_flash > 0:
                self.calib_flash = max(0.0, self.calib_flash - dt * 5.0)

        # Handle re-scan songs when analysis completes successfully
        if self.state == "ANALYZING":
            self.spinner_angle = (self.spinner_angle + dt * 180) % 360
            if self.analysis_thread and not self.analysis_thread.is_alive():
                # Thread finished!
                if self.analysis_error:
                    print(f"Analysis failed: {self.analysis_error}")
                    self.state = "SONG_SELECT"
                else:
                    print("Analysis completed successfully!")
                    self.scan_songs()
                    # Select the newly analyzed song
                    new_filename = self.analysis_success_data["filename"]
                    for idx, s in enumerate(self.songs_list):
                        if s["filename"] == new_filename:
                            self.song_index = idx
                            break
                    self.state = "SONG_SELECT"
                self.analysis_thread = None

        elif self.state == "EDITOR" and self.editor:
            self.editor.update(dt)

        elif self.state == "GAMEPLAY" and self.gameplay:
            self.gameplay.update(dt)
            
            if self.gameplay.game_over:
                self.results_data = []
                for p in self.gameplay.players:
                    p_res = {
                        "player_idx": p.player_idx,
                        "character_name": p.character_name,
                        "title": self.gameplay.metadata["title"],
                        "difficulty": p.difficulty,
                        "bpm": self.gameplay.bpm,
                        "score": p.score,
                        "max_combo": p.max_combo,
                        "perfects": p.perfects,
                        "goods": p.goods,
                        "greats": p.greats,
                        "misses": p.misses,
                        "timing_offsets": p.timing_offsets,
                        "duration": max([n["time"] for n in p.notes]) + 2.0 if p.notes else 60.0,
                        "missed_last_note": p.notes[-1].get("missed", False) if p.notes else False
                    }
                    active_song = None
                    for s in self.songs_list:
                        if s["title"] == self.gameplay.metadata["title"]:
                            active_song = s
                            break
                    if not active_song and self.songs_list:
                        active_song = self.songs_list[0]
                        
                    self.last_gameplay_pause_duration = self.gameplay.elapsed_pause_time
                    if active_song:
                        self.update_high_score(active_song, p.difficulty, p_res)
                    if p.player_idx == 0:
                        new_unlocks = profile_manager.update_after_gameplay(
                            self.gameplay.metadata["title"],
                            p.difficulty,
                            p_res,
                            settings.playback_speed
                        )
                        if new_unlocks:
                            self.celebration.trigger()
                            self.newly_unlocked_achievements = new_unlocks
                            self.achievement_banner_timer = 6.0
                    self.results_data.append(p_res)
                self.gameplay.clean_up()
                self.gameplay = None
                self.state = "RESULTS"

    def handle_mouse_click(self, mx, my):
        w, h = SCREEN_WIDTH, SCREEN_HEIGHT
        
        # --- PROFILE CREATION SCREEN ---
        if self.state == "PROFILE_CREATION":
            panel_h = 420
            panel_y = h // 2 - panel_h // 2 - 20
            
            # Avatar grid coordinates (6 avatars inline)
            av_start_x = w // 2 - 180
            av_y = panel_y + 305
            for idx in range(len(AVATARS)):
                ax = av_start_x + idx * 60
                av_rect = pygame.Rect(ax - 22, av_y - 22, 44, 44)
                if av_rect.collidepoint(mx, my):
                    self.profile_creation_avatar_idx = idx
                    sound_helper.play_select()
                    return
            
            # Confirm button click
            btn_rect = pygame.Rect(w // 2 - 100, panel_y + 350, 200, 42)
            if btn_rect.collidepoint(mx, my):
                name = self.profile_creation_name.strip()
                if name:
                    avatar_id = AVATARS[self.profile_creation_avatar_idx]["id"]
                    profile_manager.create_profile(name, avatar_id)
                    profile_manager.load()
                    sound_helper.play_select()
                    self.state = "TITLE"
                    self.title_index = 0
            return

        # --- PROFILE STATS SCREEN ---
        elif self.state == "PROFILE_STATS":
            tab_rects = {
                "stats": pygame.Rect(w // 2 - 210, 140, 130, 36),
                "scores": pygame.Rect(w // 2 - 60, 140, 150, 36),
                "achievements": pygame.Rect(w // 2 + 110, 150, 150, 36)
            }
            for tab_name, rect in tab_rects.items():
                if rect.collidepoint(mx, my):
                    self.profile_tab = tab_name
                    self.profile_scroll_idx = 0
                    sound_helper.play_select()
                    return

            # Tagline selection
            if self.profile_tab == "stats":
                unlocked_tags = profile_manager.profile.get("unlocked_taglines", ["Beginner"])
                for idx, tag in enumerate(unlocked_tags):
                    row_y = 380 + idx * 30
                    tag_rect = pygame.Rect(w // 2 - 220, row_y, 440, 26)
                    if tag_rect.collidepoint(mx, my):
                        profile_manager.profile["tagline"] = tag
                        profile_manager.save()
                        sound_helper.play_select()
                        return

            # Back button
            back_rect = pygame.Rect(50, h - 60, 100, 36)
            if back_rect.collidepoint(mx, my):
                self.trigger_back()
                return

        # --- EDITOR SCREEN ---
        elif self.state == "EDITOR" and self.editor:
            self.editor.handle_mouse_click(mx, my)
            return

        # --- TITLE SCREEN ---
        elif self.state == "TITLE":
            for idx, opt in enumerate(self.title_options):
                y_start = 370 + idx * 70
                y_end = y_start + 50
                if (w // 2 - 150 <= mx <= w // 2 + 150) and (y_start <= my <= y_end):
                    self.title_index = idx
                    self.trigger_confirm()
                    return
                    
        elif self.state == "MODE_SELECT":
            card_w = 165
            card_h = 300
            spacing = 20
            total_w = len(self.mode_options) * card_w + (len(self.mode_options) - 1) * spacing
            start_x = w // 2 - total_w // 2
            card_y = 180
            
            for idx in range(len(self.mode_options)):
                x_pos = start_x + idx * (card_w + spacing)
                card_rect = pygame.Rect(x_pos, card_y, card_w, card_h)
                if card_rect.collidepoint(mx, my):
                    self.mode_index = idx
                    self.trigger_confirm()
                    return
                    
        elif self.state == "LOBBY":
            lobby_items = self.get_lobby_items()
            lobby_h = len(lobby_items) * 45
            start_y = h // 2 - lobby_h // 2 - 20
            card_w = 600
            card_x = w // 2 - card_w // 2
            
            for idx, item in enumerate(lobby_items):
                y_pos = start_y + idx * 45
                row_rect = pygame.Rect(card_x, y_pos, card_w, 36)
                if row_rect.collidepoint(mx, my):
                    self.lobby_selection_index = idx
                    
                    if item["type"] == "value":
                        if item["key"] in ["practice_start_measure", "practice_end_measure"]:
                            # Clicked the text area to type directly
                            if card_x + card_w - 130 <= mx <= card_x + card_w - 40:
                                sound_helper.play_select()
                                self.lobby_edit_mode = item["key"]
                                self.lobby_edit_buffer = str(getattr(self, item["key"]))
                            elif mx < card_x + card_w - 130:
                                self.adjust_lobby_setting(-1)
                            else:
                                self.adjust_lobby_setting(1)
                        else:
                            if mx < card_x + card_w - 120:
                                self.adjust_lobby_setting(-1)
                            else:
                                self.adjust_lobby_setting(1)
                    else:
                        self.trigger_confirm()
                    return
                    
        elif self.state == "DIFFICULTY_SELECT_OVERLAY":
            panel_w = 380
            p1_x = 100
            p1_y = 170
            list_start_y_1 = p1_y + 60
            row_h = 42
            
            for d_idx, df in enumerate(self.difficulties):
                row_rect = pygame.Rect(p1_x + 20, list_start_y_1 + d_idx * row_h, panel_w - 40, 36)
                if row_rect.collidepoint(mx, my):
                    self.p1_diff_index = d_idx
                    self.p1_ready = True
                    sound_helper.play_select()
                    
            if settings.players == 2:
                p2_x = w - 100 - panel_w
                p2_y = 170
                list_start_y_2 = p2_y + 60
                for d_idx, df in enumerate(self.difficulties):
                    row_rect = pygame.Rect(p2_x + 20, list_start_y_2 + d_idx * row_h, panel_w - 40, 36)
                    if row_rect.collidepoint(mx, my):
                        self.p2_diff_index = d_idx
                        self.p2_ready = True
                        sound_helper.play_select()
                        
            if self.p1_ready and self.p2_ready:
                self.start_gameplay_from_overlay()
            return

        # --- SONG SELECT SCREEN ---
        elif self.state == "SONG_SELECT":
            list_w = 450
            # Song List click check
            if (60 <= mx <= 490):
                total_items = len(self.display_list)
                visible_rows = 9
                start_row = max(0, min(self.song_index - visible_rows // 2, total_items - visible_rows)) if total_items > visible_rows else 0
                
                for row_idx in range(visible_rows):
                    item_idx = start_row + row_idx
                    if item_idx >= total_items:
                        break
                    y_pos = 140 + row_idx * 50
                    if (y_pos - 10 <= my <= y_pos + 32):
                        if self.song_index == item_idx:
                            self.trigger_confirm()
                        else:
                            self.song_index = item_idx
                            self.update_difficulties_list()
                            sound_helper.play_select()
                        return
            
            # Details Card click check
            card_x = 540
            card_w = 430
            if self.display_list and self.song_index < len(self.display_list):
                item = self.display_list[self.song_index]
                if item["type"] == "song":
                    # Check difficulty rows click (viewport-aligned)
                    list_start_y = getattr(self, "diff_list_start_y", 230)
                    displayed_diffs = getattr(self, "displayed_diffs", [])
                    row_h = 36
                    row_spacing = 5
                    max_visible = 4
                    
                    is_multiplayer = (settings.players == 2 or settings.game_mode in ["Co-Op", "Versus", "FNF"])
                    if is_multiplayer:
                        proceed_rect = pygame.Rect(card_x + 30, list_start_y, card_w - 60, 48)
                        if proceed_rect.collidepoint(mx, my):
                            self.trigger_confirm()
                            return
                    else:
                        start_idx = max(0, min(self.difficulty_index - max_visible // 2, len(displayed_diffs) - max_visible)) if displayed_diffs else 0
                        for i in range(min(max_visible, len(displayed_diffs))):
                            idx = start_idx + i
                            y_pos = list_start_y + i * (row_h + row_spacing)
                            row_rect = pygame.Rect(card_x + 30, y_pos, card_w - 60, row_h)
                            if row_rect.collidepoint(mx, my):
                                if self.difficulty_index == idx:
                                    self.trigger_confirm()
                                else:
                                    self.difficulty_index = idx
                                    sound_helper.play_select()
                                return
                    
                    # Playback Speed selector clicked
                    speed_y = getattr(self, "speed_y", 528)
                    left_box = pygame.Rect(card_x + 190, speed_y, 26, 22)
                    right_box = pygame.Rect(card_x + 268, speed_y, 26, 22)
                    if left_box.collidepoint(mx, my):
                        settings.playback_speed = max(0.5, settings.playback_speed - 0.25)
                        sound_helper.play_select()
                        return
                    elif right_box.collidepoint(mx, my):
                        settings.playback_speed = min(5.0, settings.playback_speed + 0.25)
                        sound_helper.play_select()
                        return
                    
                    # EDIT CHART and DELETE SONG Buttons clicked
                    btn_y = getattr(self, "btn_y", 575)
                    edit_btn_rect = pygame.Rect(card_x + 30, btn_y, 175, 40)
                    delete_btn_rect = pygame.Rect(card_x + 225, btn_y, 175, 40)
                    
                    if edit_btn_rect.collidepoint(mx, my):
                        self.start_chart_editor()
                        return
                    elif delete_btn_rect.collidepoint(mx, my):
                        if self.display_list and self.song_index < len(self.display_list):
                            item = self.display_list[self.song_index]
                            if item["type"] == "song":
                                selected_song = item["song"]
                                if selected_song["filename"] != "Retro_Beat.wav":
                                    self.delete_song(selected_song)
                                    return
            else:
                # Upload Button clicked
                if (card_x + 30 <= mx <= card_x + card_w - 30) and (570 <= my <= 630):
                    self.trigger_confirm()
                    return

        # --- SETTINGS SCREEN ---
        elif self.state == "SETTINGS":
            opts = self.get_settings_options()
            # Only check visible elements in scroll view
            for i in range(12):
                idx = self.settings_scroll_y + i
                if idx >= len(opts):
                    break
                opt = opts[idx]
                if opt.startswith("---"):
                    continue
                y_start = 120 + i * 38
                y_end = y_start + 30
                if (w // 2 - 250 <= mx <= w // 2 + 250) and (y_start <= my <= y_end):
                    self.settings_index = idx
                    if "REMAP" in opt or opt == "BACK" or opt == "CALIBRATE LATENCY":
                        self.trigger_confirm()
                    else:
                        if mx > w // 2:
                            self.adjust_setting(1)
                        else:
                            self.adjust_setting(-1)
                    return

        # --- REMAP SCREEN ---
        elif self.state == "REMAP":
            self.handle_remap_click(mx, my)
            return

        # --- RESULTS SCREEN ---
        elif self.state == "RESULTS":
            self.trigger_confirm()

        # --- GAMEPLAY STATE (Check if paused) ---
        elif self.state == "GAMEPLAY" and self.gameplay and self.gameplay.paused:
            # Resume button
            if (w // 2 - 150 <= mx <= w // 2 + 150) and (h // 2 - 20 <= my <= h // 2 + 20):
                self.gameplay.toggle_pause()
                sound_helper.play_select()
            # Exit button
            elif (w // 2 - 150 <= mx <= w // 2 + 150) and (h // 2 + 40 <= my <= h // 2 + 80):
                pygame.mixer.music.stop()
                self.gameplay = None
                sound_helper.play_back()
                self.state = "SONG_SELECT"

    def handle_mouse_hover(self, mx, my):
        w, h = SCREEN_WIDTH, SCREEN_HEIGHT
        if self.state == "TITLE":
            for idx in range(len(self.title_options)):
                y_start = 370 + idx * 70
                y_end = y_start + 50
                if (w // 2 - 150 <= mx <= w // 2 + 150) and (y_start <= my <= y_end):
                    if self.title_index != idx:
                        self.title_index = idx
                    return
        elif self.state == "SONG_SELECT":
            if (60 <= mx <= 490):
                total_items = len(self.songs_list) + 1
                visible_rows = 9
                start_row = max(0, min(self.song_index - visible_rows // 2, total_items - visible_rows))
                for row_idx in range(visible_rows):
                    item_idx = start_row + row_idx
                    if item_idx >= total_items:
                        break
                    y_pos = 140 + row_idx * 50
                    if (y_pos - 10 <= my <= y_pos + 32):
                        if self.song_index != item_idx:
                            self.song_index = item_idx
                            self.update_difficulties_list()
                        return
        elif self.state == "SETTINGS":
            opts = self.get_settings_options()
            for i in range(12):
                idx = self.settings_scroll_y + i
                if idx >= len(opts):
                    break
                if opts[idx].startswith("---"):
                    continue
                y_start = 120 + i * 38
                y_end = y_start + 30
                if (w // 2 - 250 <= mx <= w // 2 + 250) and (y_start <= my <= y_end):
                    if self.settings_index != idx:
                        self.settings_index = idx
                    return
    def get_song_cover_surface(self, item, theme):
        """Retrieves or procedurally generates a cover surface for a song or group, sized 370x150."""
        # Check cache
        cache_key = None
        if item["type"] == "group":
            cache_key = f"group_{item['name']}"
        elif item["type"] == "song":
            cache_key = f"song_{item['song']['title']}"
        elif item["type"] == "upload":
            cache_key = "upload_banner"
            
        if cache_key in self.cover_cache:
            return self.cover_cache[cache_key]
            
        # Create a new Surface
        surf = pygame.Surface((370, 150), pygame.SRCALPHA)
        
        if item["type"] == "group":
            # Procedural Group Album Cover
            surf.fill((22, 18, 30))
            pygame.draw.rect(surf, (255, 215, 0), (0, 0, 370, 150), width=2, border_radius=8)
            # Folder Shape drawing
            pygame.draw.rect(surf, (255, 215, 0), (30, 45, 120, 75), border_radius=4)
            pygame.draw.polygon(surf, (255, 215, 0), [(30, 45), (60, 30), (90, 45)])
            pygame.draw.rect(surf, (22, 18, 30), (38, 52, 104, 60), border_radius=2)
            
            # Text label
            font_title = pygame.font.SysFont("Impact" if theme == "DDR-Retro" else "Segoe UI", 22, bold=True)
            lbl = font_title.render(item["name"].upper(), True, (255, 255, 255))
            surf.blit(lbl, (170, 45))
            
            font_sub = pygame.font.SysFont("Segoe UI", 14, bold=True)
            lbl_sub = font_sub.render(f"{item['count']} Songs", True, (255, 215, 0))
            surf.blit(lbl_sub, (170, 80))
            
        elif item["type"] == "song":
            song_data = item["song"]
            cover_path = song_data.get("cover_path")
            
            loaded = False
            if cover_path and os.path.exists(cover_path):
                try:
                    img = pygame.image.load(cover_path).convert_alpha()
                    # Scale to fit exactly
                    scaled = pygame.transform.smoothscale(img, (370, 150))
                    surf.blit(scaled, (0, 0))
                    pygame.draw.rect(surf, (255, 255, 255, 120), (0, 0, 370, 150), width=1, border_radius=8)
                    loaded = True
                except Exception as e:
                    print(f"Error loading cover image {cover_path}: {e}")
                    
            if not loaded:
                # Procedural Abstract Neon Cover Art!
                title_hash = sum(ord(c) for c in song_data["title"])
                h1 = (title_hash % 360) / 360.0
                h2 = ((title_hash + 120) % 360) / 360.0
                
                import colorsys
                c1 = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(h1, 0.8, 0.4))
                c2 = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(h2, 0.8, 0.8))
                
                # Gradient
                for x in range(370):
                    factor = x / 370.0
                    col = (
                        int(c1[0] + factor * (c2[0] - c1[0])),
                        int(c1[1] + factor * (c2[1] - c1[1])),
                        int(c1[2] + factor * (c2[2] - c1[2]))
                    )
                    pygame.draw.line(surf, col, (x, 0), (x, 150))
                    
                # Stylized vector cat face outline
                cat_col = (255, 255, 255, 70)
                cx, cy = 185, 75
                pygame.draw.polygon(surf, cat_col, [(cx - 45, cy - 15), (cx - 35, cy - 45), (cx - 15, cy - 25)])
                pygame.draw.polygon(surf, cat_col, [(cx + 45, cy - 15), (cx + 35, cy - 45), (cx + 15, cy - 25)])
                pygame.draw.ellipse(surf, cat_col, (cx - 40, cy - 25, 80, 50), width=2)
                pygame.draw.circle(surf, cat_col, (cx - 15, cy - 5), 3)
                pygame.draw.circle(surf, cat_col, (cx + 15, cy - 5), 3)
                pygame.draw.polygon(surf, cat_col, [(cx, cy + 5), (cx - 4, cy + 1), (cx + 4, cy + 1)])
                
                # Title text overlay on the bottom banner
                pygame.draw.rect(surf, (0, 0, 0, 140), (0, 110, 370, 40))
                font_title = pygame.font.SysFont("Segoe UI", 15, bold=True)
                title_lbl = font_title.render(song_data["title"], True, (255, 255, 255))
                surf.blit(title_lbl, (15, 120))
                
                pygame.draw.rect(surf, (255, 255, 255, 180), (0, 0, 370, 150), width=2, border_radius=8)
                
        elif item["type"] == "upload":
            surf.fill((15, 12, 22))
            pygame.draw.rect(surf, (0, 255, 204), (0, 0, 370, 150), width=2, border_radius=8)
            # Stylized cloud arrow vector
            pygame.draw.rect(surf, (0, 255, 204), (160, 60, 50, 40), border_radius=4)
            pygame.draw.polygon(surf, (0, 255, 204), [(150, 60), (185, 30), (220, 60)])
            pygame.draw.rect(surf, (15, 12, 22), (175, 70, 20, 30), border_radius=2)
            
            font_title = pygame.font.SysFont("Impact" if theme == "DDR-Retro" else "Segoe UI", 20, bold=True)
            lbl = font_title.render("UPLOAD CUSTOM SONG", True, (255, 255, 255))
            surf.blit(lbl, (185 - lbl.get_width()//2, 115))
            
        self.cover_cache[cache_key] = surf
        return surf

    def draw(self):
        theme = settings.theme
        bg_color = theme_manager.get_bg_color(theme)
        self.screen.fill(bg_color)
        
        text_color = theme_manager.get_text_color(theme)
        accent_color = theme_manager.get_accent_color(theme)
        
        # Load fonts
        title_font = pygame.font.SysFont("Impact" if theme == "DDR-Retro" else "Segoe UI", 64, bold=True)
        menu_font = pygame.font.SysFont("Trebuchet MS" if theme == "DDR-Retro" else "Segoe UI", 36, bold=True)
        desc_font = pygame.font.SysFont("Trebuchet MS" if theme == "DDR-Retro" else "Segoe UI", 22)
        small_font = pygame.font.SysFont("Trebuchet MS" if theme == "DDR-Retro" else "Segoe UI", 16)
        
        w, h = SCREEN_WIDTH, SCREEN_HEIGHT
        mx, my = pygame.mouse.get_pos()

        # --- DRAW STATE: TITLE ---
        if self.state == "TITLE":
            # Draw floating animated cat particles in the background first
            for p in self.title_particles:
                try:
                    p_surf = pygame.Surface((p["size"] * 2, p["size"] * 2), pygame.SRCALPHA)
                    alpha = p["alpha"]
                    col = (255, 255, 255, alpha) if self.is_dark_theme(theme) else (60, 50, 75, alpha)
                    r = p["size"] // 2
                    cx, cy = p["size"], p["size"]
                    
                    if p["type"] == "paw":
                        pad_col = (255, 200, 215, alpha) if self.is_dark_theme(theme) else (140, 100, 115, alpha)
                        # Main pad
                        pygame.draw.circle(p_surf, col, (cx, cy), r)
                        # Toes
                        for dx, dy in [(-r * 0.7, -r * 0.3), (-r * 0.3, -r * 0.7), (r * 0.3, -r * 0.7), (r * 0.7, -r * 0.3)]:
                            pygame.draw.circle(p_surf, col, (int(cx + dx), int(cy + dy)), int(r * 0.35))
                        # Main center pad
                        pygame.draw.circle(p_surf, pad_col, (cx, cy + int(r * 0.15)), int(r * 0.5))
                    else:
                        # Cat head/face
                        pygame.draw.circle(p_surf, col, (cx, cy + int(r * 0.15)), int(r * 0.85))
                        # Left Ear
                        pygame.draw.polygon(p_surf, col, [
                            (cx - int(r * 0.8), cy - int(r * 0.1)),
                            (cx - int(r * 0.4), cy - int(r * 0.3)),
                            (cx - int(r * 0.75), cy - int(r * 0.85))
                        ])
                        # Right Ear
                        pygame.draw.polygon(p_surf, col, [
                            (cx + int(r * 0.8), cy - int(r * 0.1)),
                            (cx + int(r * 0.4), cy - int(r * 0.3)),
                            (cx + int(r * 0.75), cy - int(r * 0.85))
                        ])
                    self.screen.blit(p_surf, (int(p["x"] - cx), int(p["y"] - cy)))
                except:
                    pass

            # Glow effect for Title in Retro Theme
            title_text = "ZOOMIES"
            if theme == "DDR-Retro":
                # Draw background neon lines/circles
                pygame.draw.circle(self.screen, (25, 15, 45), (w // 2, h // 2), 250, width=3)
                pygame.draw.circle(self.screen, (40, 20, 65), (w // 2, h // 2), 320, width=1)
                
                # Neon glow
                for offset in range(5, 0, -1):
                    glow_color = (150 - offset*20, 0, 100 - offset*10)
                    glow_surf = title_font.render(title_text, True, glow_color)
                    self.screen.blit(glow_surf, (w // 2 - glow_surf.get_width() // 2 + offset, 150 + offset))
            
            main_title_surf = title_font.render(title_text, True, text_color)
            self.screen.blit(main_title_surf, (w // 2 - main_title_surf.get_width() // 2, 150))
            
            if getattr(self, "last_tagline_state", None) != "TITLE":
                import random
                self.active_tagline = random.choice(self.taglines)
                self.last_tagline_state = "TITLE"
            sub_title = desc_font.render(self.active_tagline, True, accent_color)
            self.screen.blit(sub_title, (w // 2 - sub_title.get_width() // 2, 230))
            
            # Developer Credits
            dev_lbl = small_font.render("developed by PixelPaws Studio", True, (130, 120, 140) if self.is_dark_theme(theme) else (90, 80, 100))
            self.screen.blit(dev_lbl, (w // 2 - dev_lbl.get_width() // 2, h - 80))
            
            # Draw Title Options
            for idx, opt in enumerate(self.title_options):
                is_selected = (idx == self.title_index)
                opt_color = accent_color if is_selected else text_color
                
                # Draw selector background for Minimalist
                if theme == "Minimalist" and is_selected:
                    pygame.draw.rect(self.screen, (230, 230, 235), (w // 2 - 150, 370 + idx * 70, 300, 50), border_radius=10)
                
                # Select pointer for Retro
                text_str = f"> {opt} <" if (is_selected and theme == "DDR-Retro") else opt
                opt_surf = menu_font.render(text_str, True, opt_color)
                self.screen.blit(opt_surf, (w // 2 - opt_surf.get_width() // 2, 375 + idx * 70))
                
            footer = small_font.render("F11: Fullscreen | Arrow Keys: Navigate | ENTER: Select", True, text_color)
            self.screen.blit(footer, (w // 2 - footer.get_width() // 2, h - 50))

        # --- DRAW STATE: SONG SELECT ---
        elif self.state == "SONG_SELECT":
            # Header
            header_surf = menu_font.render("SELECT SONG", True, text_color)
            self.screen.blit(header_surf, (50, 50))
            
            # Display current song item card on right, song list on left
            list_w = 450
            list_h = 520
            pygame.draw.rect(self.screen, (20, 15, 35) if self.is_dark_theme(theme) else (235, 235, 240), (50, 120, list_w, list_h), border_radius=10)
            
            total_items = len(self.display_list)
            visible_rows = 9
            start_row = max(0, min(self.song_index - visible_rows // 2, total_items - visible_rows))
            
            for row_idx in range(visible_rows):
                item_idx = start_row + row_idx
                if item_idx >= total_items:
                    break
                    
                item = self.display_list[item_idx]
                is_selected = (item_idx == self.song_index)
                y_pos = 140 + row_idx * 50
                
                # Highlight bar color
                if is_selected:
                    if item["type"] == "group":
                        bar_color = (80, 70, 20) if self.is_dark_theme(theme) else (255, 240, 190)
                        row_color = (255, 215, 0)
                    else:
                        bar_color = (35, 25, 60) if self.is_dark_theme(theme) else (220, 220, 225)
                        row_color = accent_color
                    pygame.draw.rect(self.screen, bar_color, (60, y_pos - 10, list_w - 20, 42), border_radius=5)
                else:
                    if item["type"] == "group":
                        row_color = (230, 190, 40)
                    else:
                        row_color = text_color
                
                if item["type"] == "group":
                    # Draw Folder Group Header
                    icon = "📂" if item["name"] in self.expanded_groups else "📁"
                    grp_title = f"{icon}  {item['name'].upper()}  ({item['count']})"
                    grp_lbl = render_truncated_text(desc_font, grp_title, 390, row_color)
                    self.screen.blit(grp_lbl, (80, y_pos - 4))
                    
                elif item["type"] == "song":
                    # Draw Song Title indented
                    song_title = f"  - {item['song']['title']}"
                    song_lbl = render_truncated_text(desc_font, song_title, 380, row_color)
                    self.screen.blit(song_lbl, (80, y_pos - 4))
                    
                elif item["type"] == "upload":
                    upload_lbl = desc_font.render("+ UPLOAD CUSTOM SONG...", True, row_color)
                    self.screen.blit(upload_lbl, (80, y_pos - 4))
            
            # Right Card details
            card_x = 540
            card_w = 430
            pygame.draw.rect(self.screen, (20, 15, 35) if self.is_dark_theme(theme) else (235, 235, 240), (card_x, 120, card_w, list_h), border_radius=10)
            
            if total_items > 0 and self.song_index < total_items:
                item = self.display_list[self.song_index]
                
                # Draw Album Cover surface
                cover_surf = self.get_song_cover_surface(item, theme)
                self.screen.blit(cover_surf, (card_x + 30, 135))
                
                if item["type"] == "song":
                    selected_song = item["song"]
                    
                    # Title
                    title_end_y = draw_wrapped_text(self.screen, menu_font, selected_song["title"], text_color, card_x + 30, 295, card_w - 60)
                    
                    # Duration & BPM (Meta)
                    meta_y = title_end_y + 10
                    speed_mult = getattr(settings, "playback_speed", 1.0)
                    display_bpm = selected_song["bpm"] * speed_mult
                    dur_m = int((selected_song["duration"] / speed_mult) // 60)
                    dur_s = int((selected_song["duration"] / speed_mult) % 60)
                    if speed_mult != 1.0:
                        meta_str = f"BPM: {display_bpm:.1f} ({speed_mult:.2f}x)   |   Length: {dur_m:02d}:{dur_s:02d}"
                    else:
                        meta_str = f"BPM: {display_bpm:.1f}   |   Length: {dur_m:02d}:{dur_s:02d}"
                    meta_surf = desc_font.render(meta_str, True, text_color)
                    self.screen.blit(meta_surf, (card_x + 30, meta_y))
                    
                    # List of difficulties
                    tiny_font = pygame.font.SysFont("Trebuchet MS" if theme == "DDR-Retro" else "Segoe UI", 12)
                    displayed_diffs = self.difficulties
                    self.displayed_diffs = displayed_diffs
                    list_start_y = meta_y + 40
                    self.diff_list_start_y = list_start_y
                    row_h = 36
                    row_spacing = 5
                    max_visible = 4
                    
                    is_multiplayer = (settings.players == 2 or settings.game_mode in ["Co-Op", "Versus", "FNF"])
                    if is_multiplayer:
                        diff_hdr_surf = small_font.render("MULTIPLAYER SETUP:", True, text_color)
                        self.screen.blit(diff_hdr_surf, (card_x + 30, list_start_y - 20))
                        
                        proceed_rect = pygame.Rect(card_x + 30, list_start_y, card_w - 60, 48)
                        proceed_hover = proceed_rect.collidepoint(mx, my)
                        bg_col_proc = accent_color if proceed_hover else (35, 25, 60, 150)
                        pygame.draw.rect(self.screen, bg_col_proc, proceed_rect, border_radius=8)
                        pygame.draw.rect(self.screen, accent_color, proceed_rect, width=2, border_radius=8)
                        
                        proc_text = menu_font.render("READY & CHOOSE DIFFS", True, (255, 255, 255))
                        self.screen.blit(proc_text, (proceed_rect.centerx - proc_text.get_width() // 2, proceed_rect.centery - proc_text.get_height() // 2))
                        
                        diff_list_end_y = list_start_y + 48
                    else:
                        start_idx = max(0, min(self.difficulty_index - max_visible // 2, len(displayed_diffs) - max_visible))
                        
                        diff_hdr_surf = small_font.render("SELECT DIFFICULTY & PLAY:", True, text_color)
                        self.screen.blit(diff_hdr_surf, (card_x + 30, list_start_y - 20))
                        
                        if start_idx > 0:
                            up_ind = tiny_font.render("▲", True, accent_color)
                            self.screen.blit(up_ind, (card_x + card_w // 2 - up_ind.get_width() // 2, list_start_y - 12))
                            
                        for i in range(min(max_visible, len(displayed_diffs))):
                            idx = start_idx + i
                            diff_name = displayed_diffs[idx]
                            is_selected = (idx == self.difficulty_index)
                            y_pos = list_start_y + i * (row_h + row_spacing)
                            
                            diff_color = theme_manager.get_lane_color(idx % 5, theme)
                            row_rect = pygame.Rect(card_x + 30, y_pos, card_w - 60, row_h)
                            row_hover = row_rect.collidepoint(mx, my)
                            
                            if is_selected:
                                bg_col = (diff_color[0], diff_color[1], diff_color[2], 180)
                                border_col = (255, 255, 255)
                                text_col_row = (255, 255, 255)
                            elif row_hover:
                                bg_col = (50, 40, 75, 120) if self.is_dark_theme(theme) else (210, 210, 220, 120)
                                border_col = diff_color
                                text_col_row = text_color
                            else:
                                bg_col = (30, 22, 45, 100) if self.is_dark_theme(theme) else (220, 220, 225, 100)
                                border_col = (50, 45, 70) if self.is_dark_theme(theme) else (200, 200, 205)
                                text_col_row = text_color
                                
                            row_surf = pygame.Surface((row_rect.width, row_rect.height), pygame.SRCALPHA)
                            pygame.draw.rect(row_surf, bg_col, (0, 0, row_rect.width, row_rect.height), border_radius=6)
                            pygame.draw.rect(row_surf, border_col, (0, 0, row_rect.width, row_rect.height), width=1 if not is_selected else 2, border_radius=6)
                            self.screen.blit(row_surf, (row_rect.x, row_rect.y))
                            
                            diff_text_to_draw = diff_name.upper()
                            diff_surf = small_font.render(diff_text_to_draw, True, text_col_row)
                            self.screen.blit(diff_surf, (card_x + 45, y_pos + 1))
                            
                            is_custom_diff = (diff_name not in ["Easy", "Medium", "Hard", "Harder", "Crazy", "Dynamic"])
                            if is_custom_diff:
                                custom_tag_font = pygame.font.SysFont("Trebuchet MS" if theme == "DDR-Retro" else "Segoe UI", 10, bold=True)
                                custom_tag_surf = custom_tag_font.render(" CUSTOM ", True, (0, 0, 0))
                                
                                tag_x = card_x + 45 + diff_surf.get_width() + 8
                                tag_y = y_pos + 4
                                tag_w = custom_tag_surf.get_width() + 4
                                tag_h = custom_tag_surf.get_height() + 2
                                
                                pygame.draw.rect(self.screen, (25, 215, 0), (tag_x, tag_y, tag_w, tag_h), border_radius=3)
                                self.screen.blit(custom_tag_surf, (tag_x + 2, tag_y + 1))
                            
                            chart_data = selected_song["charts"].get("Medium" if diff_name == "Dynamic" else diff_name, [])
                            notes_count = len(chart_data)
                            
                            duration = selected_song.get("duration", 60.0)
                            if duration <= 0:
                                duration = 60.0
                            density = notes_count / duration
                            level = max(1, min(15, int(density * 2.5) + 1))
                            
                            steps_str = f"{notes_count} notes  |  BPM: {display_bpm:.0f}  |  Lv.{level}"
                            if diff_name == "Dynamic":
                                steps_str += " (Dyn)"
                                
                            steps_surf = tiny_font.render(steps_str, True, (210, 210, 220) if is_selected or self.is_dark_theme(theme) else (80, 80, 90))
                            self.screen.blit(steps_surf, (card_x + 45, y_pos + 17))
                            
                            high_scores = selected_song.get("high_scores", {})
                            record = high_scores.get(diff_name)
                            if record:
                                rec_str = f"Score: {record['score']:07d} ({record['grade']})"
                                rec_surf = small_font.render(rec_str, True, (255, 215, 0) if not is_selected else (255, 255, 255))
                            else:
                                rec_str = "No Record"
                                rec_surf = small_font.render(rec_str, True, (130, 120, 140) if not is_selected else (200, 200, 200))
                            self.screen.blit(rec_surf, (card_x + card_w - 45 - rec_surf.get_width(), y_pos + 8))
                            
                        if start_idx + max_visible < len(displayed_diffs):
                            down_ind = tiny_font.render("▼", True, accent_color)
                            self.screen.blit(down_ind, (card_x + card_w // 2 - down_ind.get_width() // 2, list_start_y + max_visible * (row_h + row_spacing) - 4))
                            
                        visible_count = min(max_visible, len(displayed_diffs))
                        diff_list_end_y = list_start_y + visible_count * (row_h + row_spacing)
                    
                    speed_y = diff_list_end_y + 12
                    self.speed_y = speed_y
                    
                    # Draw Playback Speed Selector on Card
                    speed_lbl = small_font.render("PLAYBACK SPEED:", True, text_color)
                    self.screen.blit(speed_lbl, (card_x + 30, speed_y + 4))
                    
                    # Left Arrow Box
                    left_box = pygame.Rect(card_x + 190, speed_y, 26, 22)
                    left_hover = left_box.collidepoint(mx, my)
                    left_col = (50, 40, 75) if left_hover else (30, 22, 45)
                    pygame.draw.rect(self.screen, left_col, left_box, border_radius=4)
                    pygame.draw.rect(self.screen, (60, 55, 75), left_box, width=1, border_radius=4)
                    left_text = tiny_font.render("◄", True, (0, 255, 204) if left_hover else text_color)
                    self.screen.blit(left_text, (left_box.centerx - left_text.get_width() // 2, left_box.centery - left_text.get_height() // 2 - 1))
                    
                    # Value
                    val_str = f"{speed_mult:.2f}x"
                    val_surf = small_font.render(val_str, True, (0, 255, 204) if speed_mult != 1.0 else text_color)
                    self.screen.blit(val_surf, (card_x + 242 - val_surf.get_width() // 2, speed_y + 2))
                    
                    # Right Arrow Box
                    right_box = pygame.Rect(card_x + 268, speed_y, 26, 22)
                    right_hover = right_box.collidepoint(mx, my)
                    right_col = (50, 40, 75) if right_hover else (30, 22, 45)
                    pygame.draw.rect(self.screen, right_col, right_box, border_radius=4)
                    pygame.draw.rect(self.screen, (60, 55, 75), right_box, width=1, border_radius=4)
                    right_text = tiny_font.render("►", True, (0, 255, 204) if right_hover else text_color)
                    self.screen.blit(right_text, (right_box.centerx - right_text.get_width() // 2, right_box.centery - right_text.get_height() // 2 - 1))
                    
                    btn_y = speed_y + 45
                    self.btn_y = btn_y
                    edit_btn_rect = pygame.Rect(card_x + 30, btn_y, 175, 36)
                    delete_btn_rect = pygame.Rect(card_x + 225, btn_y, 175, 36)
                    
                    edit_hover = edit_btn_rect.collidepoint(mx, my)
                    delete_hover = delete_btn_rect.collidepoint(mx, my)
                    
                    edit_color = (180, 40, 120) if edit_hover else (140, 30, 90)
                    pygame.draw.rect(self.screen, edit_color, edit_btn_rect, border_radius=6)
                    btn_lbl_font = pygame.font.SysFont("Trebuchet MS" if theme == "DDR-Retro" else "Segoe UI", 14, bold=True)
                    edit_btn_lbl = btn_lbl_font.render("EDIT CHART", True, (255, 255, 255))
                    self.screen.blit(edit_btn_lbl, (edit_btn_rect.centerx - edit_btn_lbl.get_width() // 2, edit_btn_rect.centery - edit_btn_lbl.get_height() // 2))
                    
                    if selected_song["filename"] != "Retro_Beat.wav":
                        del_color = (220, 50, 50) if delete_hover else (180, 40, 40)
                        pygame.draw.rect(self.screen, del_color, delete_btn_rect, border_radius=6)
                        del_lbl = btn_lbl_font.render("DELETE SONG", True, (255, 255, 255))
                        self.screen.blit(del_lbl, (delete_btn_rect.centerx - del_lbl.get_width() // 2, delete_btn_rect.centery - del_lbl.get_height() // 2))
                        
                elif item["type"] == "group":
                    # Display Album/Folder contents
                    title_end_y = draw_wrapped_text(self.screen, menu_font, f"ALBUM: {item['name'].upper()}", text_color, card_x + 30, 295, card_w - 60)
                    pygame.draw.line(self.screen, (60, 55, 75), (card_x + 30, title_end_y + 10), (card_x + card_w - 30, title_end_y + 10), 1)
                    
                    y_list = title_end_y + 25
                    lbl_inside = small_font.render("SONGS IN THIS ALBUM:", True, (255, 215, 0))
                    self.screen.blit(lbl_inside, (card_x + 30, y_list))
                    y_list += 30
                    
                    for song_idx, s in enumerate(item["songs"][:5]):
                        s_lbl = desc_font.render(f"- {s['title']}", True, text_color)
                        self.screen.blit(s_lbl, (card_x + 40, y_list))
                        y_list += 28
                        
                    if len(item["songs"]) > 5:
                        s_lbl = desc_font.render(f"... and {len(item['songs']) - 5} more songs", True, (160, 160, 165))
                        self.screen.blit(s_lbl, (card_x + 40, y_list))
                        
                    hint_lbl = desc_font.render("Press ENTER to expand or collapse folder", True, accent_color)
                    self.screen.blit(hint_lbl, (card_x + card_w // 2 - hint_lbl.get_width() // 2, 580))
                    
                elif item["type"] == "upload":
                    # Display Upload Card info
                    upload_title = menu_font.render("UPLOAD SONG", True, text_color)
                    self.screen.blit(upload_title, (card_x + 30, 295))
                    
                    info1 = desc_font.render("Add your own MP3 or WAV files!", True, text_color)
                    info2 = desc_font.render("Our AI-based analyzer will:", True, text_color)
                    self.screen.blit(info1, (card_x + 30, 340))
                    self.screen.blit(info2, (card_x + 30, 380))
                    
                    bullets = [
                        "- Detect the rhythm & BPM",
                        "- Locate all percussion peaks",
                        "- Generate 5 synced charts",
                        "- Save to songs library"
                    ]
                    for b_idx, b in enumerate(bullets):
                        b_surf = desc_font.render(b, True, accent_color)
                        self.screen.blit(b_surf, (card_x + 50, 420 + b_idx * 32))
                        
                    upload_hint = desc_font.render("Press ENTER to Browse PC", True, accent_color)
                    self.screen.blit(upload_hint, (card_x + card_w // 2 - upload_hint.get_width() // 2, 580))
                    
            footer = small_font.render("ESC: Back | Up/Down: Select Song | ENTER: Confirm", True, text_color)
            self.screen.blit(footer, (w // 2 - footer.get_width() // 2, h - 40))
            
            # Hover tooltip check
            mx, my = pygame.mouse.get_pos()
            hovered_song = None
            if (60 <= mx <= 490) and total_items > 0:
                start_row = max(0, min(self.song_index - visible_rows // 2, total_items - visible_rows))
                for row_idx in range(visible_rows):
                    item_idx = start_row + row_idx
                    if item_idx >= total_items:
                        break
                    y_pos = 140 + row_idx * 50
                    if (y_pos - 10 <= my <= y_pos + 32):
                        itm = self.display_list[item_idx]
                        if itm["type"] == "song":
                            hovered_song = itm["song"]
                        break
                        
            if hovered_song:
                high_scores = hovered_song.get("high_scores", {})
                tx = mx + 20
                ty = my + 10
                tw = 260
                th = 190
                if tx + tw > w:
                    tx = mx - tw - 10
                if ty + th > h:
                    ty = h - th - 10- 10
                    
                tooltip_surf = pygame.Surface((tw, th), pygame.SRCALPHA)
                tooltip_surf.fill((20, 16, 32, 235) if self.is_dark_theme(theme) else (240, 240, 245, 245))
                pygame.draw.rect(tooltip_surf, (0, 255, 204, 150) if self.is_dark_theme(theme) else (0, 122, 255, 150), (0, 0, tw, th), width=2, border_radius=8)
                
                tt_font = pygame.font.SysFont("Trebuchet MS" if theme == "DDR-Retro" else "Segoe UI", 14, bold=True)
                title_surf = tt_font.render(hovered_song["title"].upper(), True, text_color)
                tooltip_surf.blit(title_surf, (15, 12))
                
                pygame.draw.line(tooltip_surf, (60, 50, 80) if self.is_dark_theme(theme) else (200, 200, 205), (15, 32), (tw - 15, 32), 1)
                
                sub_font = pygame.font.SysFont("Courier New" if theme == "DDR-Retro" else "Segoe UI", 13)
                diff_list = ["Easy", "Medium", "Hard", "Harder", "Crazy", "Dynamic", "Custom"]
                
                for idx, df in enumerate(diff_list):
                    df_y = 42 + idx * 19
                    record = high_scores.get(df)
                    if record:
                        score_str = f"{record['score']:07d} ({record['grade']})"
                        score_color = (255, 215, 0)
                    else:
                        score_str = "-------"
                        score_color = (130, 120, 140) if self.is_dark_theme(theme) else (160, 160, 165)
                        
                    lbl_s = sub_font.render(f"{df.upper()}:", True, text_color)
                    val_s = sub_font.render(score_str, True, score_color)
                    
                    tooltip_surf.blit(lbl_s, (15, df_y))
                    tooltip_surf.blit(val_s, (110, df_y))
                    
                self.screen.blit(tooltip_surf, (tx, ty))

            # Warning Notification overlay
            if self.warning_notification_timer > 0:
                box_w = 520
                box_h = 75
                box_x = w // 2 - box_w // 2
                box_y = h // 2 - box_h // 2
                pygame.draw.rect(self.screen, (20, 15, 30), (box_x, box_y, box_w, box_h), border_radius=10)
                pygame.draw.rect(self.screen, (255, 45, 85), (box_x, box_y, box_w, box_h), width=3, border_radius=10)
                warn_font = pygame.font.SysFont("Trebuchet MS" if theme == "DDR-Retro" else "Segoe UI", 20, bold=True)
                warn_surf = warn_font.render(self.warning_notification, True, (255, 230, 235))
                self.screen.blit(warn_surf, (box_x + box_w // 2 - warn_surf.get_width() // 2, box_y + box_h // 2 - warn_surf.get_height() // 2))

        # --- DRAW STATE: MODE_SELECT ---
        elif self.state == "MODE_SELECT":
            # Draw Mode Selection Screen
            title_text = "CHOOSE GAME MODE"
            title_surf = title_font.render(title_text, True, text_color)
            self.screen.blit(title_surf, (w // 2 - title_surf.get_width() // 2, 80))
            
            help_surf = small_font.render("USE LEFT / RIGHT ARROWS TO SELECT, ENTER TO CONFIRM, ESC TO GO BACK", True, (130, 120, 140) if self.is_dark_theme(theme) else (90, 80, 100))
            self.screen.blit(help_surf, (w // 2 - help_surf.get_width() // 2, h - 80))
            
            card_w = 165
            card_h = 300
            spacing = 20
            total_w = len(self.mode_options) * card_w + (len(self.mode_options) - 1) * spacing
            start_x = w // 2 - total_w // 2
            card_y = 180
            
            for idx, opt in enumerate(self.mode_options):
                is_selected = (idx == self.mode_index)
                x_pos = start_x + idx * (card_w + spacing)
                card_rect = pygame.Rect(x_pos, card_y, card_w, card_h)
                
                # Check hover
                is_hover = card_rect.collidepoint(mx, my)
                if is_hover and not is_selected:
                    self.mode_index = idx
                    is_selected = True
                
                # Draw Card background
                bg_col = (40, 20, 75, 200) if is_selected else (15, 10, 25, 160)
                if not self.is_dark_theme(theme):
                    bg_col = (220, 210, 235, 200) if is_selected else (240, 240, 245, 160)
                    
                border_col = accent_color if is_selected else ((60, 50, 85) if self.is_dark_theme(theme) else (200, 200, 205))
                
                # Card surface
                card_surf = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
                pygame.draw.rect(card_surf, bg_col, (0, 0, card_w, card_h), border_radius=12)
                pygame.draw.rect(card_surf, border_col, (0, 0, card_w, card_h), width=3 if is_selected else 1, border_radius=12)
                
                # Draw visual graphic based on mode
                graphic_y = 120
                if opt == "SOLO":
                    pygame.draw.circle(card_surf, border_col, (card_w // 2, graphic_y), 30, width=2)
                    pygame.draw.circle(card_surf, accent_color if is_selected else border_col, (card_w // 2, graphic_y + 4), 14)
                elif opt == "CO-OP":
                    pygame.draw.circle(card_surf, border_col, (card_w // 2 - 15, graphic_y), 24, width=2)
                    pygame.draw.circle(card_surf, accent_color if is_selected else border_col, (card_w // 2 + 15, graphic_y), 24, width=2)
                elif opt == "VERSUS":
                    pygame.draw.line(card_surf, border_col, (card_w // 2 - 25, graphic_y - 25), (card_w // 2 + 25, graphic_y + 25), width=4)
                    pygame.draw.line(card_surf, accent_color if is_selected else border_col, (card_w // 2 + 25, graphic_y - 25), (card_w // 2 - 25, graphic_y + 25), width=4)
                elif opt == "FNF":
                    pygame.draw.circle(card_surf, border_col, (card_w // 2, graphic_y - 10), 16)
                    pygame.draw.line(card_surf, accent_color if is_selected else border_col, (card_w // 2, graphic_y + 6), (card_w // 2, graphic_y + 30), width=6)
                elif opt == "PRACTICE":
                    pygame.draw.circle(card_surf, border_col, (card_w // 2, graphic_y), 25, width=2)
                    pygame.draw.circle(card_surf, accent_color if is_selected else border_col, (card_w // 2, graphic_y), 10)
                
                # Option text
                opt_font = pygame.font.SysFont("Trebuchet MS" if theme == "DDR-Retro" else "Segoe UI", 24, bold=True)
                text_surf = opt_font.render(opt, True, text_color)
                card_surf.blit(text_surf, (card_w // 2 - text_surf.get_width() // 2, 30))
                
                # Mode description
                desc_lines = []
                if opt == "SOLO":
                    desc_lines = ["1 Player", "Standard DDR", "Speed Mods"]
                elif opt == "CO-OP":
                    desc_lines = ["2 Players", "Shared Score", "Team Work"]
                elif opt == "VERSUS":
                    desc_lines = ["2 Players", "Head-to-head", "Battle Mode"]
                elif opt == "FNF":
                    desc_lines = ["2 Players", "Call & Response", "Vocal Duel"]
                elif opt == "PRACTICE":
                    desc_lines = ["1 Player", "Loop Section", "Improve Skill"]
                    
                for i, line in enumerate(desc_lines):
                    line_surf = small_font.render(line, True, (210, 200, 220) if is_selected else (140, 130, 150))
                    card_surf.blit(line_surf, (card_w // 2 - line_surf.get_width() // 2, 200 + i * 22))
                
                self.screen.blit(card_surf, (x_pos, card_y))

        # --- DRAW STATE: LOBBY ---
        elif self.state == "LOBBY":
            mode_name = self.mode_options[self.mode_index]
            title_text = f"{mode_name} MODE LOBBY"
            title_surf = title_font.render(title_text, True, text_color)
            self.screen.blit(title_surf, (w // 2 - title_surf.get_width() // 2, 60))
            
            help_surf = small_font.render("USE UP / DOWN ARROWS TO NAVIGATE, LEFT / RIGHT TO CHANGE VALUES, ENTER TO PROCEED, ESC TO GO BACK", True, (130, 120, 140) if self.is_dark_theme(theme) else (90, 80, 100))
            self.screen.blit(help_surf, (w // 2 - help_surf.get_width() // 2, h - 50))
            
            lobby_items = self.get_lobby_items()
            lobby_h = len(lobby_items) * 45
            start_y = h // 2 - lobby_h // 2 - 20
            
            card_w = 600
            card_x = w // 2 - card_w // 2
            
            bg_panel_col = (20, 15, 30, 200) if self.is_dark_theme(theme) else (235, 235, 240, 200)
            pygame.draw.rect(self.screen, bg_panel_col, (card_x - 30, start_y - 20, card_w + 60, lobby_h + 40), border_radius=12)
            pygame.draw.rect(self.screen, (50, 45, 70) if self.is_dark_theme(theme) else (200, 200, 205), (card_x - 30, start_y - 20, card_w + 60, lobby_h + 40), width=1, border_radius=12)
            
            for idx, item in enumerate(lobby_items):
                is_selected = (idx == self.lobby_selection_index)
                y_pos = start_y + idx * 45
                
                row_rect = pygame.Rect(card_x, y_pos, card_w, 36)
                if row_rect.collidepoint(mx, my):
                    self.lobby_selection_index = idx
                    is_selected = True
                
                if is_selected:
                    sel_col = (50, 40, 75, 160) if self.is_dark_theme(theme) else (210, 210, 225, 160)
                    pygame.draw.rect(self.screen, sel_col, row_rect, border_radius=6)
                    pygame.draw.rect(self.screen, accent_color, row_rect, width=1, border_radius=6)
                    
                lbl_color = accent_color if is_selected else text_color
                lbl_surf = small_font.render(item["label"], True, lbl_color)
                self.screen.blit(lbl_surf, (card_x + 15, y_pos + 6))
                
                if item["type"] == "value":
                    if getattr(self, "lobby_edit_mode", None) == item["key"]:
                        cursor = "_" if (int(time.time() * 2) % 2 == 0) else ""
                        val_str = f"[{self.lobby_edit_buffer}{cursor}]"
                        val_surf = small_font.render(val_str, True, (255, 128, 0))
                    else:
                        val_str = item["value_text"]
                        val_surf = small_font.render(f"◄  {val_str}  ►", True, text_color)
                    self.screen.blit(val_surf, (card_x + card_w - val_surf.get_width() - 15, y_pos + 6))
                elif item["type"] == "link":
                    link_str = "PRESS ENTER TO REMAP" if is_selected else item.get("value_text", "PRESS ENTER TO REMAP")
                    link_surf = small_font.render(link_str, True, (0, 255, 204) if is_selected else (130, 120, 140))
                    self.screen.blit(link_surf, (card_x + card_w - link_surf.get_width() - 15, y_pos + 6))
                elif item["type"] == "action":
                    action_surf = small_font.render("CONFIRM", True, (0, 255, 100) if is_selected else text_color)
                    self.screen.blit(action_surf, (card_x + card_w - action_surf.get_width() - 15, y_pos + 6))

        # --- DRAW STATE: DIFFICULTY_SELECT_OVERLAY ---
        elif self.state == "DIFFICULTY_SELECT_OVERLAY":
            item = self.display_list[self.song_index]
            selected_song = item["song"]
            
            # Draw dimmer background with song cover
            self.screen.blit(self.get_song_cover_surface(item, theme), (w // 2 - 185, 30))
            
            overlay_rect = pygame.Rect(80, 150, w - 160, h - 220)
            bg_panel_col = (15, 10, 25, 230) if self.is_dark_theme(theme) else (240, 240, 245, 230)
            pygame.draw.rect(self.screen, bg_panel_col, overlay_rect, border_radius=12)
            pygame.draw.rect(self.screen, accent_color, overlay_rect, width=2, border_radius=12)
            
            # Title
            title_surf = menu_font.render(f"CHOOSE DIFFICULTY: {selected_song['title'].upper()}", True, text_color)
            self.screen.blit(title_surf, (w // 2 - title_surf.get_width() // 2, 90))
            
            # Panels
            panel_w = 380
            panel_h = 360
            
            # Draw Player 1 Panel
            p1_x = 100
            p1_y = 170
            p1_rect = pygame.Rect(p1_x, p1_y, panel_w, panel_h)
            pygame.draw.rect(self.screen, (25, 20, 45) if self.is_dark_theme(theme) else (225, 225, 235), p1_rect, border_radius=8)
            pygame.draw.rect(self.screen, (50, 40, 75) if self.is_dark_theme(theme) else (190, 190, 205), p1_rect, width=1, border_radius=8)
            
            p1_hdr = small_font.render("PLAYER 1 (LEFT)", True, (0, 255, 204))
            self.screen.blit(p1_hdr, (p1_x + 20, p1_y + 15))
            
            # Draw Player 2 Panel
            p2_x = w - 100 - panel_w
            p2_y = 170
            p2_rect = pygame.Rect(p2_x, p2_y, panel_w, panel_h)
            
            if settings.players == 2:
                pygame.draw.rect(self.screen, (25, 20, 45) if self.is_dark_theme(theme) else (225, 225, 235), p2_rect, border_radius=8)
                pygame.draw.rect(self.screen, (50, 40, 75) if self.is_dark_theme(theme) else (190, 190, 205), p2_rect, width=1, border_radius=8)
                
                # Check FNF mode match type to see if AI
                active_match = self.fnf_match_types[self.fnf_match_type_index] if settings.game_mode == "FNF" else ""
                p2_is_ai = False
                if active_match and len(active_match.split(" vs ")) > 1:
                    p2_is_ai = "AI" in active_match.split(" vs ")[1]
                p2_label = "PLAYER 2 (AI OPPONENT)" if p2_is_ai else "PLAYER 2 (RIGHT)"
                
                p2_hdr = small_font.render(p2_label, True, (255, 45, 85))
                self.screen.blit(p2_hdr, (p2_x + 20, p2_y + 15))
            else:
                # 1 Player mode: Player 2 panel is empty/hidden
                pygame.draw.rect(self.screen, (15, 12, 28) if self.is_dark_theme(theme) else (235, 235, 240), p2_rect, border_radius=8)
                p2_hdr = small_font.render("NO OPPONENT", True, (120, 110, 130))
                self.screen.blit(p2_hdr, (p2_x + 20, p2_y + 15))
                
                mid_lbl = small_font.render("SOLO MODE ACTIVE", True, (130, 120, 140))
                self.screen.blit(mid_lbl, (p2_x + panel_w // 2 - mid_lbl.get_width() // 2, p2_y + panel_h // 2 - 10))
            
            # Render difficulties lists inside panels
            tiny_font = pygame.font.SysFont("Trebuchet MS" if theme == "DDR-Retro" else "Segoe UI", 12)
            for p_idx in [1, 2]:
                if p_idx == 2 and settings.players == 1:
                    continue
                    
                px = p1_x if p_idx == 1 else p2_x
                py = p1_y if p_idx == 1 else p2_y
                p_ready = self.p1_ready if p_idx == 1 else self.p2_ready
                p_diff_idx = self.p1_diff_index if p_idx == 1 else self.p2_diff_index
                
                if p_ready:
                    # Draw Ready Banner
                    r_lbl = menu_font.render("READY!", True, (0, 255, 100))
                    self.screen.blit(r_lbl, (px + panel_w // 2 - r_lbl.get_width() // 2, py + panel_h // 2 - 30))
                    
                    h_lbl = small_font.render("PRESS BACKSPACE/SHIFT TO CANCEL", True, (130, 120, 140))
                    self.screen.blit(h_lbl, (px + panel_w // 2 - h_lbl.get_width() // 2, py + panel_h // 2 + 20))
                else:
                    # Draw difficulty options list
                    list_start_y = py + 60
                    row_h = 42
                    
                    for d_idx, df in enumerate(self.difficulties):
                        is_sel = (d_idx == p_diff_idx)
                        row_rect = pygame.Rect(px + 20, list_start_y + d_idx * row_h, panel_w - 40, 36)
                        
                        # Mouse hover select
                        if row_rect.collidepoint(mx, my):
                            if p_idx == 1:
                                self.p1_diff_index = d_idx
                            else:
                                self.p2_diff_index = d_idx
                            is_sel = True
                        
                        bg_c = (50, 40, 75) if is_sel else (30, 22, 45)
                        if not self.is_dark_theme(theme):
                            bg_c = (210, 210, 225) if is_sel else (240, 240, 245)
                            
                        border_c = accent_color if is_sel else ((60, 55, 75) if self.is_dark_theme(theme) else (200, 200, 205))
                        
                        pygame.draw.rect(self.screen, bg_c, row_rect, border_radius=6)
                        pygame.draw.rect(self.screen, border_c, row_rect, width=2 if is_sel else 1, border_radius=6)
                        
                        df_color = theme_manager.get_lane_color(d_idx % 5, theme)
                        pygame.draw.circle(self.screen, df_color, (row_rect.x + 20, row_rect.centery), 6)
                        
                        df_surf = small_font.render(df.upper(), True, text_color)
                        self.screen.blit(df_surf, (row_rect.x + 40, row_rect.centery - df_surf.get_height() // 2))
                        
                        # Note count
                        notes_count = len(selected_song["charts"].get(df if df != "Dynamic" else "Medium", []))
                        n_surf = tiny_font.render(f"{notes_count} notes", True, (130, 120, 140))
                        self.screen.blit(n_surf, (row_rect.x + row_rect.width - n_surf.get_width() - 15, row_rect.centery - n_surf.get_height() // 2))
                        
            footer = small_font.render("P1: WASD/Arrows, Enter to ready | P2: IJKL/Numpad, Keypad Enter/Tab to ready | ESC: Back", True, text_color)
            self.screen.blit(footer, (w // 2 - footer.get_width() // 2, h - 40))

        # --- DRAW STATE: ANALYZING ---
        elif self.state == "ANALYZING":
            # Loading screen
            title_surf = menu_font.render("ANALYZING AUDIO TRACK", True, text_color)
            self.screen.blit(title_surf, (w // 2 - title_surf.get_width() // 2, h // 2 - 140))
            
            prog_surf = desc_font.render(self.analysis_progress_text, True, accent_color)
            self.screen.blit(prog_surf, (w // 2 - prog_surf.get_width() // 2, h // 2 - 80))
            
            # --- CUTE PIXEL-STYLE CAT PAW KNEADING ANIMATION ---
            ticks = pygame.time.get_ticks()
            paw_bob = math.sin(ticks * 0.006) * 14
            toe_squeeze = 0.8 + 0.25 * math.sin(ticks * 0.012)
            
            paw_x = w // 2
            paw_y = h // 2 + 40 + paw_bob
            
            fur_col = (255, 255, 255) # Fluffy white cat fur
            pad_col = (255, 180, 200) # Soft pink toe pads
            shadow_col = (220, 220, 225) # Soft light grey for border/shadow
            
            # Draw arm extending from bottom
            arm_w = 64
            arm_h = h - (paw_y + 10)
            pygame.draw.rect(self.screen, fur_col, (paw_x - arm_w // 2, paw_y, arm_w, arm_h), border_radius=18)
            pygame.draw.rect(self.screen, shadow_col, (paw_x - arm_w // 2, paw_y, arm_w, arm_h), width=2, border_radius=18)
            
            # Draw main paw circle
            pygame.draw.circle(self.screen, fur_col, (paw_x, paw_y), 32)
            pygame.draw.circle(self.screen, shadow_col, (paw_x, paw_y), 32, width=2)
            
            # Draw main pink pad (heart/beans shape)
            pygame.draw.circle(self.screen, pad_col, (paw_x, paw_y + 4), 16)
            
            # Draw 4 toe pads (expanding/kneading on bob)
            toes = [
                (-22 * toe_squeeze, -10),
                (-9 * toe_squeeze, -20),
                (9 * toe_squeeze, -20),
                (22 * toe_squeeze, -10)
            ]
            for dx, dy in toes:
                # Fur background for toe
                pygame.draw.circle(self.screen, fur_col, (int(paw_x + dx), int(paw_y + dy)), 10)
                pygame.draw.circle(self.screen, shadow_col, (int(paw_x + dx), int(paw_y + dy)), 10, width=2)
                # Pink bean
                pygame.draw.circle(self.screen, pad_col, (int(paw_x + dx), int(paw_y + dy)), 6)
            
            # Cute Cat Quote/Tip
            if getattr(self, "last_tip_state", None) != "ANALYZING":
                import random
                self.active_tip = random.choice(self.loading_tips)
                self.last_tip_state = "ANALYZING"
            tip_surf = small_font.render(self.active_tip, True, (244, 143, 177) if self.is_dark_theme(theme) else (180, 50, 90))
            self.screen.blit(tip_surf, (w // 2 - tip_surf.get_width() // 2, h // 2 + 140))

        # --- DRAW STATE: GAMEPLAY ---
        elif self.state == "GAMEPLAY" and self.gameplay:
            if getattr(self.gameplay, "shake_timer", 0.0) > 0.0:
                temp_surf = pygame.Surface((w, h))
                self.gameplay.draw(temp_surf)
                import random
                dx = random.randint(-int(self.gameplay.shake_intensity), int(self.gameplay.shake_intensity))
                dy = random.randint(-int(self.gameplay.shake_intensity), int(self.gameplay.shake_intensity))
                self.screen.blit(temp_surf, (dx, dy))
            else:
                self.gameplay.draw(self.screen)

        # --- DRAW STATE: EDITOR ---
        elif self.state == "EDITOR" and self.editor:
            self.editor.draw(self.screen)

        # --- DRAW STATE: CALIBRATION ---
        elif self.state == "CALIBRATION":
            # Draw header
            header_surf = menu_font.render("AUDIO LATENCY CALIBRATOR", True, text_color)
            self.screen.blit(header_surf, (w // 2 - header_surf.get_width() // 2, 80))
            
            sub_surf = desc_font.render("Tap SPACE exactly on the chime metronome beats!", True, text_color)
            self.screen.blit(sub_surf, (w // 2 - sub_surf.get_width() // 2, 130))
            
            # Pulsing Metronome Circle
            pulse_r = int(50 + 20 * self.calib_flash)
            pulse_color = (max(0, min(255, accent_color[0] + int(self.calib_flash * 100))),
                           max(0, min(255, accent_color[1] + int(self.calib_flash * 100))),
                           max(0, min(255, accent_color[2] + int(self.calib_flash * 100))))
            
            # Draw pulse circles
            pygame.draw.circle(self.screen, pulse_color, (w // 2, h // 2 - 80), pulse_r)
            pygame.draw.circle(self.screen, text_color, (w // 2, h // 2 - 80), 50, width=3)
            
            # Draw Beat indicator dot/lines in the center of circle
            beat_lbl = title_font.render("BEAT", True, (255, 255, 255) if self.calib_flash > 0.5 else text_color)
            self.screen.blit(beat_lbl, (w // 2 - beat_lbl.get_width() // 2, h // 2 - 110))
            
            # Target line & tap history timeline (Y = h // 2 + 100)
            timeline_y = h // 2 + 70
            pygame.draw.line(self.screen, (100, 100, 110), (w // 2 - 200, timeline_y), (w // 2 + 200, timeline_y), 3)
            # Center target line (green)
            pygame.draw.line(self.screen, (0, 255, 128), (w // 2, timeline_y - 20), (w // 2, timeline_y + 20), 4)
            
            # Early / Late labels
            early_lbl = small_font.render("EARLY (-150ms)", True, (255, 100, 100) if self.is_dark_theme(theme) else (200, 50, 50))
            late_lbl = small_font.render("LATE (+150ms)", True, (255, 100, 100) if self.is_dark_theme(theme) else (200, 50, 50))
            self.screen.blit(early_lbl, (w // 2 - 200, timeline_y - 35))
            self.screen.blit(late_lbl, (w // 2 + 200 - late_lbl.get_width(), timeline_y - 35))
            
            # Draw tap markers on the timeline (mapping +/-150ms to +/- 200px)
            for diff in self.calib_taps:
                diff_ms = diff * 1000.0
                offset_x = int((diff_ms / 150.0) * 200)
                offset_x = max(-200, min(200, offset_x))
                # Draw a glowing dot
                pygame.draw.circle(self.screen, (255, 215, 0), (w // 2 + offset_x, timeline_y), 8)
                pygame.draw.circle(self.screen, (255, 255, 255), (w // 2 + offset_x, timeline_y), 8, width=1)
                
            # Calculations & stats
            avg_offset_s = sum(self.calib_taps) / len(self.calib_taps) if self.calib_taps else 0.0
            avg_offset_ms = int(avg_offset_s * 1000)
            
            status_str = f"TAPS RECORDED: {len(self.calib_taps)} / 12"
            status_surf = desc_font.render(status_str, True, text_color)
            self.screen.blit(status_surf, (w // 2 - status_surf.get_width() // 2, timeline_y + 40))
            
            if self.calib_taps:
                sign = "+" if avg_offset_ms >= 0 else ""
                offset_str = f"CALCULATED LATENCY OFFSET: {sign}{avg_offset_ms} ms"
                color_offset = (0, 255, 128) if abs(avg_offset_ms) < 30 else (255, 165, 0)
                offset_surf = menu_font.render(offset_str, True, color_offset)
                self.screen.blit(offset_surf, (w // 2 - offset_surf.get_width() // 2, timeline_y + 75))
            else:
                offset_surf = desc_font.render("TAP SPACE TO CALCULATE LATENCY...", True, (130, 130, 140))
                self.screen.blit(offset_surf, (w // 2 - offset_surf.get_width() // 2, timeline_y + 75))
                
            # Control instructions at bottom
            footer1_str = "ENTER: Save & Apply Offset  |  ESC: Discard & Exit"
            footer1_surf = desc_font.render(footer1_str, True, accent_color)
            self.screen.blit(footer1_surf, (w // 2 - footer1_surf.get_width() // 2, h - 90))

        # --- DRAW STATE: SETTINGS ---
        elif self.state == "SETTINGS":
            header_surf = menu_font.render("SETTINGS & CONTROLS", True, text_color)
            self.screen.blit(header_surf, (w // 2 - header_surf.get_width() // 2, 60))
            
            opts = self.get_settings_options()
            
            # Scroll indicator top
            if self.settings_scroll_y > 0:
                up_surf = small_font.render("▲  MORE SETTINGS ABOVE  ▲", True, accent_color)
                self.screen.blit(up_surf, (w // 2 - up_surf.get_width() // 2, 105))
                
            for i in range(12):
                idx = self.settings_scroll_y + i
                if idx >= len(opts):
                    break
                opt = opts[idx]
                is_selected = (idx == self.settings_index)
                y_box = 125 + i * 38
                
                if opt.startswith("---"):
                    # Section Header
                    section_title = opt.replace("---", "").strip()
                    hdr_font = pygame.font.SysFont("Trebuchet MS" if theme == "DDR-Retro" else "Segoe UI", 16, bold=True)
                    hdr_surf = hdr_font.render(section_title, True, (0, 255, 204) if theme == "DDR-Retro" else (0, 122, 255))
                    self.screen.blit(hdr_surf, (w // 2 - 240, y_box + 4))
                    # Draw a thin underline for section
                    pygame.draw.line(self.screen, (60, 50, 80) if theme == "DDR-Retro" else (220, 220, 225), (w // 2 - 240, y_box + 22), (w // 2 + 240, y_box + 22), 1)
                    continue

                opt_color = accent_color if is_selected else text_color
                label_text = opt
                value_text = ""
                
                if opt == "THEME":
                    value_text = settings.theme
                elif opt == "PLAYERS":
                    value_text = f"{settings.players} Player(s)"
                elif opt == "GAME MODE":
                    value_text = settings.game_mode
                elif opt.startswith("P") and "CHARACTER" in opt:
                    p_num = int(opt[1])
                    value_text = self.get_player_char(p_num)
                elif opt.startswith("P") and "DEVICE" in opt:
                    p_num = int(opt[1])
                    value_text = self.get_player_dev(p_num)
                elif opt == "MUSIC VOLUME":
                    value_text = f"{int(settings.music_volume * 100)}%"
                elif opt == "SFX VOLUME":
                    value_text = f"{int(settings.sfx_volume * 100)}%"
                elif opt == "SHOW CONSOLE":
                    value_text = "ENABLED" if settings.show_console else "DISABLED"
                elif opt == "ASSIST TICK":
                    value_text = "ENABLED" if settings.assist_tick else "DISABLED"
                elif opt == "AUDIO OFFSET":
                    value_text = f"{int(settings.audio_offset * 1000)} ms"
                elif opt == "PROPORTIONAL SCORING":
                    value_text = "ON (ACCURACY)" if getattr(settings, "proportional_scoring", False) else "OFF (FLAT)"
                elif opt == "MISS PENALTY":
                    curr_pen = getattr(settings, "miss_penalty", 0)
                    value_text = "DISABLED" if curr_pen == 0 else f"-{curr_pen} PTS"
                elif opt == "PLAYBACK SPEED":
                    value_text = f"{getattr(settings, 'playback_speed', 1.0):.2f}x"
                elif opt == "CALIBRATE LATENCY":
                    value_text = "[ Press Enter ]"
                elif "REMAP" in opt:
                    value_text = "[ Press Enter ]"
                
                # Print Left/Right indicator on selections
                if opt in ["PLAYERS", "GAME MODE", "MUSIC VOLUME", "SFX VOLUME", "SHOW CONSOLE", "THEME", "AUDIO OFFSET", "ASSIST TICK", "PROPORTIONAL SCORING", "MISS PENALTY", "PLAYBACK SPEED"] or ("CHARACTER" in opt) or ("DEVICE" in opt):
                    if is_selected:
                        value_text = f"<  {value_text}  >"

                # Draw selector bar for Minimalist
                if theme == "Minimalist" and is_selected:
                    pygame.draw.rect(self.screen, (230, 230, 235), (w // 2 - 250, y_box, 500, 32), border_radius=6)

                # Render option label
                lbl_surf = desc_font.render(label_text, True, opt_color)
                self.screen.blit(lbl_surf, (w // 2 - 230, y_box + 2))
                
                # Render option value
                val_surf = desc_font.render(value_text, True, opt_color if is_selected else accent_color)
                self.screen.blit(val_surf, (w // 2 + 220 - val_surf.get_width(), y_box + 2))
                
            # Scroll indicator bottom
            if self.settings_scroll_y + 12 < len(opts):
                down_surf = small_font.render("▼  MORE SETTINGS BELOW  ▼", True, accent_color)
                self.screen.blit(down_surf, (w // 2 - down_surf.get_width() // 2, 125 + 12 * 38))
                
            footer = small_font.render("ESC: Title Menu | Up/Down: Navigate | Left/Right/Enter: Adjust", True, text_color)
            self.screen.blit(footer, (w // 2 - footer.get_width() // 2, h - 40))

        # --- DRAW STATE: REMAP ---
        elif self.state == "REMAP":
            p_num = int(self.remap_mode[1])
            is_gamepad = "gamepad" in self.remap_mode
            
            # Retrieve keys/bings
            if is_gamepad:
                cur_keys = getattr(settings, f"gamepad_p{p_num}", {})
            else:
                cur_keys = getattr(settings, f"keys_p{p_num}", {})
                
            # Table card container dimensions
            card_w = 680
            card_h = 500
            card_x = w // 2 - card_w // 2
            card_y = h // 2 - card_h // 2 - 20
            
            # Card background
            card_bg_col = (20, 15, 30) if self.is_dark_theme(theme) else (235, 235, 240)
            card_border_col = accent_color
            pygame.draw.rect(self.screen, card_bg_col, (card_x, card_y, card_w, card_h), border_radius=12)
            pygame.draw.rect(self.screen, card_border_col, (card_x, card_y, card_w, card_h), width=2, border_radius=12)
            
            # Title & Subtitle
            device_desc = "GAMEPAD" if is_gamepad else "KEYBOARD"
            title_text = f"REMAP INPUTS - PLAYER {p_num}"
            subtitle_text = f"Device Type: {device_desc}"
            
            title_surf = menu_font.render(title_text, True, text_color)
            self.screen.blit(title_surf, (card_x + 30, card_y + 15))
            
            sub_surf = small_font.render(subtitle_text, True, accent_color)
            self.screen.blit(sub_surf, (card_x + 30, card_y + 48))
            
            # Columns
            x_start_col0 = card_x + 30
            x_start_col1 = card_x + 270
            x_start_col2 = card_x + 450
            
            y_header = card_y + 75
            y_data = y_header + 40
            row_h = 38
            
            # Header Row
            hdr_font = pygame.font.SysFont("Trebuchet MS" if theme == "DDR-Retro" else "Segoe UI", 14, bold=True)
            act_hdr = hdr_font.render("ACTION", True, text_color)
            set1_hdr = hdr_font.render("GAMEPAD BIND" if is_gamepad else "SET 1 (PRIMARY)", True, text_color)
            self.screen.blit(act_hdr, (x_start_col0, y_header))
            self.screen.blit(set1_hdr, (x_start_col1, y_header))
            
            if not is_gamepad:
                set2_hdr = hdr_font.render("SET 2 (SECONDARY)", True, text_color)
                self.screen.blit(set2_hdr, (x_start_col2, y_header))
                
            # Divider line under header
            pygame.draw.line(self.screen, (50, 45, 70) if self.is_dark_theme(theme) else (200, 200, 205), (card_x + 20, y_header + 22), (card_x + card_w - 20, y_header + 22), 1)
            
            # Render each direction/action row
            for idx, direction in enumerate(self.remap_directions):
                y_row = y_data + idx * 46
                
                # Column 0: Action Label
                lbl_str = direction.upper()
                lbl_surf = small_font.render(lbl_str, True, text_color)
                self.screen.blit(lbl_surf, (x_start_col0, y_row + 8))
                
                # Retrieve current bindings
                raw_val = cur_keys.get(direction)
                if is_gamepad:
                    val1 = raw_val
                    val2 = None
                else:
                    if isinstance(raw_val, list):
                        val1 = raw_val[0]
                        val2 = raw_val[1] if len(raw_val) > 1 else 0
                    else:
                        val1 = raw_val
                        val2 = 0
                        
                # Draw Column 1 Cell
                cell1_w = 340 if is_gamepad else 160
                cell1_rect = pygame.Rect(x_start_col1, y_row, cell1_w, row_h)
                cell1_hover = cell1_rect.collidepoint(mx, my)
                cell1_active = (getattr(self, "active_remap_cell", None) == (direction, 0))
                
                if cell1_active:
                    bg_col = (255, 128, 0, 100) # orange highlight for active
                    border_col = (255, 215, 0)
                    cell_text = "[ PRESS KEY ]" if not is_gamepad else "[ PRESS BUTTON ]"
                elif cell1_hover:
                    bg_col = (50, 40, 75, 120) if self.is_dark_theme(theme) else (210, 210, 220, 120)
                    border_col = accent_color
                    cell_text = self.get_key_name_str(val1)
                else:
                    bg_col = (25, 20, 40) if self.is_dark_theme(theme) else (220, 220, 225)
                    border_col = (45, 40, 60) if self.is_dark_theme(theme) else (200, 200, 205)
                    cell_text = self.get_key_name_str(val1)
                    
                row_surf = pygame.Surface((cell1_w, row_h), pygame.SRCALPHA)
                pygame.draw.rect(row_surf, bg_col, (0, 0, cell1_w, row_h), border_radius=6)
                pygame.draw.rect(row_surf, border_col, (0, 0, cell1_w, row_h), width=1 if not cell1_active else 2, border_radius=6)
                self.screen.blit(row_surf, (x_start_col1, y_row))
                
                txt_surf = small_font.render(cell_text, True, (255, 255, 255) if cell1_active or self.is_dark_theme(theme) else (50, 50, 60))
                self.screen.blit(txt_surf, (x_start_col1 + cell1_w // 2 - txt_surf.get_width() // 2, y_row + 8))
                
                # Draw Column 2 Cell (if keyboard)
                if not is_gamepad:
                    cell2_rect = pygame.Rect(x_start_col2, y_row, 160, row_h)
                    cell2_hover = cell2_rect.collidepoint(mx, my)
                    cell2_active = (getattr(self, "active_remap_cell", None) == (direction, 1))
                    
                    if cell2_active:
                        bg_col2 = (255, 128, 0, 100)
                        border_col2 = (255, 215, 0)
                        cell_text2 = "[ PRESS KEY ]"
                    elif cell2_hover:
                        bg_col2 = (50, 40, 75, 120) if self.is_dark_theme(theme) else (210, 210, 220, 120)
                        border_col2 = accent_color
                        cell_text2 = self.get_key_name_str(val2)
                    else:
                        bg_col2 = (25, 20, 40) if self.is_dark_theme(theme) else (220, 220, 225)
                        border_col2 = (45, 40, 60) if self.is_dark_theme(theme) else (200, 200, 205)
                        cell_text2 = self.get_key_name_str(val2)
                        
                    row_surf2 = pygame.Surface((160, row_h), pygame.SRCALPHA)
                    pygame.draw.rect(row_surf2, bg_col2, (0, 0, 160, row_h), border_radius=6)
                    pygame.draw.rect(row_surf2, border_col2, (0, 0, 160, row_h), width=1 if not cell2_active else 2, border_radius=6)
                    self.screen.blit(row_surf2, (x_start_col2, y_row))
                    
                    txt_surf2 = small_font.render(cell_text2, True, (255, 255, 255) if cell2_active or self.is_dark_theme(theme) else (50, 50, 60))
                    self.screen.blit(txt_surf2, (x_start_col2 + 80 - txt_surf2.get_width() // 2, y_row + 8))
                    
            # Draw Reset Defaults & Back/Save Buttons
            reset_rect = pygame.Rect(card_x + 60, card_y + card_h - 70, 220, 40)
            back_rect = pygame.Rect(card_x + card_w - 280, card_y + card_h - 70, 220, 40)
            
            res_hover = reset_rect.collidepoint(mx, my) and getattr(self, "active_remap_cell", None) is None
            bak_hover = back_rect.collidepoint(mx, my) and getattr(self, "active_remap_cell", None) is None
            
            res_bg = (140, 30, 90) if res_hover else (100, 20, 60)
            bak_bg = (0, 220, 170) if bak_hover else (0, 180, 140)
            
            pygame.draw.rect(self.screen, res_bg, reset_rect, border_radius=8)
            pygame.draw.rect(self.screen, bak_bg, back_rect, border_radius=8)
            
            res_surf = small_font.render("RESET DEFAULTS", True, (255, 255, 255))
            self.screen.blit(res_surf, (reset_rect.centerx - res_surf.get_width() // 2, reset_rect.centery - res_surf.get_height() // 2))
            
            bak_surf = small_font.render("BACK / SAVE", True, (255, 255, 255) if self.is_dark_theme(theme) else (45, 45, 55))
            self.screen.blit(bak_surf, (back_rect.centerx - bak_surf.get_width() // 2, back_rect.centery - bak_surf.get_height() // 2))
            
            # Guide text at bottom
            if getattr(self, "active_remap_cell", None) is not None:
                guide_str = "Press any key to bind. ESC to cancel, DELETE/BACKSPACE to clear."
            else:
                guide_str = "Click any slot to bind new inputs. ESC to save & exit."
            guide_surf = small_font.render(guide_str, True, text_color)
            self.screen.blit(guide_surf, (card_x + card_w // 2 - guide_surf.get_width() // 2, card_y + card_h - 22))

        # --- DRAW STATE: RESULTS ---
        elif self.state == "RESULTS" and self.results_data:
            # Title
            title_surf = title_font.render("SONG COMPLETE", True, accent_color)
            self.screen.blit(title_surf, (w // 2 - title_surf.get_width() // 2, 60))
            
            # Draw metadata at top
            first_res = self.results_data[0]
            song_title_end_y = draw_wrapped_text_centered(self.screen, menu_font, first_res["title"], text_color, w // 2, 130, 600)
            
            diff_y = song_title_end_y + 10
            diff_lbl = desc_font.render(f"{first_res['difficulty'].upper()} | BPM: {first_res['bpm']}", True, accent_color)
            self.screen.blit(diff_lbl, (w // 2 - diff_lbl.get_width() // 2, diff_y))
            
            # Draw player stats cards
            num_results = len(self.results_data)
            
            if num_results >= 3:
                card_w = 210
                card_h = 320
                spacing = 15
                total_w = card_w * num_results + spacing * (num_results - 1)
                start_x = (w - total_w) // 2
            elif num_results == 2:
                card_w = 400
                card_h = 320
                spacing = 40
                total_w = card_w * 2 + spacing
                start_x = (w - total_w) // 2
            else:
                card_w = 420
                card_h = 320
                start_x = (w - card_w) // 2
                
            for p_idx, res in enumerate(self.results_data):
                if num_results >= 2:
                    card_x = start_x + p_idx * (card_w + spacing)
                else:
                    card_x = start_x
                    
                card_y = diff_y + 35
                
                # Draw card backdrop
                pygame.draw.rect(self.screen, (20, 15, 35) if self.is_dark_theme(theme) else (235, 235, 240), (card_x, card_y, card_w, card_h), border_radius=12)
                p_accent = (0, 255, 204) if p_idx == 0 else (255, 64, 128) if p_idx == 1 else (180, 0, 255) if p_idx == 2 else (255, 215, 0)
                pygame.draw.rect(self.screen, p_accent, (card_x, card_y, card_w, card_h), width=2, border_radius=12)
                
                # Player header
                p_header = f"PLAYER {p_idx+1}"
                header_surf = desc_font.render(p_header, True, p_accent)
                self.screen.blit(header_surf, (card_x + 15, card_y + 15))
                
                # Grade
                grade = res.get("grade", "D")
                grade_color = (255, 215, 0) if grade in ["SSS", "AAA"] else (255, 128, 0) if grade == "S" else (0, 255, 128) if grade in ["AA", "A"] else accent_color
                grade_font = desc_font if num_results >= 3 else title_font
                grade_surf = grade_font.render(grade, True, grade_color)
                self.screen.blit(grade_surf, (card_x + card_w - 15 - grade_surf.get_width(), card_y + 10))
                
                # Draw stats rows
                rows = [
                    ("PERFECT", res["perfects"], (255, 215, 0)),
                    ("GREAT", res["greats"], (0, 255, 128)),
                    ("GOOD", res["goods"], (0, 191, 255)),
                    ("MISS", res["misses"], (255, 64, 64)),
                    ("MAX COMBO", res["max_combo"], text_color),
                    ("SCORE", res["score"], p_accent),
                ]
                
                card_font = small_font if num_results >= 3 else desc_font
                for idx, (label, val, col) in enumerate(rows):
                    lbl_s = card_font.render(label, True, col)
                    val_str = f"{val:07d}" if label == "SCORE" else str(val)
                    val_s = card_font.render(val_str, True, col)
                    
                    row_y = card_y + (55 if num_results >= 3 else 70) + idx * (32 if num_results >= 3 else 36)
                    self.screen.blit(lbl_s, (card_x + 15, row_y))
                    self.screen.blit(val_s, (card_x + card_w - 15 - val_s.get_width(), row_y))
                    
                # Draw badges (e.g. ALL PERFECT, FULL COMBO, NO MISSES)
                p_badges = res.get("badges", [])
                badge_font = pygame.font.SysFont("Trebuchet MS" if theme == "DDR-Retro" else "Segoe UI", 12, bold=True)
                for b_idx, b_text in enumerate(p_badges):
                    badge_surf = badge_font.render(b_text, True, (255, 215, 0))
                    self.screen.blit(badge_surf, (card_x + card_w // 2 - badge_surf.get_width() // 2, card_y + 252 + b_idx * 16))
                    
                # Draw newly unlocked achievements
                unlocked = res.get("unlocked_achievements", [])
                if unlocked:
                    ach_font = pygame.font.SysFont("Trebuchet MS" if theme == "DDR-Retro" else "Segoe UI", 11, bold=True)
                    ach_y = card_y + 275
                    for ach_name in unlocked:
                        ach_surf = ach_font.render(f"🏆 UNLOCKED: {ach_name}!", True, (255, 165, 0))
                        self.screen.blit(ach_surf, (card_x + card_w // 2 - ach_surf.get_width() // 2, ach_y))
                        ach_y += 14
                    
            # --- TIMING OFFSET HEATMAP SCATTER PLOT ---
            map_w = 720
            map_h = 160
            map_x = w // 2 - map_w // 2
            map_y = h - 250
            
            # Backing box
            pygame.draw.rect(self.screen, (15, 12, 22), (map_x, map_y, map_w, map_h), border_radius=8)
            pygame.draw.rect(self.screen, (60, 55, 75), (map_x, map_y, map_w, map_h), width=1, border_radius=8)
            
            # Center guideline (Perfect 0ms)
            pygame.draw.line(self.screen, (0, 255, 204, 100), (map_x + 40, map_y + map_h // 2), (map_x + map_w - 40, map_y + map_h // 2), 2)
            
            # Draw threshold lines (Perfect, Great)
            py_perfect_top = map_y + map_h // 2 - int((TIMING_PERFECT / TIMING_GOOD) * (map_h // 2 - 20))
            py_perfect_bottom = map_y + map_h // 2 + int((TIMING_PERFECT / TIMING_GOOD) * (map_h // 2 - 20))
            py_great_top = map_y + map_h // 2 - int((TIMING_GREAT / TIMING_GOOD) * (map_h // 2 - 20))
            py_great_bottom = map_y + map_h // 2 + int((TIMING_GREAT / TIMING_GOOD) * (map_h // 2 - 20))
            
            pygame.draw.line(self.screen, (0, 180, 150, 60), (map_x + 40, py_perfect_top), (map_x + map_w - 40, py_perfect_top), 1)
            pygame.draw.line(self.screen, (0, 180, 150, 60), (map_x + 40, py_perfect_bottom), (map_x + map_w - 40, py_perfect_bottom), 1)
            pygame.draw.line(self.screen, (180, 150, 0, 50), (map_x + 40, py_great_top), (map_x + map_w - 40, py_great_top), 1)
            pygame.draw.line(self.screen, (180, 150, 0, 50), (map_x + 40, py_great_bottom), (map_x + map_w - 40, py_great_bottom), 1)
            
            # Vertical structural divisions of the song (every 25%)
            for i in [0.25, 0.50, 0.75]:
                vx = map_x + 40 + int(i * (map_w - 80))
                pygame.draw.line(self.screen, (45, 42, 58), (vx, map_y + 15), (vx, map_y + map_h - 15), 1)
            
            # Text labels
            map_font = pygame.font.SysFont("Segoe UI", 11, bold=True)
            lbl_title = map_font.render("SONG PERFORMANCE TIMING TIMELINE", True, (200, 200, 210))
            lbl_early = map_font.render("-180ms (EARLY)", True, (220, 100, 100))
            lbl_late = map_font.render("+180ms (LATE)", True, (100, 160, 220))
            lbl_perf = map_font.render("0ms (PERFECT)", True, (0, 255, 204))
            
            self.screen.blit(lbl_title, (map_x + 12, map_y + 6))
            self.screen.blit(lbl_early, (map_x + 12, map_y + map_h - 22))
            self.screen.blit(lbl_late, (map_x + 12, map_y + 22))
            self.screen.blit(lbl_perf, (map_x + map_w - lbl_perf.get_width() - 12, map_y + map_h // 2 - 7))
            
            # Plot hit offset points
            for p_idx, res in enumerate(self.results_data):
                p_accent = (0, 255, 204) if p_idx == 0 else (255, 64, 128) if p_idx == 1 else (180, 0, 255) if p_idx == 2 else (255, 215, 0)
                offsets_list = res.get("timing_offsets", [])
                song_dur = res.get("duration", 60.0)
                
                for idx, offset_item in enumerate(offsets_list):
                    offset_val = offset_item["offset"]
                    rating = offset_item["rating"]
                    note_time = offset_item.get("time", 0.0)
                    
                    x_pct = note_time / song_dur if song_dur > 0 else 0.0
                    x_pos = map_x + 40 + int(x_pct * (map_w - 80))
                    x_pos = max(map_x + 40, min(map_x + map_w - 40, x_pos))
                    
                    y_pct = (offset_val - (-TIMING_GOOD)) / (2 * TIMING_GOOD)
                    y_pos = map_y + map_h - 20 - int(y_pct * (map_h - 40))
                    y_pos = max(map_y + 15, min(map_y + map_h - 15, y_pos))
                    
                    if rating == "PERFECT":
                        dot_col = (0, 255, 204)
                    elif rating == "GREAT":
                        dot_col = (255, 215, 0)
                    elif rating == "GOOD":
                        dot_col = (200, 200, 50)
                    else:
                        dot_col = (255, 64, 64)
                        
                    rad = 4 if rating == "MISS" else 3
                    pygame.draw.circle(self.screen, dot_col, (x_pos, y_pos), rad)
                    if len(self.results_data) > 1:
                        pygame.draw.circle(self.screen, p_accent, (x_pos, y_pos), rad, width=1)
                    
            # --- AI COACH PERFORMANCE ANALYSIS ---
            coach_x = w // 2 - 360
            coach_y = h - 110
            coach_w = 720
            coach_h = 35
            
            # Glassmorphic speech bubble
            pygame.draw.rect(self.screen, (20, 18, 30) if self.is_dark_theme(theme) else (245, 245, 250), (coach_x, coach_y, coach_w, coach_h), border_radius=8)
            pygame.draw.rect(self.screen, (244, 143, 177) if self.is_dark_theme(theme) else (180, 50, 90), (coach_x, coach_y, coach_w, coach_h), width=1, border_radius=8)
            
            # AI Coach text generation
            # Let's read stats from Player 1 (first result)
            perf1 = first_res["perfects"]
            great1 = first_res["greats"]
            miss1 = first_res["misses"]
            total1 = perf1 + great1 + first_res.get("goods", 0) + miss1
            acc1 = (perf1 * 100.0 + great1 * 75.0 + first_res.get("goods", 0) * 40.0) / max(1, total1)
            
            offsets1 = first_res.get("timing_offsets", [])
            early_count = sum(1 for o in offsets1 if o["offset"] < -0.010)
            late_count = sum(1 for o in offsets1 if o["offset"] > 0.010)
            
            if acc1 >= 98.0:
                coach_msg = "Coach Mia: Purr-fect stepping! You have cat-like reflexes! Are you sure you're not an esports champion?"
            elif acc1 >= 90.0:
                coach_msg = "Coach Mia: Great job! Your timing is super clean. Keep up the rhythm and you'll get that All Perfect next time!"
            elif miss1 == 0:
                coach_msg = "Coach Mia: A clean sheet! No misses at all! That was incredibly steady, I'm proud of you!"
            elif miss1 > 0 and miss1 <= 5:
                coach_msg = "Coach Mia: So close! Just a couple of misses. Watch out for those fast streams near the end!"
            elif early_count > late_count * 1.5:
                coach_msg = "Coach Mia: You are stepping a bit early! Try listening closer to the beat, or adjust your audio latency offset in settings."
            elif late_count > early_count * 1.5:
                coach_msg = "Coach Mia: You are stepping slightly late! Try reading ahead on the highway to anticipate the notes."
            else:
                coach_msg = "Coach Mia: Don't give up! Try lowering the playback speed in practice mode to learn the tricky sections first!"
                
            coach_font = pygame.font.SysFont("Trebuchet MS" if theme == "DDR-Retro" else "Segoe UI", 11, italic=True)
            coach_surf = coach_font.render(coach_msg, True, (244, 143, 177) if self.is_dark_theme(theme) else (180, 50, 90))
            self.screen.blit(coach_surf, (coach_x + coach_w // 2 - coach_surf.get_width() // 2, coach_y + coach_h // 2 - coach_surf.get_height() // 2))
            
            play_hint = desc_font.render("Press ENTER to Continue", True, accent_color)
            self.screen.blit(play_hint, (w // 2 - play_hint.get_width() // 2, h - 55))

        # --- DRAW STATE: PROFILE_CREATION ---
        elif self.state == "PROFILE_CREATION":
            theme_manager.draw_background_grid(self.screen, theme, time.time() * 0.5)
            panel_w = 640
            panel_h = 420
            panel_x = w // 2 - panel_w // 2
            panel_y = h // 2 - panel_h // 2 - 20
            
            bg_col = (15, 10, 25, 220) if self.is_dark_theme(theme) else (240, 240, 245, 220)
            pygame.draw.rect(self.screen, bg_col, (panel_x, panel_y, panel_w, panel_h), border_radius=12)
            pygame.draw.rect(self.screen, accent_color, (panel_x, panel_y, panel_w, panel_h), width=2, border_radius=12)
            
            title_surf = menu_font.render("DANCER PROFILE CREATION", True, text_color)
            self.screen.blit(title_surf, (w // 2 - title_surf.get_width() // 2, panel_y + 30))
            
            desc_str = "Welcome! Create your local profile to track your scores, unlocks, and achievements."
            desc_surf = small_font.render(desc_str, True, (160, 150, 175) if self.is_dark_theme(theme) else (90, 80, 100))
            self.screen.blit(desc_surf, (w // 2 - desc_surf.get_width() // 2, panel_y + 80))
            
            lbl_name = desc_font.render("DISPLAY NAME:", True, accent_color)
            self.screen.blit(lbl_name, (panel_x + 50, panel_y + 140))
            
            input_rect = pygame.Rect(panel_x + 50, panel_y + 175, panel_w - 100, 44)
            box_col = (25, 18, 42) if self.is_dark_theme(theme) else (220, 220, 230)
            pygame.draw.rect(self.screen, box_col, input_rect, border_radius=6)
            pygame.draw.rect(self.screen, (0, 255, 204) if self.profile_creation_name else (80, 75, 95), input_rect, width=1, border_radius=6)
            
            cursor = "_" if (int(time.time() * 2) % 2 == 0) else ""
            display_text = self.profile_creation_name + cursor
            typed_surf = desc_font.render(display_text, True, text_color)
            self.screen.blit(typed_surf, (input_rect.x + 15, input_rect.centery - typed_surf.get_height() // 2))
            
            lbl_av = desc_font.render("CHOOSE AVATAR (Press Tab / Click):", True, accent_color)
            self.screen.blit(lbl_av, (panel_x + 50, panel_y + 245))
            
            av_start_x = w // 2 - 180
            av_y = panel_y + 305
            
            for idx, av in enumerate(AVATARS):
                ax = av_start_x + idx * 60
                is_selected = (idx == self.profile_creation_avatar_idx)
                
                btn_color = (45, 35, 70) if is_selected else (25, 20, 40)
                if not self.is_dark_theme(theme):
                    btn_color = (195, 195, 215) if is_selected else (230, 230, 235)
                
                border_color = (0, 255, 204) if is_selected else ((60, 55, 75) if self.is_dark_theme(theme) else (200, 200, 205))
                scale_av = 1.15 if is_selected else 1.0
                
                r_circ = int(22 * scale_av)
                pygame.draw.circle(self.screen, btn_color, (ax, av_y), r_circ)
                pygame.draw.circle(self.screen, border_color, (ax, av_y), r_circ, width=2 if is_selected else 1)
                
                av_font = pygame.font.SysFont("Segoe UI", int(20 * scale_av))
                av_surf = av_font.render(av["char"], True, (255, 255, 255))
                self.screen.blit(av_surf, (ax - av_surf.get_width() // 2, av_y - av_surf.get_height() // 2 - 1))
            
            confirm_rect = pygame.Rect(w // 2 - 100, panel_y + 350, 200, 42)
            has_name = bool(self.profile_creation_name.strip())
            
            btn_col = (0, 200, 100) if has_name else (50, 50, 60)
            text_col_btn = (255, 255, 255) if has_name else (120, 120, 130)
            
            pygame.draw.rect(self.screen, btn_col, confirm_rect, border_radius=6)
            
            btn_text = desc_font.render("CREATE PROFILE", True, text_col_btn)
            self.screen.blit(btn_text, (confirm_rect.centerx - btn_text.get_width() // 2, confirm_rect.centery - btn_text.get_height() // 2))

        # --- DRAW STATE: PROFILE_STATS ---
        elif self.state == "PROFILE_STATS":
            theme_manager.draw_background_grid(self.screen, theme, time.time() * 0.3)
            
            header_surf = menu_font.render("PLAYER DANCER PROFILE", True, text_color)
            self.screen.blit(header_surf, (w // 2 - header_surf.get_width() // 2, 50))
            
            tab_names = ["stats", "scores", "achievements"]
            tab_labels = ["STATS CARD", "TOP 10 SONGS", "ACHIEVEMENTS"]
            tab_widths = [130, 150, 150]
            tab_starts = [w // 2 - 210, w // 2 - 60, w // 2 + 110]
            
            for t_idx, (t_name, label, start_x, tw) in enumerate(zip(tab_names, tab_labels, tab_starts, tab_widths)):
                is_active = (self.profile_tab == t_name)
                t_rect = pygame.Rect(start_x, 110, tw, 36)
                
                t_color = accent_color if is_active else ((100, 90, 110) if self.is_dark_theme(theme) else (140, 140, 150))
                lbl_s = small_font.render(label, True, t_color)
                
                self.screen.blit(lbl_s, (t_rect.centerx - lbl_s.get_width() // 2, t_rect.centery - lbl_s.get_height() // 2))
                if is_active:
                    pygame.draw.line(self.screen, accent_color, (start_x + 10, 145), (start_x + tw - 10, 145), 3)

            card_w = 780
            card_h = 440
            card_x = w // 2 - card_w // 2
            card_y = 160
            
            bg_panel_col = (20, 15, 30, 200) if self.is_dark_theme(theme) else (235, 235, 240, 200)
            pygame.draw.rect(self.screen, bg_panel_col, (card_x, card_y, card_w, card_h), border_radius=12)
            pygame.draw.rect(self.screen, (50, 45, 70) if self.is_dark_theme(theme) else (200, 200, 205), (card_x, card_y, card_w, card_h), width=1, border_radius=12)

            if self.profile_tab == "stats":
                avatar_char = profile_manager.get_avatar_char()
                pygame.draw.circle(self.screen, (40, 30, 60) if self.is_dark_theme(theme) else (210, 210, 225), (card_x + 120, card_y + 110), 64)
                pygame.draw.circle(self.screen, accent_color, (card_x + 120, card_y + 110), 64, width=3)
                
                av_draw_font = pygame.font.SysFont("Segoe UI", 60)
                av_surf = av_draw_font.render(avatar_char, True, (255, 255, 255))
                self.screen.blit(av_surf, (card_x + 120 - av_surf.get_width() // 2, card_y + 110 - av_surf.get_height() // 2 - 3))
                
                p_name = profile_manager.profile.get("player_name", "Janet")
                p_tag = profile_manager.profile.get("tagline", "Beginner")
                
                name_surf = menu_font.render(p_name.upper(), True, text_color)
                self.screen.blit(name_surf, (card_x + 220, card_y + 60))
                
                tag_font = pygame.font.SysFont("Trebuchet MS" if theme == "DDR-Retro" else "Segoe UI", 16, bold=True, italic=True)
                tag_surf = tag_font.render(f"Tagline: {p_tag}", True, (255, 215, 0))
                self.screen.blit(tag_surf, (card_x + 220, card_y + 105))
                
                stats_data = profile_manager.profile.get("stats", {})
                sec = stats_data.get("total_play_time_seconds", 0)
                dur_str = f"{sec // 60}m {sec % 60}s"
                
                stat_items = [
                    ("Songs Played:", str(stats_data.get("songs_played", 0))),
                    ("Total Playtime:", dur_str),
                    ("Highest Combo:", str(stats_data.get("highest_combo_ever", 0))),
                    ("Avg Accuracy:", f"{stats_data.get('average_accuracy', 0.0):.2f}%"),
                    ("Total Perfects:", str(stats_data.get("total_perfects", 0))),
                    ("Total Misses:", str(stats_data.get("total_misses", 0)))
                ]
                
                for idx, (lbl, val) in enumerate(stat_items):
                    col_offset = card_x + 220 + (idx % 2) * 260
                    row_offset = card_y + 145 + (idx // 2) * 32
                    
                    lbl_s = desc_font.render(lbl, True, (170, 160, 185) if self.is_dark_theme(theme) else (90, 80, 100))
                    val_s = desc_font.render(val, True, text_color)
                    self.screen.blit(lbl_s, (col_offset, row_offset))
                    self.screen.blit(val_s, (col_offset + 140, row_offset))
                
                pygame.draw.line(self.screen, (60, 55, 75), (card_x + 30, card_y + 265), (card_x + card_w - 30, card_y + 265), 1)
                
                unlocked_tags_lbl = desc_font.render("SELECT ACTIVE TAGLINE (Click Tagline):", True, accent_color)
                self.screen.blit(unlocked_tags_lbl, (card_x + 40, card_y + 280))
                
                unlocked_tags = profile_manager.profile.get("unlocked_taglines", ["Beginner"])
                for idx, tag in enumerate(unlocked_tags):
                    row_y = card_y + 315 + idx * 30
                    is_active_tag = (p_tag == tag)
                    
                    bg_tag = (40, 30, 60) if is_active_tag else (25, 20, 40)
                    if not self.is_dark_theme(theme):
                        bg_tag = (210, 210, 225) if is_active_tag else (235, 235, 240)
                        
                    bd_tag = (255, 215, 0) if is_active_tag else ((60, 55, 75) if self.is_dark_theme(theme) else (200, 200, 205))
                    tag_rect = pygame.Rect(card_x + 40, row_y, card_w - 80, 26)
                    
                    pygame.draw.rect(self.screen, bg_tag, tag_rect, border_radius=4)
                    pygame.draw.rect(self.screen, bd_tag, tag_rect, width=1, border_radius=4)
                    
                    tag_color = (255, 215, 0) if is_active_tag else text_color
                    tag_s = small_font.render(f"★  {tag}  ★" if is_active_tag else tag, True, tag_color)
                    self.screen.blit(tag_s, (tag_rect.centerx - tag_s.get_width() // 2, tag_rect.centery - tag_s.get_height() // 2))

            elif self.profile_tab == "scores":
                top_scores = profile_manager.get_top_10_scores()
                if not top_scores:
                    no_scores_surf = desc_font.render("NO RECORDS FOUND YET. GO PLAY SOME SONGS!", True, (130, 120, 140))
                    self.screen.blit(no_scores_surf, (w // 2 - no_scores_surf.get_width() // 2, card_y + card_h // 2 - 10))
                else:
                    hdr_y = card_y + 15
                    pygame.draw.line(self.screen, (60, 55, 75), (card_x + 20, hdr_y + 22), (card_x + card_w - 20, hdr_y + 22), 1)
                    
                    self.screen.blit(small_font.render("SONG TITLE", True, accent_color), (card_x + 30, hdr_y))
                    self.screen.blit(small_font.render("DIFF", True, accent_color), (card_x + 270, hdr_y))
                    self.screen.blit(small_font.render("GRADE", True, accent_color), (card_x + 370, hdr_y))
                    self.screen.blit(small_font.render("BEST SCORE", True, accent_color), (card_x + 470, hdr_y))
                    self.screen.blit(small_font.render("ACC", True, accent_color), (card_x + 600, hdr_y))
                    self.screen.blit(small_font.render("FC?", True, accent_color), (card_x + 690, hdr_y))
                    
                    for idx, record in enumerate(top_scores):
                        row_y = card_y + 48 + idx * 36
                        bg_r = (25, 20, 42) if (idx % 2 == 0) else (18, 14, 30)
                        if not self.is_dark_theme(theme):
                            bg_r = (240, 240, 245) if (idx % 2 == 0) else (230, 230, 235)
                        pygame.draw.rect(self.screen, bg_r, (card_x + 20, row_y - 4, card_w - 40, 32), border_radius=4)
                        
                        title_lbl = render_truncated_text(small_font, record.get("title", ""), 220, text_color)
                        self.screen.blit(title_lbl, (card_x + 30, row_y))
                        
                        diff_lbl = small_font.render(record.get("difficulty", "Medium"), True, (255, 128, 0))
                        self.screen.blit(diff_lbl, (card_x + 270, row_y))
                        
                        grade_lbl = small_font.render(record.get("grade", "F"), True, (0, 255, 100) if "S" in record.get("grade", "") else text_color)
                        self.screen.blit(grade_lbl, (card_x + 370, row_y))
                        
                        score_lbl = small_font.render(f"{record.get('best_score', 0):,}", True, text_color)
                        self.screen.blit(score_lbl, (card_x + 470, row_y))
                        
                        acc_lbl = small_font.render(f"{record.get('best_accuracy', 0.0):.2f}%", True, text_color)
                        self.screen.blit(acc_lbl, (card_x + 600, row_y))
                        
                        fc_lbl = small_font.render("🐾 FC" if record.get("full_combo", False) else "No", True, (255, 215, 0) if record.get("full_combo", False) else (140, 130, 150))
                        self.screen.blit(fc_lbl, (card_x + 690, row_y))

            elif self.profile_tab == "achievements":
                unlocked_set = set(profile_manager.profile.get("achievements", []))
                ach_list = list(ACHIEVEMENTS.keys())
                visible_count = 4
                scroll_offset = min(self.profile_scroll_idx, max(0, len(ach_list) - visible_count))
                self.profile_scroll_idx = scroll_offset
                
                for idx in range(visible_count):
                    ach_idx = scroll_offset + idx
                    if ach_idx >= len(ach_list):
                        break
                    ach_id = ach_list[ach_idx]
                    info = ACHIEVEMENTS[ach_id]
                    is_unlocked = (ach_id in unlocked_set)
                    
                    row_y = card_y + 20 + idx * 95
                    row_bg = (30, 22, 50) if is_unlocked else (18, 14, 25)
                    if not self.is_dark_theme(theme):
                        row_bg = (220, 240, 230) if is_unlocked else (240, 240, 245)
                        
                    row_bd = (255, 215, 0) if is_unlocked else ((60, 55, 75) if self.is_dark_theme(theme) else (200, 200, 205))
                    pygame.draw.rect(self.screen, row_bg, (card_x + 30, row_y, card_w - 60, 85), border_radius=8)
                    pygame.draw.rect(self.screen, row_bd, (card_x + 30, row_y, card_w - 60, 85), width=2 if is_unlocked else 1, border_radius=8)
                    
                    trophy_font = pygame.font.SysFont("Segoe UI", 36)
                    trophy_color = (255, 215, 0) if is_unlocked else (100, 100, 110)
                    trophy_surf = trophy_font.render("🏆" if is_unlocked else "🔒", True, trophy_color)
                    self.screen.blit(trophy_surf, (card_x + 50, row_y + 15))
                    
                    title_surf = desc_font.render(info["name"].upper(), True, (255, 215, 0) if is_unlocked else (130, 120, 140))
                    desc_surf = small_font.render(info["description"], True, (220, 220, 230) if is_unlocked else (130, 120, 140))
                    
                    self.screen.blit(title_surf, (card_x + 120, row_y + 12))
                    self.screen.blit(desc_surf, (card_x + 120, row_y + 40))
                    
                    rewards = []
                    if info["unlock_tagline"]:
                        rewards.append(f"Tagline: {info['unlock_tagline']}")
                    if info["unlock_theme"]:
                        rewards.append(f"Theme: {info['unlock_theme']}")
                    if rewards:
                        rew_font = pygame.font.SysFont("Segoe UI", 11, bold=True)
                        rew_surf = rew_font.render("REWARD: " + " & ".join(rewards), True, (0, 255, 204) if is_unlocked else (130, 120, 140))
                        self.screen.blit(rew_surf, (card_x + 120, row_y + 60))

                if len(ach_list) > visible_count:
                    ind_s = small_font.render("▲ UP/DOWN ARROWS OR MOUSE WHEEL TO SCROLL LIST ▲", True, accent_color)
                    self.screen.blit(ind_s, (w // 2 - ind_s.get_width() // 2, card_y + card_h - 25))

            back_font = pygame.font.SysFont("Trebuchet MS" if theme == "DDR-Retro" else "Segoe UI", 16, bold=True)
            back_surf = back_font.render("◄  BACK  ►", True, accent_color)
            pygame.draw.rect(self.screen, (25, 20, 40) if self.is_dark_theme(theme) else (225, 225, 230), (50, h - 60, 100, 36), border_radius=6)
            pygame.draw.rect(self.screen, accent_color, (50, h - 60, 100, 36), width=1, border_radius=6)
            self.screen.blit(back_surf, (50 + 50 - back_surf.get_width() // 2, h - 60 + 18 - back_surf.get_height() // 2))

        # --- DRAW STATE: ERROR_SCREEN ---
        elif self.state == "ERROR_SCREEN" and hasattr(self, "error_traceback"):
            self.screen.fill((15, 8, 22))
            err_title_font = pygame.font.SysFont("Impact" if theme in ["DDR-Retro", "Retro-Pixel"] else "Segoe UI", 36, bold=True)
            title_surf = err_title_font.render("AN ERROR OCCURRED", True, (255, 64, 64))
            self.screen.blit(title_surf, (w // 2 - title_surf.get_width() // 2, 40))
            
            box_x = 40
            box_y = 100
            box_w = w - 80
            box_h = h - 220
            pygame.draw.rect(self.screen, (25, 12, 35), (box_x, box_y, box_w, box_h), border_radius=8)
            pygame.draw.rect(self.screen, (255, 64, 64), (box_x, box_y, box_w, box_h), width=2, border_radius=8)
            
            mono_font = pygame.font.SysFont("Courier New", 12)
            lines = self.error_traceback.split("\n")
            line_y = box_y + 15
            for line in lines:
                if not line.strip():
                    continue
                max_w = box_w - 30
                if mono_font.size(line)[0] > max_w:
                    chunk = ""
                    for char in line:
                        if mono_font.size(chunk + char)[0] > max_w:
                            line_surf = mono_font.render(chunk, True, (240, 240, 245))
                            self.screen.blit(line_surf, (box_x + 15, line_y))
                            line_y += 18
                            chunk = char
                        else:
                            chunk += char
                    if chunk:
                        line_surf = mono_font.render(chunk, True, (240, 240, 245))
                        self.screen.blit(line_surf, (box_x + 15, line_y))
                        line_y += 18
                else:
                    line_surf = mono_font.render(line, True, (240, 240, 245))
                    self.screen.blit(line_surf, (box_x + 15, line_y))
                    line_y += 18
                
                if line_y > box_y + box_h - 25:
                    break
            
            hint_surf = desc_font.render("Press ESC to return to Title Menu", True, (0, 255, 204))
            self.screen.blit(hint_surf, (w // 2 - hint_surf.get_width() // 2, h - 80))

        # --- DRAW CELEBRATION EFFECTS OVERLAY ---
        if self.celebration.active:
            self.celebration.draw(self.screen)

        # Draw Achievement Unlock Banner Notification
        if getattr(self, "achievement_banner_timer", 0) > 0 and getattr(self, "newly_unlocked_achievements", None):
            banner_w = 480
            banner_h = 80
            banner_x = w // 2 - banner_w // 2
            # Slide in from the top
            banner_y = max(20, int(20 - (6.0 - self.achievement_banner_timer) * 100))
            if self.achievement_banner_timer < 1.0:
                banner_y = int(20 - (1.0 - self.achievement_banner_timer) * 120)

            # Draw glossy glass banner card
            pygame.draw.rect(self.screen, (30, 20, 50, 230), (banner_x, banner_y, banner_w, banner_h), border_radius=12)
            pygame.draw.rect(self.screen, (255, 215, 0), (banner_x, banner_y, banner_w, banner_h), width=2, border_radius=12)
            
            # Icon
            trophy_font = pygame.font.SysFont("Segoe UI", 36)
            trophy_surf = trophy_font.render("🏆", True, (255, 255, 255))
            self.screen.blit(trophy_surf, (banner_x + 20, banner_y + banner_h // 2 - trophy_surf.get_height() // 2))

            # Text
            ach_id = self.newly_unlocked_achievements[0]
            ach_info = ACHIEVEMENTS.get(ach_id, {"name": "Achievement Unlocked!", "description": ""})
            
            hdr_font = pygame.font.SysFont("Trebuchet MS" if theme == "DDR-Retro" else "Segoe UI", 18, bold=True)
            desc_font_banner = pygame.font.SysFont("Trebuchet MS" if theme == "DDR-Retro" else "Segoe UI", 14)
            
            title_s = hdr_font.render(f"ACHIEVEMENT UNLOCKED: {ach_info['name'].upper()}!", True, (255, 215, 0))
            desc_s = desc_font_banner.render(ach_info["description"], True, (220, 220, 230))
            
            self.screen.blit(title_s, (banner_x + 80, banner_y + 16))
            self.screen.blit(desc_s, (banner_x + 80, banner_y + 44))

        pygame.display.flip()

if __name__ == "__main__":
    app = App()
    app.run()
