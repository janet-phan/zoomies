import pygame
import time
import random
import math
import os
import numpy as np
from config import settings, SCREEN_WIDTH, SCREEN_HEIGHT, TIMING_PERFECT, TIMING_GREAT, TIMING_GOOD
from sound_helper import sound_helper
from theme_manager import theme_manager

def get_or_create_speed_audio(original_filename, speed_multiplier):
    import wave
    import miniaudio
    
    if speed_multiplier == 1.0:
        return original_filename
        
    base, ext = os.path.splitext(original_filename)
    target_filename = f"{base}_speed_{speed_multiplier:.2f}.wav"
    target_path = os.path.join(settings.SONGS_DIR, target_filename)
    original_path = os.path.join(settings.SONGS_DIR, original_filename)
    
    if os.path.exists(target_path):
        return target_filename
        
    try:
        print(f"Generating sped-up audio ({speed_multiplier}x): {target_filename}...")
        decoded = miniaudio.decode_file(original_path)
        sr = decoded.sample_rate
        nchannels = decoded.nchannels
        raw_samples = decoded.samples
        
        with wave.open(target_path, "wb") as w:
            w.setnchannels(nchannels)
            w.setsampwidth(2)
            w.setframerate(int(sr * speed_multiplier))
            w.writeframes(raw_samples)
            
        print(f"Generated speed-adjusted WAV successfully: {target_filename}")
        return target_filename
    except Exception as e:
        print(f"Error generating speed audio: {e}")
        return original_filename

