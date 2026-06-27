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
import tkinter as tk
from tkinter import filedialog

# Import game modules
import zipfile
from sm_parser import SMParser
from config import settings, SCREEN_WIDTH, SCREEN_HEIGHT, FPS
from input_manager import input_manager
from theme_manager import theme_manager
from sound_helper import sound_helper
from song_analyzer import SongAnalyzer
from gameplay import Gameplay
from editor import ChartEditor

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
        
        self.clock = pygame.Clock()
        input_manager.refresh_joysticks()
        self.apply_console_visibility()
        self.running = True
        
        # State Management
        # "TITLE", "SONG_SELECT", "ANALYZING", "GAMEPLAY", "RESULTS", "SETTINGS", "REMAP", "EDITOR"
        self.state = "TITLE"
        
        # Menu Indices
        self.title_index = 0
        self.title_options = ["PLAY", "SETTINGS", "EXIT"]
        
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
            "REMAP P1 GUITAR (KEYBOARD)",
            "REMAP P2 GUITAR (KEYBOARD)",
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

    def scan_songs(self):
        """Scans the songs directory for JSON beatmaps and populates the list."""
        self.songs_list = []
        if not os.path.exists(settings.SONGS_DIR):
            os.makedirs(settings.SONGS_DIR)
            
        for f in os.listdir(settings.SONGS_DIR):
            if f.endswith(".json"):
                json_path = os.path.join(settings.SONGS_DIR, f)
                try:
                    with open(json_path, "r") as file:
                        data = json.load(file)
                        # Verify it has charts
                        if "charts" in data and "title" in data:
                            self.songs_list.append(data)
                except Exception as e:
                    print(f"Error reading song map {f}: {e}")
                    
        # Sort alphabetically by title
        self.songs_list = sorted(self.songs_list, key=lambda x: x["title"])

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
                        self.song_index = (self.song_index + dir_scroll) % (len(self.songs_list) + 1)
                        self.update_difficulties_list()
                        sound_helper.play_select()
                    continue
                elif self.state == "EDITOR" and event.button in [4, 5]:
                    self.editor.handle_scroll(event.button)
                    continue

            # --- GAMEPLAY KEYS & GAMEPADS ROUTING ---
            if self.state == "GAMEPLAY" and self.gameplay:
                if event.type in [pygame.KEYDOWN, pygame.KEYUP]:
                    is_down = (event.type == pygame.KEYDOWN)
                    key = event.key
                    
                    if is_down and key == pygame.K_ESCAPE:
                        self.trigger_back()
                        continue
                    
                    # Distribute inputs to keyboard-controlled players
                    for p_idx in range(self.gameplay.players_count):
                        p_num = p_idx + 1
                        device = getattr(settings, f"device_p{p_num}", "Keyboard")
                        
                        if device in ["Keyboard", "Guitar"]:
                            if settings.game_mode == "Guitar Hero":
                                guitar_keys = getattr(settings, f"guitar_keys_p{p_num}", {})
                                f_map = {}
                                for fret_name, fret_idx in [("green", 0), ("red", 1), ("yellow", 2), ("blue", 3), ("orange", 4)]:
                                    val = guitar_keys.get(fret_name)
                                    if isinstance(val, int):
                                        f_map[val] = fret_idx
                                        
                                if key in f_map:
                                    self.gameplay.trigger_fret(p_idx, f_map[key], is_down)
                                    
                                val_strum = guitar_keys.get("strum")
                                if isinstance(val_strum, int) and key == val_strum and is_down:
                                    self.gameplay.trigger_strum(p_idx)
                                    
                                val_whammy = guitar_keys.get("whammy")
                                if isinstance(val_whammy, int) and key == val_whammy:
                                    self.gameplay.trigger_whammy(p_idx, is_down)
                                    
                                val_tilt = guitar_keys.get("tilt")
                                if isinstance(val_tilt, int) and key == val_tilt:
                                    self.gameplay.trigger_tilt(p_idx, is_down)
                            else:
                                # DDR/FNF/Karaoke modes
                                p_keys = getattr(settings, f"keys_p{p_num}", {})
                                k_map = {
                                    p_keys.get("left"): 0,
                                    p_keys.get("down"): 1,
                                    p_keys.get("up"): 2,
                                    p_keys.get("right"): 3
                                }
                                if key in k_map:
                                    self.gameplay.trigger_input(k_map[key], is_down, p_idx)
                                    
                elif event.type in [pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP]:
                    is_down = (event.type == pygame.JOYBUTTONDOWN)
                    btn_id = event.button
                    
                    # Find which player maps to this gamepad ID (event.joy)
                    joystick_players = [idx for idx in range(self.gameplay.players_count) if getattr(settings, f"device_p{idx+1}") in ["Gamepad", "Guitar"]]
                    if joystick_players:
                        if len(joystick_players) == 1:
                            p_idx = joystick_players[0]
                        else:
                            if event.joy < len(joystick_players):
                                p_idx = joystick_players[event.joy]
                            else:
                                continue
                        p_num = p_idx + 1
                        
                        dev_type = getattr(settings, f"device_p{p_num}")
                        if dev_type == "Guitar":
                            gp_settings = getattr(settings, f"guitar_keys_p{p_num}", {})
                        else:
                            gp_settings = getattr(settings, f"gamepad_p{p_num}", {})
                            
                        for dir_name in gp_settings.keys():
                            map_val = gp_settings.get(dir_name)
                            if isinstance(map_val, dict) and map_val.get("type") == "button":
                                if btn_id == map_val.get("id"):
                                    self.process_gamepad_gameplay_input(p_idx, dir_name, is_down)
                                        
                elif event.type == pygame.JOYHATMOTION:
                    x, y = event.value
                    
                    # Find which player maps to this gamepad ID (event.joy)
                    joystick_players = [idx for idx in range(self.gameplay.players_count) if getattr(settings, f"device_p{idx+1}") in ["Gamepad", "Guitar"]]
                    if joystick_players:
                        if len(joystick_players) == 1:
                            p_idx = joystick_players[0]
                        else:
                            if event.joy < len(joystick_players):
                                p_idx = joystick_players[event.joy]
                            else:
                                continue
                        p_num = p_idx + 1
                        
                        dev_type = getattr(settings, f"device_p{p_num}")
                        if dev_type == "Guitar":
                            gp_settings = getattr(settings, f"guitar_keys_p{p_num}", {})
                        else:
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
                    joystick_players = [idx for idx in range(self.gameplay.players_count) if getattr(settings, f"device_p{idx+1}") in ["Gamepad", "Guitar"]]
                    if joystick_players:
                        if len(joystick_players) == 1:
                            p_idx = joystick_players[0]
                        else:
                            if event.joy < len(joystick_players):
                                p_idx = joystick_players[event.joy]
                            else:
                                continue
                        p_num = p_idx + 1
                        
                        dev_type = getattr(settings, f"device_p{p_num}")
                        if dev_type == "Guitar":
                            gp_settings = getattr(settings, f"guitar_keys_p{p_num}", {})
                        else:
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
                        self.editor.handle_key_down(event.key)
                elif event.type == pygame.KEYUP:
                    self.editor.handle_key_up(event.key)
                continue

            # Feed to input manager (abstracts keyboard and controller events)
            input_result = input_manager.handle_event(event)
            
            # --- REMAP STATE EVENT HANDLING ---
            if self.state == "REMAP":
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    input_manager.cancel_remap()
                    sound_helper.play_back()
                    self.state = "SETTINGS"
                continue

            # --- SONG SELECT QUICK EDITOR SHORTCUT ---
            if self.state == "SONG_SELECT" and event.type == pygame.KEYDOWN and event.key == pygame.K_e:
                if len(self.songs_list) > 0 and self.song_index < len(self.songs_list):
                    self.start_chart_editor()
                    continue

            # --- SONG SELECT QUICK DELETE SHORTCUT ---
            if self.state == "SONG_SELECT" and event.type == pygame.KEYDOWN and event.key == pygame.K_DELETE:
                if len(self.songs_list) > 0 and self.song_index < len(self.songs_list):
                    selected_song = self.songs_list[self.song_index]
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
                
        elif self.state == "SONG_SELECT":
            if not self.songs_list:
                return
            if direction == "up":
                self.song_index = (self.song_index - 1) % len(self.songs_list)
                self.update_difficulties_list()
                sound_helper.play_select()
            elif direction == "down":
                self.song_index = (self.song_index + 1) % len(self.songs_list)
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
                self.state = "SONG_SELECT"
            elif opt == "SETTINGS":
                sound_helper.play_select()
                self.state = "SETTINGS"
            elif opt == "EXIT":
                self.running = False
                
        elif self.state == "SONG_SELECT":
            # 1. Standard Play Select or Upload
            # If songs are available, enter gameplay
            # Add a virtual song index at the end for "UPLOAD SONG"
            if len(self.songs_list) > 0 and self.song_index < len(self.songs_list):
                selected_song = self.songs_list[self.song_index]
                selected_diff = self.difficulties[self.difficulty_index]
                chk_diff = "Medium" if selected_diff == "Dynamic" else selected_diff
                
                # Check if the chart is empty/uncreated
                if len(selected_song["charts"].get(chk_diff, [])) == 0:
                    sound_helper.play_back()
                    self.warning_notification = "You need to create and save the song level first!"
                    self.warning_notification_timer = 3.0
                    return
                    
                sound_helper.play_select()
                self.gameplay = Gameplay(selected_song, selected_diff, settings.character)
                self.state = "GAMEPLAY"
            else:
                self.trigger_song_upload()
                
        elif self.state == "SETTINGS":
            opts = self.get_settings_options()
            opt = opts[self.settings_index]
            if opt == "BACK":
                sound_helper.play_back()
                self.state = "TITLE"
            elif "REMAP" in opt:
                p_num = int(opt[7])
                sound_helper.play_select()
                if "KEYBOARD" in opt:
                    self.start_key_remapping(f"p{p_num}_ddr")
                elif "GUITAR" in opt:
                    self.start_key_remapping(f"p{p_num}_guitar")
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
        if self.state == "SONG_SELECT":
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

    def is_dark_theme(self, theme):
        return theme in ["DDR-Retro", "Retro-Pixel", "Futuristic", "Neko-Pixel", "Guitar-Hero"]

    def update_difficulties_list(self):
        if not self.songs_list or self.song_index >= len(self.songs_list):
            self.difficulties = ["Easy", "Medium", "Hard", "Harder", "Crazy", "Dynamic", "Custom"]
            self.difficulty_index = self.difficulty_index % len(self.difficulties)
            return
        
        selected_song = self.songs_list[self.song_index]
        base_diffs = ["Easy", "Medium", "Hard", "Harder", "Crazy", "Dynamic"]
        charts = selected_song.get("charts", {})
        custom_diffs = [k for k in charts.keys() if k.startswith("Custom")]
        
        def sort_custom_key(val):
            parts = val.split()
            if len(parts) < 2:
                return 1
            try:
                return int(parts[1])
            except ValueError:
                return 9999
        custom_diffs.sort(key=sort_custom_key)
        
        if not custom_diffs:
            custom_diffs = ["Custom"]
            
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
            
            if settings.game_mode == "Karaoke":
                setattr(settings, f"device_p{p}", "Microphone")
            else:
                allowed = ["Keyboard", "Guitar", "Gamepad"]
                if settings.game_mode == "Guitar Hero":
                    allowed = ["Guitar", "Keyboard", "Microphone"]
                curr_dev = getattr(settings, f"device_p{p}", "Keyboard")
                if curr_dev not in allowed:
                    setattr(settings, f"device_p{p}", allowed[0])
            
            if settings.game_mode != "Karaoke":
                opts.append(f"P{p} DEVICE")
                
            dev = getattr(settings, f"device_p{p}", "Keyboard")
            if dev == "Keyboard":
                opts.append(f"REMAP P{p} KEYBOARD")
            elif dev == "Guitar":
                opts.append(f"REMAP P{p} GUITAR")
            elif dev == "Gamepad":
                opts.append(f"REMAP P{p} GAMEPAD")
            elif dev == "Microphone":
                opts.append(f"P{p} MICROPHONE")
                
        # UI Settings
        opts.append("--- UI SETTINGS ---")
        opts.append("THEME")
        
        # Sound/Graphics Settings
        opts.append("--- SOUND & GRAPHICS ---")
        opts.append("MUSIC VOLUME")
        opts.append("SFX VOLUME")
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
        elif dev == "Guitar":
            if len(input_manager.joysticks) > 0:
                for j in input_manager.joysticks:
                    j_name = j.get_name().lower()
                    if "guitar" in j_name or "riffmaster" in j_name or "rock band" in j_name or "hero" in j_name:
                        name = j.get_name()
                        if len(name) > 18:
                            name = name[:15] + "..."
                        return f"Guitar ({name})"
                fallback_name = input_manager.joysticks[0].get_name()
                if len(fallback_name) > 18:
                    fallback_name = fallback_name[:15] + "..."
                return f"Guitar ({fallback_name})"
            return "Guitar (Keyboard Mode)"
        return dev
        
    def set_player_dev(self, p_num, val):
        setattr(settings, f"device_p{p_num}", val)

    def get_microphone_list(self):
        try:
            import sounddevice as sd
            devs = sd.query_devices()
            mic_names = []
            for idx, d in enumerate(devs):
                if d.get("max_input_channels", 0) > 0:
                    name = d["name"]
                    if len(name) > 30:
                        name = name[:27] + "..."
                    mic_names.append((idx, name))
            if not mic_names:
                mic_names.append((-1, "Default Microphone"))
            return mic_names
        except Exception:
            return [(-1, "Default Microphone")]

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
        elif opt == "THEME":
            themes = ["DDR-Retro", "Minimalist", "Guitar-Hero", "Retro-Pixel", "Futuristic", "Kawaii-Pink", "Neko-Pixel"]
            curr_idx = themes.index(settings.theme) if settings.theme in themes else 0
            settings.theme = themes[(curr_idx + dir_val) % len(themes)]
            sound_helper.play_select()
        elif opt == "PLAYERS":
            settings.players = ((settings.players - 1 + dir_val) % 4) + 1
            sound_helper.play_select()
        elif opt == "GAME MODE":
            modes = ["Solo", "Co-Op", "Versus", "FNF", "Guitar Hero", "Karaoke"]
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
            if settings.game_mode == "Karaoke":
                devices = ["Microphone"]
            elif settings.game_mode == "Guitar Hero":
                devices = ["Guitar", "Keyboard", "Microphone"]
            else:
                devices = ["Keyboard", "Guitar", "Gamepad"]
                
            curr_dev = getattr(settings, f"device_p{p_num}", "Keyboard")
            if curr_dev not in devices:
                curr_dev = devices[0]
            curr_idx = devices.index(curr_dev)
            new_dev = devices[(curr_idx + dir_val) % len(devices)]
            self.set_player_dev(p_num, new_dev)
            sound_helper.play_select()
        elif opt.startswith("P") and "MICROPHONE" in opt:
            p_num = int(opt[1])
            mics = self.get_microphone_list()
            curr_idx_val = getattr(settings, f"microphone_p{p_num}")
            list_idx = 0
            for i, (m_id, m_name) in enumerate(mics):
                if m_id == curr_idx_val:
                    list_idx = i
                    break
            new_list_idx = (list_idx + dir_val) % len(mics)
            setattr(settings, f"microphone_p{p_num}", mics[new_list_idx][0])
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
            
            if self.song_index >= len(self.songs_list):
                self.song_index = max(0, len(self.songs_list) - 1)
                
            print(f"Successfully deleted song: {song['title']}")
        except Exception as e:
            print(f"Error deleting song: {e}")

    def update_high_score(self, song_metadata, difficulty, results):
        """Updates high scores locally in the song's JSON file."""
        total_notes = results["perfects"] + results["greats"] + results["goods"] + results["misses"]
        if total_notes == 0:
            grade = "F"
        else:
            perf_ratio = results["perfects"] / total_notes
            great_ratio = results["greats"] / total_notes
            miss_ratio = results["misses"] / total_notes
            
            if miss_ratio == 0 and perf_ratio > 0.95:
                grade = "AAA"
            elif perf_ratio + great_ratio > 0.85 and miss_ratio < 0.05:
                grade = "AA"
            elif perf_ratio + great_ratio > 0.70 and miss_ratio < 0.15:
                grade = "A"
            elif miss_ratio < 0.30:
                grade = "B"
            elif miss_ratio < 0.45:
                grade = "C"
            else:
                grade = "D"
                
        results["grade"] = grade
        
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
                "misses": results["misses"]
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

    def start_chart_editor(self):
        """Launches the chart editor for the selected song and difficulty."""
        if len(self.songs_list) > 0 and self.song_index < len(self.songs_list):
            sound_helper.play_select()
            selected_song = self.songs_list[self.song_index]
            selected_diff = self.difficulties[self.difficulty_index]
            if selected_diff == "Dynamic":
                selected_diff = "Medium"
                
            # Initialize empty chart list if not present (e.g. for new Custom difficulty)
            if selected_diff not in selected_song["charts"]:
                selected_song["charts"][selected_diff] = []
                
            self.editor = ChartEditor(selected_song, selected_diff)
            self.state = "EDITOR"

    def trigger_song_upload(self):
        """Triggers file explorer upload and background thread analysis."""
        sound_helper.play_select()
        
        # Run filedialog in native OS picker
        selected_file = self.open_file_picker_dialog()
        if not selected_file:
            print("Song upload canceled.")
            return

        is_zip = selected_file.lower().endswith(".zip")
        
        # Prepare copy to songs/ folder for non-zip uploads
        filename = os.path.basename(selected_file)
        sanitized_filename = filename.replace(" ", "_")
        dest_path = os.path.join(settings.SONGS_DIR, sanitized_filename)
        output_json = dest_path.rsplit(".", 1)[0] + ".json"
        
        if not is_zip:
            try:
                shutil.copy(selected_file, dest_path)
            except Exception as e:
                print(f"Error copying song file: {e}")
                return

        # Start analyzing state
        self.state = "ANALYZING"
        self.analysis_error = None
        self.analysis_success_data = None
        self.analysis_progress_text = "Loading upload file..."
        
        # Start background analysis thread
        def thread_task():
            temp_dir = None
            try:
                if is_zip:
                    self.analysis_progress_text = "Extracting ZIP archive..."
                    temp_dir = os.path.join(settings.SONGS_DIR, f"temp_unzip_{int(time.time())}")
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
                    
                    # Copy audio file to songs/
                    shutil.copy(audio_file, dest_audio_path)
                    
                    if chart_file:
                        self.analysis_progress_text = "Parsing Stepmania charts..."
                        song_data = SMParser.parse(chart_file)
                        if song_data:
                            # Fill details
                            song_data["filename"] = audio_filename
                            
                            # Get audio duration
                            try:
                                import miniaudio
                                info = miniaudio.get_file_info(dest_audio_path)
                                song_data["duration"] = info.duration
                            except Exception:
                                song_data["duration"] = 120.0 # Default fallback
                                
                            # Save JSON
                            with open(dest_json_path, "w") as f_out:
                                json.dump(song_data, f_out, indent=4)
                                
                            self.analysis_success_data = song_data
                            print(f"Successfully imported Stepmania song from ZIP: {song_data['title']}")
                        else:
                            # If parsing failed, fallback to auto-analyzer
                            print("Stepmania parser returned None. Falling back to auto-analyzer...")
                            self.analysis_progress_text = "Running Transient Peak Detection..."
                            song_data = self.analyzer.analyze_song(dest_audio_path, dest_json_path)
                            self.analysis_success_data = song_data
                    else:
                        # No SM chart file found, use auto-analyzer
                        self.analysis_progress_text = "Running Transient Peak Detection..."
                        song_data = self.analyzer.analyze_song(dest_audio_path, dest_json_path)
                        self.analysis_success_data = song_data
                else:
                    # Standard non-zip copy and analyze
                    self.analysis_progress_text = "Running Transient Peak Detection..."
                    song_data = self.analyzer.analyze_song(dest_path, output_json)
                    self.analysis_success_data = song_data
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.analysis_error = str(e)
            finally:
                if temp_dir and os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    
        self.analysis_thread = threading.Thread(target=thread_task)
        self.analysis_thread.start()

    def open_file_picker_dialog(self):
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            file_path = filedialog.askopenfilename(
                title="Select Song or Stepmania Zip (MP3/WAV/ZIP)",
                filetypes=[
                    ("Supported Files", "*.mp3;*.wav;*.ogg;*.zip"),
                    ("Audio Files", "*.mp3;*.wav;*.ogg"),
                    ("Zip Files", "*.zip")
                ]
            )
            root.destroy()
            return file_path
        except Exception as e:
            print(f"Error running native file dialog: {e}")
            return None

    def start_key_remapping(self, mode):
        self.state = "REMAP"
        self.remap_mode = mode  # "p1_ddr", "p2_ddr", "p3_ddr", "p4_ddr", "p1_guitar", "p2_guitar", ...
        self.remap_step = 0
        if "guitar" in mode:
            self.remap_directions = ["green", "red", "yellow", "blue", "orange", "strum", "whammy", "tilt"]
        elif settings.game_mode == "Guitar Hero":
            self.remap_directions = ["green", "red", "yellow", "blue", "orange", "strum", "whammy", "tilt"]
        else:
            self.remap_directions = ["left", "down", "up", "right"]
            
        self.remap_target_dir = self.remap_directions[self.remap_step]
        if "guitar" in mode:
            target_device = "guitar fret / keyboard key"
        elif "gamepad" in mode:
            target_device = "gamepad button/D-pad/Stick"
        else:
            target_device = "keyboard key"
        self.remap_info_text = f"REMAP {self.remap_target_dir.upper()}: Press a {target_device}..."
        
        input_manager.start_remap(self.remap_target_dir, self.on_remap_success)

    def on_remap_success(self, result_dict):
        if not result_dict:
            return
            
        in_type = result_dict.get("type")
        if in_type == "gamepad":
            val_to_save = result_dict["map_val"]
        else:
            val_to_save = result_dict["key"]
            
        sound_helper.play_select()
        
        # Save to correct settings property dynamically!
        target_group = None
        if "gamepad" in self.remap_mode:
            target_group = "gamepad"
        elif "guitar" in self.remap_mode or settings.game_mode == "Guitar Hero":
            target_group = "guitar"
        else:
            target_group = "keys"
            
        p_num = int(self.remap_mode[1])
        
        if target_group == "gamepad":
            prop_name = f"gamepad_p{p_num}"
            new_gp = getattr(settings, prop_name).copy()
            new_gp[self.remap_target_dir] = val_to_save
            setattr(settings, prop_name, new_gp)
        elif target_group == "guitar":
            prop_name = f"guitar_keys_p{p_num}"
            new_keys = getattr(settings, prop_name).copy()
            new_keys[self.remap_target_dir] = val_to_save
            setattr(settings, prop_name, new_keys)
        else:
            prop_name = f"keys_p{p_num}"
            new_keys = getattr(settings, prop_name).copy()
            new_keys[self.remap_target_dir] = val_to_save
            setattr(settings, prop_name, new_keys)
            
        # Next step
        self.remap_step += 1
        if self.remap_step < len(self.remap_directions):
            self.remap_target_dir = self.remap_directions[self.remap_step]
            if "guitar" in self.remap_mode:
                target_device = "guitar fret / keyboard key"
            elif "gamepad" in self.remap_mode:
                target_device = "gamepad button/D-pad/Stick"
            else:
                target_device = "keyboard key"
            self.remap_info_text = f"REMAP {self.remap_target_dir.upper()}: Press a {target_device}..."
            input_manager.start_remap(self.remap_target_dir, self.on_remap_success)
        else:
            input_manager.cancel_remap()
            self.state = "SETTINGS"

    def process_gamepad_gameplay_input(self, p_idx, dir_name, is_active):
        if settings.game_mode == "Guitar Hero":
            fret_map = {"green": 0, "red": 1, "yellow": 2, "blue": 3, "orange": 4}
            if dir_name in fret_map:
                self.gameplay.trigger_fret(p_idx, fret_map[dir_name], is_active)
            elif dir_name == "strum":
                if is_active:
                    self.gameplay.trigger_strum(p_idx)
            elif dir_name == "whammy":
                self.gameplay.trigger_whammy(p_idx, is_active)
            elif dir_name == "tilt":
                self.gameplay.trigger_tilt(p_idx, is_active)
        else:
            dir_map = {"left": 0, "down": 1, "up": 2, "right": 3}
            if dir_name in dir_map:
                self.gameplay.trigger_input(dir_map[dir_name], is_active, p_idx)

    def update(self, dt):
        theme = settings.theme
        
        # Update warning notification timer
        if self.warning_notification_timer > 0:
            self.warning_notification_timer = max(0.0, self.warning_notification_timer - dt)
        
        # Check mouse hover focus
        if self.state in ["TITLE", "SONG_SELECT", "SETTINGS"]:
            mx, my = pygame.mouse.get_pos()
            self.handle_mouse_hover(mx, my)

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
                        "difficulty": self.gameplay.difficulty,
                        "bpm": self.gameplay.bpm,
                        "score": p.score,
                        "max_combo": p.max_combo,
                        "perfects": p.perfects,
                        "greats": p.greats,
                        "goods": p.goods,
                        "misses": p.misses
                    }
                    self.update_high_score(self.songs_list[self.song_index], self.gameplay.difficulty, p_res)
                    self.results_data.append(p_res)
                self.gameplay.clean_up()
                self.gameplay = None
                self.state = "RESULTS"

    def handle_mouse_click(self, mx, my):
        w, h = SCREEN_WIDTH, SCREEN_HEIGHT
        
        # --- EDITOR SCREEN ---
        if self.state == "EDITOR" and self.editor:
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

        # --- SONG SELECT SCREEN ---
        elif self.state == "SONG_SELECT":
            list_w = 450
            # Song List click check
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
            if len(self.songs_list) > 0 and self.song_index < len(self.songs_list):
                # Check difficulty rows click (viewport-aligned)
                list_start_y = getattr(self, "diff_list_start_y", 230)
                displayed_diffs = getattr(self, "displayed_diffs", [])
                row_h = 44
                row_spacing = 6
                max_visible = 6
                start_idx = max(0, min(self.difficulty_index - max_visible // 2, len(displayed_diffs) - max_visible))
                
                for i in range(min(max_visible, len(displayed_diffs))):
                    idx = start_idx + i
                    y_pos = list_start_y + i * (row_h + row_spacing)
                    row_rect = pygame.Rect(card_x + 30, y_pos, card_w - 60, row_h)
                    if row_rect.collidepoint(mx, my):
                        if self.difficulty_index == idx:
                            # Clicking selected difficulty starts the game!
                            self.trigger_confirm()
                        else:
                            self.difficulty_index = idx
                            sound_helper.play_select()
                        return
                
                # EDIT CHART and DELETE SONG Buttons clicked
                edit_btn_rect = pygame.Rect(card_x + 30, self.btn_y, 175, 40)
                delete_btn_rect = pygame.Rect(card_x + 225, self.btn_y, 175, 40)
                
                if edit_btn_rect.collidepoint(mx, my):
                    self.start_chart_editor()
                    return
                elif delete_btn_rect.collidepoint(mx, my):
                    selected_song = self.songs_list[self.song_index]
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
                    if "REMAP" in opt or opt == "BACK":
                        self.trigger_confirm()
                    else:
                        if mx > w // 2:
                            self.adjust_setting(1)
                        else:
                            self.adjust_setting(-1)
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
            
            sub_title = desc_font.render("Furry & Fast Auto-Generated Rhythm Game", True, accent_color)
            self.screen.blit(sub_title, (w // 2 - sub_title.get_width() // 2, 230))
            
            # Developer Credits
            dev_lbl = small_font.render("developed by PixelPaws Studio", True, (130, 120, 140) if self.is_dark_theme(theme) else (90, 80, 100))
            self.screen.blit(dev_lbl, (w // 2 - dev_lbl.get_width() // 2, h - 50))
            
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
            
            # Add UPLOAD SONG option at the end of the song array
            total_items = len(self.songs_list) + 1
            visible_rows = 9
            start_row = max(0, min(self.song_index - visible_rows // 2, total_items - visible_rows))
            
            for row_idx in range(visible_rows):
                item_idx = start_row + row_idx
                if item_idx >= total_items:
                    break
                    
                is_selected = (item_idx == self.song_index)
                y_pos = 140 + row_idx * 50
                
                # Highlight bar
                if is_selected:
                    bar_color = (35, 25, 60) if self.is_dark_theme(theme) else (220, 220, 225)
                    pygame.draw.rect(self.screen, bar_color, (60, y_pos - 10, list_w - 20, 42), border_radius=5)
                    row_color = accent_color
                else:
                    row_color = text_color
                
                if item_idx < len(self.songs_list):
                    # Draw song title (truncated if too long to prevent overflowing column)
                    song = self.songs_list[item_idx]
                    song_lbl = render_truncated_text(desc_font, song["title"], 390, row_color)
                    self.screen.blit(song_lbl, (80, y_pos - 4))
                else:
                    # Draw UPLOAD option
                    upload_lbl = desc_font.render("+ UPLOAD CUSTOM SONG...", True, row_color)
                    self.screen.blit(upload_lbl, (80, y_pos - 4))
            
            # Right Card details
            card_x = 540
            card_w = 430
            pygame.draw.rect(self.screen, (20, 15, 35) if self.is_dark_theme(theme) else (235, 235, 240), (card_x, 120, card_w, list_h), border_radius=10)
            
            if len(self.songs_list) > 0 and self.song_index < len(self.songs_list):
                selected_song = self.songs_list[self.song_index]
                
                # Title (Dynamic height word wrap)
                title_end_y = draw_wrapped_text(self.screen, menu_font, selected_song["title"], text_color, card_x + 30, 150, card_w - 60)
                
                # Duration & BPM (Meta)
                meta_y = title_end_y + 12
                dur_m = int(selected_song["duration"] // 60)
                dur_s = int(selected_song["duration"] % 60)
                meta_str = f"BPM: {selected_song['bpm']}   |   Length: {dur_m:02d}:{dur_s:02d}"
                meta_surf = desc_font.render(meta_str, True, text_color)
                self.screen.blit(meta_surf, (card_x + 30, meta_y))
                
                # Dynamic list of difficulties
                tiny_font = pygame.font.SysFont("Trebuchet MS" if theme == "DDR-Retro" else "Segoe UI", 12)
                high_scores = selected_song.get("high_scores", {})
                
                # Fetch available difficulties
                base_diffs = ["Easy", "Medium", "Hard", "Harder", "Crazy", "Dynamic"]
                custom_diffs = []
                for diff_name in selected_song["charts"].keys():
                    if diff_name not in base_diffs:
                        custom_diffs.append(diff_name)
                displayed_diffs = base_diffs + custom_diffs
                self.displayed_diffs = displayed_diffs
                
                list_start_y = meta_y + 45
                self.diff_list_start_y = list_start_y
                row_h = 44
                row_spacing = 6
                max_visible = 6
                
                # Auto-center scroll window around selected difficulty index
                start_idx = max(0, min(self.difficulty_index - max_visible // 2, len(displayed_diffs) - max_visible))
                
                # Render section header
                diff_hdr_surf = small_font.render("SELECT DIFFICULTY & PLAY:", True, text_color)
                self.screen.blit(diff_hdr_surf, (card_x + 30, list_start_y - 20))
                
                # Draw scroll-up indicator if there are hidden difficulties above
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
                        
                    # Draw background with border
                    row_surf = pygame.Surface((row_rect.width, row_rect.height), pygame.SRCALPHA)
                    pygame.draw.rect(row_surf, bg_col, (0, 0, row_rect.width, row_rect.height), border_radius=6)
                    pygame.draw.rect(row_surf, border_col, (0, 0, row_rect.width, row_rect.height), width=1 if not is_selected else 2, border_radius=6)
                    self.screen.blit(row_surf, (row_rect.x, row_rect.y))
                    
                    # Difficulty Name (bold & clear)
                    diff_surf = small_font.render(diff_name.upper(), True, text_col_row)
                    self.screen.blit(diff_surf, (card_x + 45, y_pos + 4))
                    
                    # Steps Density
                    if diff_name == "Dynamic":
                        notes_count = len(selected_song["charts"].get("Medium", []))
                        steps_str = f"{notes_count} notes (Dynamic)"
                    else:
                        notes_count = len(selected_song["charts"].get(diff_name, []))
                        steps_str = f"{notes_count} notes"
                    steps_surf = tiny_font.render(steps_str, True, (210, 210, 220) if is_selected or self.is_dark_theme(theme) else (80, 80, 90))
                    self.screen.blit(steps_surf, (card_x + 45, y_pos + 22))
                    
                    # Record / Grade
                    record = high_scores.get(diff_name)
                    if record:
                        rec_str = f"Score: {record['score']:07d} ({record['grade']})"
                        rec_surf = small_font.render(rec_str, True, (255, 215, 0) if not is_selected else (255, 255, 255))
                    else:
                        rec_str = "No Record"
                        rec_surf = small_font.render(rec_str, True, (130, 120, 140) if not is_selected else (200, 200, 200))
                    self.screen.blit(rec_surf, (card_x + card_w - 45 - rec_surf.get_width(), y_pos + 12))
                
                # Draw scroll-down indicator if there are hidden difficulties below
                if start_idx + max_visible < len(displayed_diffs):
                    down_ind = tiny_font.render("▼", True, accent_color)
                    self.screen.blit(down_ind, (card_x + card_w // 2 - down_ind.get_width() // 2, list_start_y + max_visible * (row_h + row_spacing) - 4))
                
                # Bottom Buttons placement (EDIT CHART and DELETE SONG)
                btn_y = 580
                self.btn_y = btn_y
                edit_btn_rect = pygame.Rect(card_x + 30, btn_y, 175, 40)
                delete_btn_rect = pygame.Rect(card_x + 225, btn_y, 175, 40)
                
                edit_hover = edit_btn_rect.collidepoint(mx, my)
                delete_hover = delete_btn_rect.collidepoint(mx, my)
                
                # EDIT button
                edit_color = (180, 40, 120) if edit_hover else (140, 30, 90)
                if theme == "Minimalist":
                    edit_color = (210, 210, 220) if edit_hover else (220, 220, 225)
                pygame.draw.rect(self.screen, edit_color, edit_btn_rect, border_radius=6)
                
                btn_lbl_font = pygame.font.SysFont("Trebuchet MS" if theme == "DDR-Retro" else "Segoe UI", 16, bold=True)
                edit_btn_lbl = btn_lbl_font.render("EDIT CHART", True, (255, 255, 255) if (theme == "DDR-Retro" or self.is_dark_theme(theme)) else (45, 45, 55))
                self.screen.blit(edit_btn_lbl, (edit_btn_rect.centerx - edit_btn_lbl.get_width() // 2, edit_btn_rect.centery - edit_btn_lbl.get_height() // 2))
                
                # DELETE button (only for non-default songs)
                if selected_song["filename"] != "Retro_Beat.wav":
                    del_color = (220, 50, 50) if delete_hover else (180, 40, 40)
                    pygame.draw.rect(self.screen, del_color, delete_btn_rect, border_radius=6)
                    del_lbl = btn_lbl_font.render("DELETE SONG", True, (255, 255, 255))
                    self.screen.blit(del_lbl, (delete_btn_rect.centerx - del_lbl.get_width() // 2, delete_btn_rect.centery - del_lbl.get_height() // 2))
                
                # Key hint under buttons
                hint_y = btn_y + 45
                hint_str = "Press ENTER to Play Selected | E to Edit"
                hint_surf = small_font.render(hint_str, True, text_color)
                self.screen.blit(hint_surf, (card_x + card_w // 2 - hint_surf.get_width() // 2, hint_y))
            else:
                # Display Upload Card info
                upload_title = menu_font.render("UPLOAD SONG", True, text_color)
                self.screen.blit(upload_title, (card_x + 30, 150))
                
                info1 = desc_font.render("Add your own MP3 or WAV files!", True, text_color)
                info2 = desc_font.render("Our AI-based analyzer will:", True, text_color)
                self.screen.blit(info1, (card_x + 30, 220))
                self.screen.blit(info2, (card_x + 30, 260))
                
                bullets = [
                    "- Detect the rhythm & BPM",
                    "- Locate all percussion peaks",
                    "- Generate 5 synced charts",
                    "- Save to songs library"
                ]
                for idx, b in enumerate(bullets):
                    b_surf = desc_font.render(b, True, accent_color)
                    self.screen.blit(b_surf, (card_x + 50, 310 + idx * 40))
                    
                upload_hint = desc_font.render("Press ENTER to Browse PC", True, accent_color)
                self.screen.blit(upload_hint, (card_x + card_w // 2 - upload_hint.get_width() // 2, 580))
                
            footer = small_font.render("ESC: Back | Up/Down: Select Song | ENTER: Confirm", True, text_color)
            self.screen.blit(footer, (w // 2 - footer.get_width() // 2, h - 40))

            # Floating High Scores Tooltip on Hover
            mx, my = pygame.mouse.get_pos()
            hovered_song = None
            if (60 <= mx <= 490) and len(self.songs_list) > 0:
                total_items = len(self.songs_list) + 1
                visible_rows = 9
                start_row = max(0, min(self.song_index - visible_rows // 2, total_items - visible_rows))
                for row_idx in range(visible_rows):
                    item_idx = start_row + row_idx
                    if item_idx >= len(self.songs_list):
                        break
                    y_pos = 140 + row_idx * 50
                    if (y_pos - 10 <= my <= y_pos + 32):
                        hovered_song = self.songs_list[item_idx]
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
                    ty = h - th - 10
                    
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
            
            fur_col = (252, 210, 153) # Cute cream-orange cat fur
            pad_col = (244, 143, 177) # Soft pink toe pads
            shadow_col = (220, 170, 115) # Slightly darker fur for border
            
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
            tip_str = "🐈 Tip: Don't miss too many notes. Even cats only get nine lives."
            tip_surf = small_font.render(tip_str, True, (244, 143, 177) if self.is_dark_theme(theme) else (180, 50, 90))
            self.screen.blit(tip_surf, (w // 2 - tip_surf.get_width() // 2, h // 2 + 140))

        # --- DRAW STATE: GAMEPLAY ---
        elif self.state == "GAMEPLAY" and self.gameplay:
            self.gameplay.draw(self.screen)

        # --- DRAW STATE: EDITOR ---
        elif self.state == "EDITOR" and self.editor:
            self.editor.draw(self.screen)

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
                elif opt.startswith("P") and "MICROPHONE" in opt:
                    p_num = int(opt[1])
                    mics = self.get_microphone_list()
                    curr_val = getattr(settings, f"microphone_p{p_num}")
                    mic_name = "Default Microphone"
                    for m_id, name in mics:
                        if m_id == curr_val:
                            mic_name = name
                            break
                    value_text = mic_name
                elif opt == "MUSIC VOLUME":
                    value_text = f"{int(settings.music_volume * 100)}%"
                elif opt == "SFX VOLUME":
                    value_text = f"{int(settings.sfx_volume * 100)}%"
                elif opt == "SHOW CONSOLE":
                    value_text = "ENABLED" if settings.show_console else "DISABLED"
                elif "REMAP" in opt:
                    value_text = "[ Press Enter ]"
                
                # Print Left/Right indicator on selections
                if opt in ["PLAYERS", "GAME MODE", "MUSIC VOLUME", "SFX VOLUME", "SHOW CONSOLE", "THEME"] or ("CHARACTER" in opt) or ("DEVICE" in opt) or ("MICROPHONE" in opt):
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
            title_surf = menu_font.render(f"REMAP CONTROLLER INPUTS", True, text_color)
            self.screen.blit(title_surf, (w // 2 - title_surf.get_width() // 2, h // 2 - 150))
            
            # Outer block
            pygame.draw.rect(self.screen, (20, 15, 35) if self.is_dark_theme(theme) else (235, 235, 240), (w // 2 - 250, h // 2 - 80, 500, 200), border_radius=10)
            
            # Guide
            step_lbl = desc_font.render(f"Step {self.remap_step + 1} of {len(self.remap_directions)}", True, text_color)
            self.screen.blit(step_lbl, (w // 2 - step_lbl.get_width() // 2, h // 2 - 50))
            
            info_surf = menu_font.render(self.remap_info_text, True, accent_color)
            self.screen.blit(info_surf, (w // 2 - info_surf.get_width() // 2, h // 2 + 10))
            
            esc_hint = desc_font.render("Press ESC to cancel remapping", True, text_color)
            self.screen.blit(esc_hint, (w // 2 - esc_hint.get_width() // 2, h // 2 + 80))

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
                grade_color = (255, 215, 0) if grade == "AAA" else (0, 255, 128) if grade == "AA" else accent_color
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
                    
            play_hint = desc_font.render("Press ENTER to Continue", True, accent_color)
            self.screen.blit(play_hint, (w // 2 - play_hint.get_width() // 2, h - 70))

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

        pygame.display.flip()

if __name__ == "__main__":
    app = App()
    app.run()