class Particle:
    def __init__(self, x, y, color, p_type="circle"):
        self.x = x
        self.y = y
        self.p_type = p_type
        self.color = color
        self.alpha = 255.0
        
        if p_type == "ring":
            self.radius = 10.0
            self.max_radius = 60.0
            self.vx = 0
            self.vy = 0
            self.decay = 8.0 # slower decay for rings
            self.width = 4
        elif p_type == "star":
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(3, 8)
            self.vx = math.cos(angle) * speed
            self.vy = math.sin(angle) * speed
            self.radius = random.uniform(6, 12)
            self.decay = random.uniform(8, 15)
            self.rotation = random.uniform(0, 360)
            self.rot_speed = random.uniform(-10, 10)
        else:
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(2, 6)
            self.vx = math.cos(angle) * speed
            self.vy = math.sin(angle) * speed
            self.radius = random.uniform(4, 9)
            self.decay = random.uniform(10, 20)

    def update(self):
        if self.p_type == "ring":
            self.radius += 3.5 # Expand outward fast
            self.alpha = max(0, self.alpha - self.decay)
            self.width = max(1, int(4 * (self.alpha / 255.0)))
        elif self.p_type == "star":
            self.x += self.vx
            self.y += self.vy
            self.rotation += self.rot_speed
            self.alpha = max(0, self.alpha - self.decay)
            self.radius = max(0.5, self.radius - 0.15)
        else:
            self.x += self.vx
            self.y += self.vy
            self.alpha = max(0, self.alpha - self.decay)
            self.radius = max(0.5, self.radius - 0.1)

    def draw(self, surface):
        if self.alpha <= 0:
            return
        if self.p_type == "ring":
            s = pygame.Surface((int(self.radius * 2) + 10, int(self.radius * 2) + 10), pygame.SRCALPHA)
            color = (self.color[0], self.color[1], self.color[2], int(self.alpha))
            cx = s.get_width() // 2
            cy = s.get_height() // 2
            pygame.draw.circle(s, color, (cx, cy), int(self.radius), self.width)
            surface.blit(s, (int(self.x - cx), int(self.y - cy)))
        elif self.p_type == "star":
            s = pygame.Surface((int(self.radius * 2) + 4, int(self.radius * 2) + 4), pygame.SRCALPHA)
            color = (self.color[0], self.color[1], self.color[2], int(self.alpha))
            cx = s.get_width() // 2
            cy = s.get_height() // 2
            r = self.radius
            angle_rad = math.radians(self.rotation)
            pts = []
            for i in range(4):
                a = angle_rad + i * (math.pi / 2)
                pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
                a_inner = a + (math.pi / 4)
                pts.append((cx + math.cos(a_inner) * r * 0.3, cy + math.sin(a_inner) * r * 0.3))
            pygame.draw.polygon(s, color, pts)
            surface.blit(s, (int(self.x - cx), int(self.y - cy)))
        else:
            s = pygame.Surface((int(self.radius * 2) + 2, int(self.radius * 2) + 2), pygame.SRCALPHA)
            color = (self.color[0], self.color[1], self.color[2], int(self.alpha))
            pygame.draw.circle(s, color, (s.get_width()//2, s.get_height()//2), int(self.radius))
            surface.blit(s, (int(self.x - s.get_width()//2), int(self.y - s.get_height()//2)))

class PlayerState:
    def __init__(self, chart, lane_x, character_name, player_idx, bpm, difficulty, is_dynamic):
        self.lane_x = lane_x
        self.character_name = character_name
        self.player_idx = player_idx
        self.bpm = bpm
        self.difficulty = difficulty
        self.is_dynamic = is_dynamic
        self.current_dynamic_idx = 1  # Medium baseline
        
        self.notes = [dict(note) for note in chart]
        for note in self.notes:
            note["hit"] = False
            note["missed"] = False
            
        self.active_holds = {i: None for i in range(len(lane_x))}
        self.receptor_pulse = [0.0] * len(lane_x)
        self.keys_held = [False] * len(lane_x)
        
        self.score = 0
        self.combo = 0
        self.max_combo = 0
        self.perfects = 0
        self.greats = 0
        self.goods = 0
        self.misses = 0
        
        # VTuber character images & animation state
        self.char_state = "idle"
        self.char_state_timer = 0.0
        self.char_pop = 0.0
        self.char_active_frame = 0
        self.char_images = {
            "idle": [],
            "perfect_cheer": [],
            "cheer": [],
            "miss": [],
            "umm": []
        }
        self.load_character_images()
        
        # Floating judgment
        self.last_judgment = ""
        self.last_judgment_color = (255, 255, 255)
        self.judgment_flash_timer = 0.0

    def load_character_images(self):
        char_dir = os.path.join(settings.CHARACTERS_DIR, self.character_name)
        loaded_imgs = {
            "idle": [],
            "perfect_cheer": [],
            "cheer": [],
            "miss": [],
            "umm": []
        }
        if os.path.exists(char_dir):
            for f in os.listdir(char_dir):
                f_lower = f.lower()
                if not f_lower.endswith((".png", ".jpg", ".jpeg")):
                    continue
                base_name = f_lower.rsplit(".", 1)[0]
                matched_state = None
                for state in loaded_imgs.keys():
                    if base_name == state or base_name.startswith(state + "_") or (base_name.startswith(state) and base_name[len(state):].isdigit()):
                        matched_state = state
                        break
                if matched_state:
                    try:
                        img_path = os.path.join(char_dir, f)
                        img = pygame.image.load(img_path).convert_alpha()
                        w_orig, h_orig = img.get_size()
                        scale_f = 220.0 / h_orig
                        new_w = int(w_orig * scale_f)
                        scaled_img = pygame.transform.scale(img, (new_w, 220))
                        loaded_imgs[matched_state].append(scaled_img)
                    except Exception as e:
                        print(f"Failed loading char image {f}: {e}")
                        
        if not loaded_imgs["idle"]:
            for s in ["cheer", "perfect_cheer", "miss", "umm"]:
                if loaded_imgs[s]:
                    loaded_imgs["idle"] = list(loaded_imgs[s])
                    break
            if not loaded_imgs["idle"] and os.path.exists(char_dir):
                for f in os.listdir(char_dir):
                    if f.lower().endswith((".png", ".jpg", ".jpeg")):
                        try:
                            img = pygame.image.load(os.path.join(char_dir, f)).convert_alpha()
                            w_orig, h_orig = img.get_size()
                            scale_f = 220.0 / h_orig
                            new_w = int(w_orig * scale_f)
                            scaled_img = pygame.transform.scale(img, (new_w, 220))
                            loaded_imgs["idle"].append(scaled_img)
                            break
                        except:
                            pass
        if not loaded_imgs["cheer"]:
            loaded_imgs["cheer"] = list(loaded_imgs["idle"])
        if not loaded_imgs["perfect_cheer"]:
            loaded_imgs["perfect_cheer"] = list(loaded_imgs["cheer"])
        if not loaded_imgs["miss"]:
            loaded_imgs["miss"] = list(loaded_imgs["idle"])
        if not loaded_imgs["umm"]:
            loaded_imgs["umm"] = list(loaded_imgs["miss"]) if loaded_imgs["miss"] else list(loaded_imgs["idle"])
        self.char_images = loaded_imgs

    def set_char_state(self, state, duration, pop=0.0):
        self.char_state = state
        self.char_state_timer = duration
        if pop > 0:
            self.char_pop = pop
        frames = self.char_images.get(state, [])
        if frames:
            self.char_active_frame = random.randint(0, len(frames) - 1)
        else:
            self.char_active_frame = 0

    def trigger_judgment(self, rating, color):
        self.last_judgment = rating
        self.last_judgment_color = color
        self.judgment_flash_timer = 1.0

class Gameplay:
    def get_note_rhythm_color(self, note_time, bpm):
        if bpm <= 0:
            return None
        beat_pos = note_time * (bpm / 60.0)
        fraction = beat_pos % 1.0
        
        # Priority-based matching with moderate tolerance (0.035 beats) for float drift and legacy charts
        tol = 0.035
        if fraction < tol or fraction > (1.0 - tol):
            return (255, 60, 60) # 4th: Red
        if abs(fraction - 0.5) < tol:
            return (60, 100, 255) # 8th: Blue
        if min(abs(fraction - 0.25), abs(fraction - 0.75)) < tol:
            return (255, 230, 50) # 16th: Yellow
        if min(abs(fraction - 1/3), abs(fraction - 2/3)) < tol:
            return (180, 50, 255) # 12th: Purple
        if min(abs(fraction - 1/6), abs(fraction - 5/6)) < tol:
            return (255, 60, 180) # 24th: Magenta
        if min(abs(fraction - 0.125), abs(fraction - 0.375), abs(fraction - 0.625), abs(fraction - 0.875)) < tol:
            return (255, 128, 0) # 32nd: Orange
            
        for sixteenth in [1/16, 3/16, 5/16, 7/16, 9/16, 11/16, 13/16, 15/16]:
            if abs(fraction - sixteenth) < tol:
                return (50, 220, 100) # 64th: Green
                
        return None

    def spawn_hit_particles(self, x, y, lane, rating):
        # 1. Shockwave rings and star bursts based on hit accuracy
        if rating == "PERFECT":
            # Cyan expanding shockwave + gold stars + cyan circles
            self.particles.append(Particle(x, y, (0, 255, 204), p_type="ring"))
            for _ in range(8):
                self.particles.append(Particle(x, y, (255, 223, 0), p_type="star"))
            for _ in range(12):
                self.particles.append(Particle(x, y, (0, 255, 204), p_type="circle"))
        elif rating == "GREAT":
            # Gold expanding shockwave + gold stars + white circles
            self.particles.append(Particle(x, y, (255, 215, 0), p_type="ring"))
            for _ in range(6):
                self.particles.append(Particle(x, y, (255, 215, 0), p_type="star"))
            for _ in range(8):
                self.particles.append(Particle(x, y, (255, 255, 255), p_type="circle"))
        elif rating == "GOOD":
            # Soft green expanding shockwave + green circles
            self.particles.append(Particle(x, y, (50, 205, 50), p_type="ring"))
            for _ in range(6):
                self.particles.append(Particle(x, y, (50, 205, 50), p_type="circle"))
        else:
            # Fallback for OK or other judgments (uses theme lane color)
            from config import settings
            from theme_manager import ThemeManager
            # Inline temp ThemeManager instance to read lane color
            tm = ThemeManager()
            p_color = tm.get_lane_color(lane, settings.theme)
            for _ in range(8):
                self.particles.append(Particle(x, y, p_color, p_type="circle"))

    def __init__(self, song_metadata, difficulty, character_name="Miku"):
        self.metadata = song_metadata
        self.difficulty = difficulty
        self.is_dynamic = (difficulty == "Dynamic")
        self.all_charts = song_metadata["charts"]
        self.bpm = song_metadata["bpm"]
        self.song_filename = song_metadata["filename"]
        
        # Speed scaling
        self.speed_multiplier = 1.0
        if self.difficulty == "Harder":
            self.speed_multiplier = 1.15
        elif self.difficulty == "Crazy":
            self.speed_multiplier = 1.50
            
        if self.speed_multiplier != 1.0:
            self.song_filename = get_or_create_speed_audio(self.song_filename, self.speed_multiplier)
            
        self.song_path = pygame.mixer.music.load(os.path.join(settings.SONGS_DIR, self.song_filename))
        sound_helper.init_sounds()
        
        # Baseline chart
        if self.is_dynamic:
            self.baseline_chart = song_metadata["charts"]["Medium"]
        else:
            self.baseline_chart = song_metadata["charts"][difficulty]
            
        # Modes
        raw_mode = settings.game_mode
        self.players_count = settings.players
        
        # Translate settings game modes to internal gameplay mode states
        if raw_mode == "FNF":
            self.game_mode = "Versus"
            self.players_count = 2  # Versus is forced 2 players
        elif raw_mode == "Versus":
            self.game_mode = "Versus"
            self.players_count = 2  # Versus is forced 2 players
        else:
            self.game_mode = "DDR"
            if raw_mode == "Solo":
                self.players_count = 1
                
        self.mic_trackers = {}
        self.vocal_targets = []
        self.vocal_history = {}
        
        self.num_lanes = 4
        
        # Select width and spacing based on player count to fit side-by-side
        if self.players_count == 4:
            self.lane_width = 42
            self.lane_spacing = 8
        elif self.players_count == 3:
            self.lane_width = 58
            self.lane_spacing = 12
        elif self.players_count == 2:
            self.lane_width = 72
            self.lane_spacing = 18
        else:
            self.lane_width = 82
            self.lane_spacing = 22
            
        self.total_width = (self.lane_width * self.num_lanes) + (self.lane_spacing * (self.num_lanes - 1))
        
        # Lock chart to default 4 lanes
        self.chart = [dict(note) for note in self.baseline_chart]
            
        # Layout positioning
        self.is_downscroll = (settings.theme == "Guitar-Hero")
        self.receptor_y = 620 if self.is_downscroll else 120
        self.scroll_speed = 460
        
        # Initialize Player States with side-by-side highways
        self.players = []
        char_names = [
            settings.character,
            settings.character_p2,
            getattr(settings, "character_p3", "Miku"),
            getattr(settings, "character_p4", "Beat Bot")
        ]
        
        for p_idx in range(self.players_count):
            c_x = int((SCREEN_WIDTH / (self.players_count + 1)) * (p_idx + 1))
            start_x = c_x - self.total_width // 2
            lane_x = [start_x + i * (self.lane_width + self.lane_spacing) + self.lane_width // 2 for i in range(self.num_lanes)]
            char_name = char_names[p_idx % len(char_names)]
            self.players.append(PlayerState(self.chart, lane_x, char_name, p_idx, self.bpm, self.difficulty, self.is_dynamic))
            
        # Particle effects
        self.particles = []
        self.bg_particles = []
        for _ in range(25):
            self.bg_particles.append({
                "x": random.randint(0, SCREEN_WIDTH),
                "y": random.randint(0, SCREEN_HEIGHT),
                "speed": random.uniform(25, 75),
                "base_radius": random.uniform(3, 8),
                "color": (random.randint(180, 255), 0, random.randint(180, 255))
            })
            
        self.song_started = False
        self.start_time = 0
        self.paused = False
        self.pause_start_time = 0
        self.elapsed_pause_time = 0
        self.intro_delay = 2.0
        self.intro_start_time = time.time()
        self.game_over = False
        self.clock = pygame.Clock()
        
        # Held frets for guitar strum bar logic
        self.held_frets = {p_idx: [False] * self.num_lanes for p_idx in range(self.players_count)}

    def start_music(self):
        pygame.mixer.music.set_volume(settings.music_volume)
        pygame.mixer.music.play()
        self.start_time = time.time()
        self.song_started = True

    def get_current_time(self):
        if not self.song_started:
            return 0
        if self.paused:
            return self.pause_start_time - self.start_time - self.elapsed_pause_time
        return time.time() - self.start_time - self.elapsed_pause_time

    def toggle_pause(self):
        if self.game_over:
            return
        self.paused = not self.paused
        if self.paused:
            self.pause_start_time = time.time()
            pygame.mixer.music.pause()
        else:
            self.elapsed_pause_time += time.time() - self.pause_start_time
            pygame.mixer.music.unpause()

    def change_dynamic_difficulty(self, target_idx, player_idx=0):
        p = self.players[player_idx]
        if not p.is_dynamic or p.current_dynamic_idx == target_idx:
            return
            
        diffs = ["Easy", "Medium", "Hard", "Harder", "Crazy"]
        new_diff = diffs[target_idx - 1]
        p.current_dynamic_idx = target_idx
        p.difficulty = new_diff
        
        curr_time = self.get_current_time()
        lookahead = 0.5
        
        # Keep past notes, merge upcoming notes
        kept_notes = [note for note in p.notes if note["hit"] or note["missed"] or note["time"] < curr_time + lookahead]
        future_notes = []
        new_chart = self.all_charts[new_diff]
        for note in new_chart:
            if note["time"] >= curr_time + lookahead:
                n_copy = dict(note)
                if self.num_lanes == 5:
                    new_lanes = []
                    for lane in n_copy["lanes"]:
                        if lane == 3:
                            new_lanes.append(random.choice([3, 4]))
                        else:
                            new_lanes.append(lane)
                    n_copy["lanes"] = sorted(list(set(new_lanes)))
                n_copy["hit"] = False
                n_copy["missed"] = False
                future_notes.append(n_copy)
                
        p.notes = sorted(kept_notes + future_notes, key=lambda x: x["time"])
        print(f"P{p.player_idx+1} dynamic difficulty changed to {new_diff}!")



    def trigger_input(self, direction_idx, is_down, player_idx=0):
        if player_idx >= len(self.players) or self.paused or self.game_over:
            return
            
        p = self.players[player_idx]
        if is_down:
            p.keys_held[direction_idx] = True
            p.receptor_pulse[direction_idx] = 1.0
            
            # Find closest note
            curr_time = self.get_current_time()
            best_note = None
            best_diff = TIMING_GOOD
            
            for note in p.notes:
                if not note["hit"] and not note["missed"] and direction_idx in note["lanes"]:
                    diff = abs(note["time"] - curr_time)
                    if diff < best_diff:
                        best_diff = diff
                        best_note = note
                        
            if best_note:
                rating = "GOOD"
                color = (200, 200, 50)
                score_gain = settings.SCORE_GOOD
                
                if best_diff <= TIMING_PERFECT:
                    rating = "PERFECT"
                    color = (0, 255, 204)
                    score_gain = settings.SCORE_PERFECT
                    p.perfects += 1
                elif best_diff <= TIMING_GREAT:
                    rating = "GREAT"
                    color = (255, 215, 0)
                    score_gain = settings.SCORE_GREAT
                    p.greats += 1
                else:
                    p.goods += 1
                    
                best_note["hit"] = True
                p.score += score_gain
                p.combo += 1
                if p.combo > p.max_combo:
                    p.max_combo = p.combo
                    
                if best_note.get("type") == "hold":
                    p.active_holds[direction_idx] = best_note
                    
                p.set_char_state("perfect_cheer" if rating == "PERFECT" else "cheer", 1.0, pop=1.2)
                sound_helper.play_hit()
                
                # Spawn particles
                x = p.lane_x[direction_idx]
                y = self.receptor_y
                self.spawn_hit_particles(x, y, direction_idx, rating)
                    
                p.trigger_judgment(rating, color)
                
                # Dynamic mode scale (P1 only)
                if p.player_idx == 0 and p.is_dynamic:
                    if p.combo == 20:
                        self.change_dynamic_difficulty(2)
                    elif p.combo == 50:
                        self.change_dynamic_difficulty(3)
                    elif p.combo == 100:
                        self.change_dynamic_difficulty(4)
            else:
                p.set_char_state("umm", 0.8)
        else:
            # Key up
            p.keys_held[direction_idx] = False
            curr_time = self.get_current_time()
            active_hold = p.active_holds[direction_idx]
            if active_hold is not None:
                if curr_time < active_hold["endtime"] - TIMING_GOOD:
                    # Let go too early!
                    active_hold["missed"] = True
                    p.misses += 1
                    p.combo = 0
                    p.set_char_state("miss", 1.0)
                    p.trigger_judgment("HOLD MISS", (220, 50, 50))
                    sound_helper.play_miss()
                else:
                    # Success
                    p.score += 500
                    p.trigger_judgment("HOLD OK", (0, 255, 204))
                p.active_holds[direction_idx] = None

    def update(self, dt):
        self.clock.tick()
        # Update character states & receptor pulses
        for p in self.players:
            p.char_pop = max(0.0, p.char_pop - dt * 4.0)
            if p.char_state != "idle":
                p.char_state_timer -= dt
                if p.char_state_timer <= 0:
                    p.char_state = "idle"
            for i in range(len(p.receptor_pulse)):
                if p.keys_held[i]:
                    p.receptor_pulse[i] = 1.0
                else:
                    p.receptor_pulse[i] = max(0.0, p.receptor_pulse[i] - dt * 7.0)
                    
        # Update background particles
        for bp in self.bg_particles:
            bp["y"] += bp["speed"] * dt
            if bp["y"] > SCREEN_HEIGHT:
                bp["y"] = 0
                bp["x"] = random.randint(0, SCREEN_WIDTH)
                
        # Update hit particles
        for part in list(self.particles):
            part.update()
            if part.alpha <= 0:
                self.particles.remove(part)
                
        if not self.song_started:
            if time.time() - self.intro_start_time >= self.intro_delay:
                self.start_music()
            return
            
        if self.paused or self.game_over:
            return
            
        curr_time = self.get_current_time()
        
        # Standard Highway Tap/Hold loops for all players
        for p in self.players:
            # Check misses and hold completions
            for note in p.notes:
                if not note["hit"] and not note["missed"] and curr_time > note["time"] + TIMING_GOOD:
                    note["missed"] = True
                    p.misses += 1
                    p.combo = 0
                    p.trigger_judgment("MISS", (180, 50, 50))
                    p.set_char_state("miss", 1.0)
                    sound_helper.play_miss()
                    
                    if p.player_idx == 0 and p.is_dynamic:
                        p.current_dynamic_idx = max(1, p.current_dynamic_idx - 1)
                        self.change_dynamic_difficulty(p.current_dynamic_idx)
                            
                # Continuous scoring for active holds
                for lane, hold_note in p.active_holds.items():
                    if hold_note is not None:
                        if curr_time >= hold_note["endtime"]:
                            gain = 500
                            p.score += gain
                            p.trigger_judgment("HOLD OK", (0, 255, 204))
                            p.active_holds[lane] = None
                        else:
                            gain = int(100 * dt)
                            p.score += gain
                            
        # Check if song finished
        if self.song_started and not pygame.mixer.music.get_busy() and not self.paused:
            self.game_over = True

    def draw_versus_bar(self, surface):
        w, h = surface.get_size()
        bar_w = 400
        bar_h = 16
        bar_x = (w - bar_w) // 2
        bar_y = 35
        
        pygame.draw.rect(surface, (25, 22, 32), (bar_x - 2, bar_y - 2, bar_w + 4, bar_h + 4), border_radius=6)
        
        p1 = self.players[0]
        p2 = self.players[1]
        total = p1.score + p2.score
        ratio = 0.5 if total == 0 else p1.score / total
        
        p1_color = (255, 45, 120)
        p2_color = (0, 255, 204)
        
        # P2 on right side
        pygame.draw.rect(surface, p2_color, (bar_x, bar_y, bar_w, bar_h), border_radius=4)
        # P1 on left side
        p1_w = int(bar_w * ratio)
        if p1_w > 0:
            pygame.draw.rect(surface, p1_color, (bar_x, bar_y, p1_w, bar_h), border_radius=4)
            
        # Draw center notch
        pygame.draw.line(surface, (255, 255, 255), (bar_x + bar_w // 2, bar_y), (bar_x + bar_w // 2, bar_y + bar_h), 2)
        
        # Draw bobbing indicator cursor
        cursor_x = bar_x + int(bar_w * ratio)
        bob = int(math.sin(self.get_current_time() * 8.0) * 3)
        cursor_y = bar_y + bar_h // 2 + bob
        
        # Color circle indicator depending on lead
        col = p1_color if ratio > 0.55 else p2_color if ratio < 0.45 else (255, 255, 255)
        pygame.draw.circle(surface, col, (cursor_x, cursor_y), 9)
        pygame.draw.circle(surface, (255, 255, 255), (cursor_x, cursor_y), 9, width=2)
        
        # Versus title label
        vs_font = pygame.font.SysFont("Impact", 18)
        vs_surf = vs_font.render("VERSUS BATTLE", True, (255, 255, 255))
        surface.blit(vs_surf, (w // 2 - vs_surf.get_width() // 2, 10))

    def draw(self, surface):
        theme = settings.theme
        theme_manager.draw_background_grid(surface, theme, self.get_current_time() * (self.bpm / 60.0))
        
        w, h = surface.get_size()
        curr_time = self.get_current_time()
        beat_progress = curr_time * (self.bpm / 60.0)
        
        # --- ON-BEAT FULLSCREEN GLOW PULSE ---
        # --- ON-BEAT FULLSCREEN GLOW PULSE ---
        beat_pulse = max(0.0, 1.0 - (beat_progress % 1.0) * 4.0)
        if beat_pulse > 0.0:
            glow_surf = pygame.Surface((w, h), pygame.SRCALPHA)
            glow_col = (0, 255, 204, int(beat_pulse * 18)) # Cool teal beat pulse
            glow_surf.fill(glow_col)
            surface.blit(glow_surf, (0, 0))
        
        # Draw FNF battle bar in Versus mode
        if self.game_mode == "Versus" and len(self.players) == 2:
            self.draw_versus_bar(surface)
            
        for p in self.players:
            # Draw highway backdrop panel
            hw_x = p.lane_x[0] - self.lane_width // 2 - 10
            hw_w = self.total_width + 20
            
            # --- ON-BEAT RECEPTOR LIGHT STRIP ---
            beat_pulse = max(0.0, 1.0 - (beat_progress % 1.0) * 4.0)
            if beat_pulse > 0.0:
                flash_y = self.receptor_y
                flash_h = 44
                flash_surf = pygame.Surface((hw_w, flash_h), pygame.SRCALPHA)
                f_color = (0, 255, 204)
                f_alpha = int(beat_pulse * 64)
                pygame.draw.rect(flash_surf, (f_color[0], f_color[1], f_color[2], f_alpha), (0, 0, hw_w, flash_h), border_radius=4)
                surface.blit(flash_surf, (hw_x, flash_y - flash_h // 2 + self.lane_width // 2))

            pygame.draw.rect(surface, (12, 10, 18, 180) if theme != "Minimalist" else (240, 240, 245, 180), (hw_x, 0, hw_w, h))
            # Pulse cyan highway sides on beat
            if theme == "DDR-Retro":
                bd_color = tuple(int(c1 + (c2 - c1) * beat_pulse) for c1, c2 in zip((0, 150, 120), (0, 255, 204)))
                line_w = 2 + int(beat_pulse * 2)
            else:
                bd_color = (180, 180, 190)
                line_w = 2
            pygame.draw.line(surface, bd_color, (hw_x, 0), (hw_x, h), line_w)
            pygame.draw.line(surface, bd_color, (hw_x + hw_w, 0), (hw_x + hw_w, h), line_w)
            
            # Draw Receptor targets calling theme_manager.draw_arrow
            for idx, lx in enumerate(p.lane_x):
                pulse = p.receptor_pulse[idx]
                theme_manager.draw_arrow(surface, lx, self.receptor_y, idx, theme, scale=self.lane_width/80.0, is_receptor=True, active_pulse=pulse)
                
            # Draw Hold trails
            for note in p.notes:
                if not note["missed"] and note.get("type") == "hold":
                    for lane in note["lanes"]:
                        is_currently_holding = (p.active_holds[lane] == note)
                        if not note["hit"] or is_currently_holding:
                            lx = p.lane_x[lane]
                            t_diff_start = note["time"] - curr_time
                            
                            # Corrected scroll coordinates:
                            # Up-scroll: moves from bottom upwards to receptor Y = 120
                            # Down-scroll: moves from top downwards to receptor Y = 620
                            if not self.is_downscroll:
                                start_y = self.receptor_y + int(t_diff_start * self.scroll_speed)
                            else:
                                start_y = self.receptor_y - int(t_diff_start * self.scroll_speed)
                                
                            t_diff_end = note["endtime"] - curr_time
                            if not self.is_downscroll:
                                end_y = self.receptor_y + int(t_diff_end * self.scroll_speed)
                            else:
                                end_y = self.receptor_y - int(t_diff_end * self.scroll_speed)
                                
                            if is_currently_holding:
                                start_y = self.receptor_y
                                
                            trail_color = theme_manager.get_lane_color(lane, theme)
                            if self.is_downscroll:
                                th = int(start_y - end_y)
                                ty = int(end_y)
                            else:
                                th = int(end_y - start_y)
                                ty = int(start_y)
                                
                            if th > 0:
                                trail_surf = pygame.Surface((24, th), pygame.SRCALPHA)
                                trail_surf.fill((trail_color[0], trail_color[1], trail_color[2], 130))
                                surface.blit(trail_surf, (lx - 12, ty))
                                pygame.draw.rect(surface, trail_color, (lx - 15, int(end_y) - 4, 30, 8), border_radius=2)
                            
            # Draw Note heads calling theme_manager.draw_arrow
            for note in p.notes:
                if not note["hit"] and not note["missed"]:
                    t_diff = note["time"] - curr_time
                    if not self.is_downscroll:
                        y = self.receptor_y + int(t_diff * self.scroll_speed)
                    else:
                        y = self.receptor_y - int(t_diff * self.scroll_speed)
                        
                    if 0 <= y <= SCREEN_HEIGHT:
                        # Determine rhythm color
                        n_col = self.get_note_rhythm_color(note["time"], self.bpm)
                            
                        for lane in note["lanes"]:
                            lx = p.lane_x[lane]
                            theme_manager.draw_arrow(surface, lx, y, lane, theme, scale=self.lane_width/80.0, is_receptor=False, note_color=n_col)
                                
            # Floating Judgment
            if p.last_judgment and p.judgment_flash_timer > 0:
                p.judgment_flash_timer -= 0.016
                font_hud = pygame.font.SysFont("Trebuchet MS" if theme == "DDR-Retro" else "Segoe UI", 24, bold=True)
                alpha = int(max(0, min(255, p.judgment_flash_timer * 255)))
                
                jx = p.lane_x[self.num_lanes // 2]
                jy = self.receptor_y + (40 if self.is_downscroll else -45)
                
                txt_surf = font_hud.render(p.last_judgment, True, p.last_judgment_color)
                alpha_surf = pygame.Surface(txt_surf.get_size(), pygame.SRCALPHA)
                alpha_surf.fill((255, 255, 255, alpha))
                alpha_surf.blit(txt_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                surface.blit(alpha_surf, (jx - alpha_surf.get_width() // 2, jy - alpha_surf.get_height() // 2))
                
            # HUD details
            hud_font = pygame.font.SysFont("Impact" if theme in ["DDR-Retro", "Retro-Pixel"] else "Segoe UI", 16 if self.players_count > 2 else 20)
            p_lbl = f"P{p.player_idx+1}: {p.character_name}"
            score_lbl = f"SCORE: {p.score:07d}"
            combo_lbl = f"COMBO: {p.combo} (MAX {p.max_combo})"
            
            p_surf = hud_font.render(p_lbl, True, (255, 255, 255) if theme != "Minimalist" else (45, 45, 55))
            score_surf = hud_font.render(score_lbl, True, (0, 255, 204) if theme != "Minimalist" else (45, 45, 55))
            combo_surf = hud_font.render(combo_lbl, True, (255, 215, 0) if theme != "Minimalist" else (45, 45, 55))
            
            hx = p.lane_x[0] - self.lane_width // 2
            hy = h - 160 if self.is_downscroll else 20
            
            surface.blit(p_surf, (hx, hy))
            surface.blit(score_surf, (hx, hy + 22))
            surface.blit(combo_surf, (hx, hy + 44))
            

            # Cheering character
            self.draw_player_character(surface, p, theme, beat_progress)
            
        # Draw hit particles
        for part in self.particles:
            part.draw(surface)
            
        # Countdown overlay
        if not self.song_started:
            font_large = pygame.font.SysFont("Impact", 72)
            elapsed = time.time() - self.intro_start_time
            remaining = int(math.ceil(self.intro_delay - elapsed))
            if remaining > 0:
                count_lbl = font_large.render(str(remaining), True, (255, 255, 255) if theme != "Minimalist" else (45, 45, 55))
                surface.blit(count_lbl, (w // 2 - count_lbl.get_width() // 2, h // 2 - count_lbl.get_height() // 2))
                
        if self.paused:
            self.draw_pause_screen(surface, theme)

    def draw_player_character(self, surface, p, theme, beat_progress):
        w, h = surface.get_size()
        beat_phase = beat_progress % 1.0
        bounce_scale = 1.0 + 0.08 * math.sin(beat_phase * math.pi) * math.exp(-beat_phase * 1.5)
        hit_scale = 1.0 + 0.15 * p.char_pop
        scale = bounce_scale * hit_scale
        
        # Position VTuber dynamically directly below/above the player's highway
        c_x = int((w / (self.players_count + 1)) * (p.player_idx + 1))
        px = c_x
        py = 150 if self.is_downscroll else h - 130
        
        state = p.char_state
        frames = p.char_images.get(state, [])
        if frames:
            if state == "idle":
                beat_idx = int(beat_progress)
                frame_idx = beat_idx % len(frames)
                char_surface = frames[frame_idx]
            else:
                frame_idx = p.char_active_frame % len(frames)
                char_surface = frames[frame_idx]
                
            cw, ch = char_surface.get_size()
            
            # Scale character down if 3 or 4 players to avoid overlapping highways
            char_scale_factor = 0.55 if self.players_count >= 3 else 1.0
            sw = int(cw * scale * char_scale_factor)
            sh = int(ch * scale * char_scale_factor)
            
            x = px - sw // 2
            y = py - sh // 2
            
            # Flip character if on right side to face center
            if px > w // 2:
                char_surface = pygame.transform.flip(char_surface, True, False)
                
            scaled_char = pygame.transform.scale(char_surface, (sw, sh))
            surface.blit(scaled_char, (x, y))

    def draw_pause_screen(self, surface, theme):
        w, h = surface.get_size()
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((10, 8, 15, 200) if theme != "Minimalist" else (240, 240, 245, 200))
        surface.blit(overlay, (0, 0))
        
        font_p = pygame.font.SysFont("Impact" if theme != "Minimalist" else "Segoe UI", 48)
        lbl_p = font_p.render("GAME PAUSED", True, (255, 255, 255) if theme != "Minimalist" else (45, 45, 55))
        surface.blit(lbl_p, (w // 2 - lbl_p.get_width() // 2, h // 2 - 50))
        
        font_sub = pygame.font.SysFont("Segoe UI", 20)
        lbl_sub = font_sub.render("Press ESCAPE to Resume  |  BACKSPACE to Quit", True, (0, 255, 204) if theme != "Minimalist" else (45, 45, 55))
        surface.blit(lbl_sub, (w // 2 - lbl_sub.get_width() // 2, h // 2 + 20))

    def clean_up(self):
        """Stops and clears all active microphone pitch trackers."""
        if hasattr(self, "mic_trackers"):
            for p_idx, tracker in list(self.mic_trackers.items()):
                try:
                    tracker.stop()
                except Exception as e:
                    print(f"Error stopping mic tracker {p_idx}: {e}")
            self.mic_trackers.clear()
