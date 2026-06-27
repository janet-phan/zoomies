import pygame
import os
import json
import math
from config import settings, SCREEN_WIDTH, SCREEN_HEIGHT
from sound_helper import sound_helper

class ChartEditor:
    def __init__(self, song_metadata, difficulty):
        self.metadata = song_metadata
        self.difficulty = difficulty
        self.chart = song_metadata["charts"][difficulty]
        self.bpm = song_metadata["bpm"]
        self.song_filename = song_metadata["filename"]
        
        # Paths
        self.song_wav_path = os.path.join(settings.SONGS_DIR, self.song_filename)
        self.output_json_path = os.path.join(settings.SONGS_DIR, self.song_filename.rsplit(".", 1)[0] + ".json")
        
        # Audio Player State
        self.music_loaded = False
        self.load_music()
        
        # Timeline State (in seconds)
        self.editor_time = 0.0
        self.song_duration = song_metadata["duration"]
        self.playing = False
        self.play_start_time = 0.0
        self.play_start_editor_time = 0.0
        self.playback_speed = 1.0
        
        # Grid settings
        self.grid_snaps = [4, 8, 16, 32, "Free"]  # 4th, 8th, 16th, 32nd, or Free placement
        self.snap_index = 1                       # Default 8th notes
        self.beat_interval = 60.0 / self.bpm
        
        # Undo/Redo stacks
        self.undo_stack = []
        self.redo_stack = []
        
        # Rendering Layout
        self.lane_width = 70
        self.lane_spacing = 15
        self.total_width = (self.lane_width * 4) + (self.lane_spacing * 3)
        self.start_x = 100  # Shifted left to make room for sidebar controls
        self.receptor_y = 550  # Receptor bar is near bottom of editor
        self.scroll_speed = 300  # Pixels per second
        
        self.lane_x = [
            self.start_x + i * (self.lane_width + self.lane_spacing) + self.lane_width // 2
            for i in range(4)
        ]
        
        # Save confirmation alert
        self.save_notification_timer = 0.0
        self.unsaved_changes = False
        
        # Selection and Clipboard states
        self.selection_start = None
        self.selection_end = None
        self.clipboard = []
        
        # Scrollbar Dragging State
        self.dragging_scrollbar = False
        
        # Waveform Visualizer State
        self.wave_envelope = []
        self.wave_fps = 100
        self.load_waveform_envelope()
        
        # Hold note dragging state
        self.dragging_hold_note = None
        self.dragging_hold_lane = None
        
        # Live recording state
        self.recording = False
        self.active_record_notes = {}

    def load_music(self):
        try:
            pygame.mixer.music.load(self.song_wav_path)
            pygame.mixer.music.set_volume(settings.music_volume)
            self.music_loaded = True
        except Exception as e:
            print(f"Error loading editor music: {e}")
            self.music_loaded = False

    def load_waveform_envelope(self):
        try:
            import miniaudio
            import numpy as np
            if os.path.exists(self.song_wav_path):
                # Decode audio file
                decoded = miniaudio.decode_file(self.song_wav_path)
                raw_samples = np.frombuffer(decoded.samples, dtype=np.int16)
                if decoded.nchannels > 1:
                    samples = raw_samples.reshape(-1, decoded.nchannels).mean(axis=1).astype(np.float32)
                else:
                    samples = raw_samples.astype(np.float32)
                    
                # Normalize amplitude
                max_val = np.max(np.abs(samples))
                if max_val > 0:
                    samples /= max_val
                    
                # Calculate energy bins
                bin_size = decoded.sample_rate // self.wave_fps
                if bin_size > 0:
                    num_bins = len(samples) // bin_size
                    # Reshape and take max absolute value in each bin for clean envelope peaks
                    truncated_len = num_bins * bin_size
                    binned = samples[:truncated_len].reshape(num_bins, bin_size)
                    self.wave_envelope = np.max(np.abs(binned), axis=1).tolist()
                else:
                    self.wave_envelope = []
        except Exception as e:
            print(f"Error generating waveform envelope: {e}")
            self.wave_envelope = []

    def toggle_play(self):
        if not self.music_loaded:
            return
            
        if self.playing:
            pygame.mixer.music.stop()
            self.playing = False
        else:
            if self.editor_time < 0.0:
                self.playing = True
            else:
                audio_filename = self.metadata.get("filename")
                if audio_filename:
                    from gameplay import get_or_create_speed_audio
                    speed_filename = get_or_create_speed_audio(audio_filename, self.playback_speed)
                    speed_path = os.path.join(settings.SONGS_DIR, speed_filename)
                    try:
                        pygame.mixer.music.load(speed_path)
                        pygame.mixer.music.play(start=self.editor_time / self.playback_speed)
                    except Exception as e:
                        print(f"Error playing speed audio: {e}")
                        pygame.mixer.music.load(self.music_path)
                        pygame.mixer.music.play(start=self.editor_time)
                
                self.play_start_time = pygame.time.get_ticks() / 1000.0
                self.play_start_editor_time = self.editor_time
                self.playing = True

    def get_snap_duration(self):
        """Returns duration of one grid step in seconds."""
        snap_val = self.grid_snaps[self.snap_index]
        if snap_val == "Free":
            return 0.001  # 1ms step minimum
        subdiv_per_beat = snap_val / 4.0
        return self.beat_interval / subdiv_per_beat

    def snap_time(self, t):
        """Snaps a timestamp to the nearest grid step."""
        snap_val = self.grid_snaps[self.snap_index]
        if snap_val == "Free":
            return max(0.0, min(self.song_duration, t))
        step = self.get_snap_duration()
        snapped = round(t / step) * step
        return max(0.0, min(self.song_duration, snapped))

    def push_undo(self):
        import copy
        self.undo_stack.append(copy.deepcopy(self.chart))
        self.redo_stack.clear()
        if len(self.undo_stack) > 50:
            self.undo_stack.pop(0)

    def undo(self):
        if self.undo_stack:
            import copy
            self.redo_stack.append(copy.deepcopy(self.chart))
            self.chart = self.undo_stack.pop()
            self.metadata["charts"][self.difficulty] = self.chart
            self.unsaved_changes = True
            try:
                sound_helper.play_back()
            except:
                pass

    def redo(self):
        if self.redo_stack:
            import copy
            self.undo_stack.append(copy.deepcopy(self.chart))
            self.chart = self.redo_stack.pop()
            self.metadata["charts"][self.difficulty] = self.chart
            self.unsaved_changes = True
            try:
                sound_helper.play_hit()
            except:
                pass

    def get_lane_from_key(self, key):
        """Maps a Pygame key code to the corresponding lane index."""
        num_lanes = 5 if settings.game_mode == "Guitar" else 4
        if num_lanes == 5:
            guitar_keys = {
                pygame.K_a: 0,
                pygame.K_s: 1,
                pygame.K_d: 2,
                pygame.K_f: 3,
                pygame.K_g: 4,
                pygame.K_1: 0,
                pygame.K_2: 1,
                pygame.K_3: 2,
                pygame.K_4: 3,
                pygame.K_5: 4
            }
            return guitar_keys.get(key, -1)
        else:
            ddr_keys = {
                pygame.K_d: 0,
                pygame.K_f: 1,
                pygame.K_j: 2,
                pygame.K_k: 3
            }
            left_k = settings.keys.get("left")
            down_k = settings.keys.get("down")
            up_k = settings.keys.get("up")
            right_k = settings.keys.get("right")
            settings_map = {
                left_k: 0,
                down_k: 1,
                up_k: 2,
                right_k: 3
            }
            if key in ddr_keys:
                return ddr_keys[key]
            return settings_map.get(key, -1)

    def toggle_record(self):
        """Toggles live recording state on/off, flushing active keys to notes."""
        if self.recording:
            # Toggling OFF: sweep any active press events into tap notes
            self.recording = False
            if self.active_record_notes:
                self.push_undo()
                for lane, start_time in self.active_record_notes.items():
                    snapped_start = self.snap_time(start_time)
                    found = None
                    for note in self.chart:
                        if abs(note["time"] - snapped_start) < 0.005:
                            found = note
                            break
                    if found:
                        if lane not in found["lanes"]:
                            found["lanes"].append(lane)
                            found["lanes"].sort()
                            found["type"] = "jump" if len(found["lanes"]) > 1 else "single"
                    else:
                        new_note = {
                            "time": float(round(snapped_start, 3)),
                            "lanes": [lane],
                            "type": "single"
                        }
                        self.chart.append(new_note)
                self.chart.sort(key=lambda x: x["time"])
                self.unsaved_changes = True
            self.active_record_notes.clear()
            
            # Stop playback
            if self.playing:
                self.toggle_play()
            print("Live recording stopped.")
        else:
            # Toggling ON: clear states and trigger playback
            self.recording = True
            self.active_record_notes.clear()
            if not self.playing:
                self.toggle_play()
            print("Live recording started.")

    def toggle_note(self, lane, target_time):
        """Adds or removes a note in a specific lane at target_time."""
        self.push_undo()
        snapped_t = self.snap_time(target_time)
        
        # Check if note already exists at this timestamp (within 5ms)
        found_note = None
        for note in self.chart:
            if abs(note["time"] - snapped_t) < 0.005:
                found_note = note
                break
                
        if found_note:
            # Note exists, toggle lane
            if lane in found_note["lanes"]:
                found_note["lanes"].remove(lane)
                # If no lanes left, delete note
                if not found_note["lanes"]:
                    self.chart.remove(found_note)
            else:
                found_note["lanes"].append(lane)
                found_note["lanes"].sort()
                found_note["type"] = "jump" if len(found_note["lanes"]) > 1 else "single"
        else:
            # Create new note
            new_note = {
                "time": float(round(snapped_t, 3)),
                "lanes": [lane],
                "type": "single"
            }
            self.chart.append(new_note)
            self.chart.sort(key=lambda x: x["time"])
            
        self.unsaved_changes = True
        
        # Audio feedback on toggle
        try:
            sound_helper.play_hit()
        except:
            pass

    def save_chart(self):
        """Writes edited charts back to the song's JSON file."""
        try:
            with open(self.output_json_path, "w") as f:
                json.dump(self.metadata, f, indent=4)
            self.save_notification_timer = 2.0  # Show notification for 2 seconds
            self.unsaved_changes = False
            print(f"Chart saved successfully to {self.output_json_path}")
        except Exception as e:
            print(f"Error saving chart: {e}")

    def save_new_version(self):
        """Duplicates current chart under a new sequential Custom difficulty index."""
        charts = self.metadata.get("charts", {})
        base_name = "Custom"
        idx = 2
        while f"{base_name} {idx}" in charts:
            idx += 1
        new_key = f"{base_name} {idx}"
        
        import copy
        charts[new_key] = copy.deepcopy(self.chart)
        self.difficulty = new_key
        self.chart = charts[new_key]
        
        self.save_chart()
        self.save_notification_timer = 2.0
        print(f"Chart saved as new version: {new_key}")

    def copy_selection(self):
        if self.selection_start is None or self.selection_end is None:
            return
        t_start = min(self.selection_start, self.selection_end)
        t_end = max(self.selection_start, self.selection_end)
        
        self.clipboard = []
        for note in self.chart:
            if t_start <= note["time"] <= t_end:
                self.clipboard.append({
                    "rel_time": note["time"] - t_start,
                    "lanes": list(note["lanes"]),
                    "type": note["type"]
                })
        print(f"Copied {len(self.clipboard)} notes to clipboard.")

    def paste_selection(self):
        if not self.clipboard:
            return
            
        self.push_undo()
        for clip_note in self.clipboard:
            paste_time = self.editor_time + clip_note["rel_time"]
            snapped_t = self.snap_time(paste_time)
            
            # Don't paste beyond song duration
            if snapped_t > self.song_duration:
                continue
                
            # Check for existing note at this timestamp
            found_note = None
            for note in self.chart:
                if abs(note["time"] - snapped_t) < 0.005:
                    found_note = note
                    break
                    
            if found_note:
                # Merge lanes
                for lane in clip_note["lanes"]:
                    if lane not in found_note["lanes"]:
                        found_note["lanes"].append(lane)
                found_note["lanes"].sort()
                found_note["type"] = "jump" if len(found_note["lanes"]) > 1 else "single"
            else:
                new_note = {
                    "time": float(round(snapped_t, 3)),
                    "lanes": list(clip_note["lanes"]),
                    "type": clip_note["type"]
                }
                self.chart.append(new_note)
                
        self.chart.sort(key=lambda x: x["time"])
        self.unsaved_changes = True
        print("Pasted notes from clipboard.")

    def cut_selection(self):
        if self.selection_start is None or self.selection_end is None:
            return
        self.copy_selection()
        self.delete_selection()

    def delete_selection(self):
        if self.selection_start is None or self.selection_end is None:
            return
        t_start = min(self.selection_start, self.selection_end)
        t_end = max(self.selection_start, self.selection_end)
        
        self.push_undo()
        initial_count = len(self.chart)
        self.chart = [note for note in self.chart if not (t_start <= note["time"] <= t_end)]
        self.metadata["charts"][self.difficulty] = self.chart
        
        deleted_count = initial_count - len(self.chart)
        if deleted_count > 0:
            self.unsaved_changes = True
            print(f"Deleted {deleted_count} notes.")

    def update(self, dt):
        # Draggable Scrollbar logic
        mx, my = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()
        
        # Scrollbar dimensions
        scrollbar_x = self.start_x + self.total_width + 15
        scrollbar_w = 15
        
        if mouse_pressed[0]:  # Left click is held down
            if self.dragging_scrollbar or (scrollbar_x <= mx <= scrollbar_x + scrollbar_w):
                self.dragging_scrollbar = True
                h = 720.0  # SCREEN_HEIGHT is 720
                my_clipped = max(0.0, min(h, float(my)))
                self.editor_time = -2.0 + (my_clipped / h) * (self.song_duration + 2.0)
                if self.playing:
                    self.toggle_play()
            elif self.dragging_hold_note is not None:
                # Update hold note endtime based on drag position
                drag_time = self.editor_time + (self.receptor_y - my) / self.scroll_speed
                snapped = self.snap_time(drag_time)
                min_endtime = self.dragging_hold_note["time"] + self.get_snap_duration()
                self.dragging_hold_note["endtime"] = max(min_endtime, snapped)
                self.unsaved_changes = True
        else:
            self.dragging_scrollbar = False
            if self.dragging_hold_note is not None:
                print(f"Finished dragging hold note. New endtime: {self.dragging_hold_note['endtime']}s")
                self.dragging_hold_note = None
                self.dragging_hold_lane = None

        # Update playback position
        if self.playing:
            if self.editor_time < 0.0:
                self.editor_time += dt * self.playback_speed
                if self.editor_time >= 0.0:
                    # Time to start music!
                    audio_filename = self.metadata.get("filename")
                    if audio_filename:
                        from gameplay import get_or_create_speed_audio
                        speed_filename = get_or_create_speed_audio(audio_filename, self.playback_speed)
                        speed_path = os.path.join(settings.SONGS_DIR, speed_filename)
                        try:
                            pygame.mixer.music.load(speed_path)
                            pygame.mixer.music.play(start=0.0)
                        except Exception as e:
                            print(f"Error starting music after buffer: {e}")
                            pygame.mixer.music.load(self.music_path)
                            pygame.mixer.music.play(start=0.0)
                    self.play_start_time = pygame.time.get_ticks() / 1000.0
                    self.play_start_editor_time = 0.0
            else:
                if self.music_loaded and pygame.mixer.music.get_busy():
                    # Sync precisely with mixer music position (scaled by speed)
                    pos = pygame.mixer.music.get_pos() / 1000.0
                    if pos >= 0:
                        self.editor_time = self.play_start_editor_time + pos * self.playback_speed
                    else:
                        self.editor_time += dt * self.playback_speed
                else:
                    self.editor_time += dt * self.playback_speed
                
            if self.editor_time >= self.song_duration:
                self.editor_time = self.song_duration
                self.playing = False
                pygame.mixer.music.stop()
                if self.recording:
                    self.toggle_record()
        elif self.recording:
            self.toggle_record()

        # Update notification timer
        if self.save_notification_timer > 0:
            self.save_notification_timer = max(0.0, self.save_notification_timer - dt)

    def handle_mouse_click(self, mx, my):
        # 0. Check click on any hold note's end cap to drag
        for note in self.chart:
            if note.get("type") == "hold" and "endtime" in note:
                for lane in note["lanes"]:
                    note_x = self.lane_x[lane]
                    note_y = self.receptor_y - (note["endtime"] - self.editor_time) * self.scroll_speed
                    # Check if click is close (within 25px in X and 20px in Y)
                    if abs(mx - note_x) < 25 and abs(my - note_y) < 20:
                        self.push_undo()
                        self.dragging_hold_note = note
                        self.dragging_hold_lane = lane
                        print(f"Started dragging hold note endtime. Start: {note['time']}s, End: {note['endtime']}s")
                        return

        # 1. Check click in lanes area (to place notes)
        # Y coordinate relative to receptor:
        # y_offset = (note_time - editor_time) * scroll_speed
        # note_y = receptor_y - y_offset
        # So: target_time = editor_time + (receptor_y - my) / scroll_speed
        if self.start_x <= mx <= self.start_x + self.total_width:
            # Determine which lane was clicked
            clicked_lane = -1
            for lane_idx, lx in enumerate(self.lane_x):
                if lx - self.lane_width // 2 <= mx <= lx + self.lane_width // 2:
                    clicked_lane = lane_idx
                    break
                    
            if clicked_lane != -1:
                # Calculate corresponding time in song
                time_offset = (self.receptor_y - my) / self.scroll_speed
                target_time = self.editor_time + time_offset
                if 0 <= target_time <= self.song_duration:
                    self.toggle_note(clicked_lane, target_time)
                    return

        # 2. Check sidebar controls clicks
        sidebar_x = 520
        # Snap change button (next to Grid Snap label)
        if (sidebar_x + 140 <= mx <= sidebar_x + 260) and (275 <= my <= 305):
            self.snap_index = (self.snap_index + 1) % len(self.grid_snaps)
        # Play/Pause button
        elif (sidebar_x <= mx <= sidebar_x + 140) and (330 <= my <= 370):
            self.toggle_play()
        # Save button
        elif (sidebar_x + 160 <= mx <= sidebar_x + 225) and (330 <= my <= 370):
            self.save_chart()
        # Save New Version button
        elif (sidebar_x + 235 <= mx <= sidebar_x + 300) and (330 <= my <= 370):
            self.save_new_version()
        # Clear all notes button
        elif (sidebar_x <= mx <= sidebar_x + 300) and (435 <= my <= 470):
            self.push_undo()
            self.chart.clear()
            self.unsaved_changes = True
        # Undo button
        elif (sidebar_x <= mx <= sidebar_x + 140) and (385 <= my <= 420):
            self.undo()
        # Redo button
        elif (sidebar_x + 160 <= mx <= sidebar_x + 300) and (385 <= my <= 420):
            self.redo()
        # Record button
        elif (sidebar_x <= mx <= sidebar_x + 300) and (485 <= my <= 520):
            self.toggle_record()
        # Playback speed buttons click check (Y=535)
        elif (sidebar_x + 130 <= mx <= sidebar_x + 298) and (535 <= my <= 561):
            s_idx = int((mx - (sidebar_x + 130)) // 28)
            speeds = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0]
            if 0 <= s_idx < len(speeds):
                new_speed = speeds[s_idx]
                if self.playback_speed != new_speed:
                    was_playing = self.playing
                    if was_playing:
                        self.toggle_play()
                    self.playback_speed = new_speed
                    if was_playing:
                        self.toggle_play()
                    print(f"Playback speed changed to {self.playback_speed}x")

    def handle_key_down(self, key):
        # Toggle record mode with R key
        if key == pygame.K_r:
            self.toggle_record()
            return
            
        # Toggle play with SPACE key
        if key == pygame.K_SPACE:
            self.toggle_play()
            return

        # If recording, intercept lane input keys and discard any other shortcuts to prevent interference
        if self.recording:
            lane = self.get_lane_from_key(key)
            if lane != -1:
                press_time = float(round(self.editor_time, 3))
                self.active_record_notes[lane] = press_time
                try:
                    sound_helper.play_hit()
                except:
                    pass
            return

        mods = pygame.key.get_mods()
        ctrl_pressed = (mods & pygame.KMOD_CTRL) or (mods & pygame.KMOD_META)

        # 1. Clipboard and history operations with Ctrl
        if ctrl_pressed:
            if key == pygame.K_c:
                self.copy_selection()
                return
            elif key == pygame.K_v:
                self.paste_selection()
                return
            elif key == pygame.K_x:
                self.cut_selection()
                return
            elif key == pygame.K_z:
                self.undo()
                return
            elif key == pygame.K_y:
                self.redo()
                return

        # 2. Selection marking brackets
        if key == pygame.K_LEFTBRACKET:
            self.selection_start = self.editor_time
            return
        elif key == pygame.K_RIGHTBRACKET:
            self.selection_end = self.editor_time
            return
        elif key in [pygame.K_BACKSPACE, pygame.K_DELETE]:
            if self.selection_start is not None and self.selection_end is not None:
                self.delete_selection()
                return
            else:
                # Delete hovered note
                mx, my = pygame.mouse.get_pos()
                if self.start_x <= mx <= self.start_x + self.total_width:
                    hovered_lane = -1
                    for lane_idx, lx in enumerate(self.lane_x):
                        if lx - self.lane_width // 2 <= mx <= lx + self.lane_width // 2:
                            hovered_lane = lane_idx
                            break
                    if hovered_lane != -1:
                        time_offset = (self.receptor_y - my) / self.scroll_speed
                        target_time = self.editor_time + time_offset
                        
                        closest_note = None
                        closest_diff = 0.25  # 250ms range
                        for note in self.chart:
                            if hovered_lane in note["lanes"]:
                                diff = abs(note["time"] - target_time)
                                if diff < closest_diff:
                                    closest_diff = diff
                                    closest_note = note
                        if closest_note:
                            self.push_undo()
                            closest_note["lanes"].remove(hovered_lane)
                            if not closest_note["lanes"]:
                                self.chart.remove(closest_note)
                            else:
                                closest_note["type"] = "jump" if len(closest_note["lanes"]) > 1 else "single"
                            self.unsaved_changes = True
                            print("Deleted hovered note.")
                            try:
                                sound_helper.play_back()
                            except:
                                pass
                            return

        # 3. Standard Navigation
        if key == pygame.K_s:
            self.save_chart()
        elif key == pygame.K_UP:
            # Scroll forward by 1 grid step
            step = self.get_snap_duration()
            self.editor_time = min(self.song_duration, self.editor_time + step)
            if self.playing:
                self.toggle_play()  # Stop playback to step
        elif key == pygame.K_DOWN:
            # Scroll backward by 1 grid step
            step = self.get_snap_duration()
            self.editor_time = max(-2.0, self.editor_time - step)
            if self.playing:
                self.toggle_play()
        elif key == pygame.K_LEFT:
            # Decrease grid snap
            self.snap_index = (self.snap_index - 1) % len(self.grid_snaps)
        elif key == pygame.K_RIGHT:
            # Increase grid snap
            self.snap_index = (self.snap_index + 1) % len(self.grid_snaps)
        
        # Toggle hold note state on hovered note with H key
        if key == pygame.K_h:
            mx, my = pygame.mouse.get_pos()
            if self.start_x <= mx <= self.start_x + self.total_width:
                hovered_lane = -1
                for lane_idx, lx in enumerate(self.lane_x):
                    if lx - self.lane_width // 2 <= mx <= lx + self.lane_width // 2:
                        hovered_lane = lane_idx
                        break
                        
                if hovered_lane != -1:
                    time_offset = (self.receptor_y - my) / self.scroll_speed
                    target_time = self.editor_time + time_offset
                    
                    closest_note = None
                    closest_diff = 0.25  # 250ms range
                    
                    for note in self.chart:
                        if hovered_lane in note["lanes"]:
                            diff = abs(note["time"] - target_time)
                            if diff < closest_diff:
                                closest_diff = diff
                                closest_note = note
                                
                    if closest_note:
                        self.push_undo()
                        if closest_note.get("type") == "hold":
                            closest_note["type"] = "single"
                            if "endtime" in closest_note:
                                del closest_note["endtime"]
                            print("Toggled hold note back to tap note.")
                        else:
                            end_t = self.snap_time(self.editor_time)
                            if end_t > closest_note["time"]:
                                closest_note["type"] = "hold"
                                closest_note["endtime"] = end_t
                                print(f"Created hold note from {closest_note['time']}s to {end_t}s")
                            else:
                                closest_note["type"] = "hold"
                                closest_note["endtime"] = closest_note["time"] + self.get_snap_duration() * 2
                                print("Created default hold note.")
                        self.unsaved_changes = True
                        try:
                            sound_helper.play_hit()
                        except:
                            pass
            return
        
        # Lanes placing keys: D, F, J, K (keys for left=0, down=1, up=2, right=3)
        lane_keys = {
            pygame.K_d: 0,
            pygame.K_f: 1,
            pygame.K_j: 2,
            pygame.K_k: 3
        }
        
        if key in lane_keys:
            self.toggle_note(lane_keys[key], self.editor_time)

    def handle_key_up(self, key):
        if self.recording:
            lane = self.get_lane_from_key(key)
            if lane != -1 and lane in self.active_record_notes:
                start_time = self.active_record_notes.pop(lane)
                end_time = float(round(self.editor_time, 3))
                duration = end_time - start_time
                
                snapped_start = self.snap_time(start_time)
                snapped_end = self.snap_time(end_time)
                
                self.push_undo()
                
                if duration > 0.25:
                    found = None
                    for note in self.chart:
                        if abs(note["time"] - snapped_start) < 0.005:
                            found = note
                            break
                    if found:
                        found["type"] = "hold"
                        found["endtime"] = max(snapped_start + 0.1, snapped_end)
                        if lane not in found["lanes"]:
                            found["lanes"].append(lane)
                            found["lanes"].sort()
                    else:
                        new_note = {
                            "time": float(round(snapped_start, 3)),
                            "lanes": [lane],
                            "type": "hold",
                            "endtime": float(round(max(snapped_start + 0.1, snapped_end), 3))
                        }
                        self.chart.append(new_note)
                else:
                    found = None
                    for note in self.chart:
                        if abs(note["time"] - snapped_start) < 0.005:
                            found = note
                            break
                    if found:
                        if lane not in found["lanes"]:
                            found["lanes"].append(lane)
                            found["lanes"].sort()
                            found["type"] = "jump" if len(found["lanes"]) > 1 else "single"
                    else:
                        new_note = {
                            "time": float(round(snapped_start, 3)),
                            "lanes": [lane],
                            "type": "single"
                        }
                        self.chart.append(new_note)
                        
                self.chart.sort(key=lambda x: x["time"])
                self.unsaved_changes = True
                print(f"Recorded note on lane {lane} at {snapped_start}s (Hold: {duration > 0.25}s)")

    def handle_scroll(self, button):
        """Scrolls the timeline using the mouse wheel."""
        if self.playing:
            self.toggle_play()
            
        step = self.get_snap_duration()
        if button == 4:  # Scroll Up (forward in time)
            self.editor_time = min(self.song_duration, self.editor_time + step)
        elif button == 5:  # Scroll Down (backward in time)
            self.editor_time = max(-2.0, self.editor_time - step)

    def draw(self, surface):
        w, h = surface.get_size()
        theme = settings.theme
        
        # Background: dark grid for editor
        surface.fill((20, 18, 25))
        
        # 1. Draw lanes container
        pygame.draw.rect(surface, (12, 10, 15), (self.start_x - self.lane_spacing, 0, self.total_width + self.lane_spacing * 2, h))
        for x in self.lane_x:
            pygame.draw.line(surface, (28, 25, 35), (x, 0), (x, h), 1)

        # 1.5 Draw Audio Waveform Envelope inside the lanes background
        if self.wave_envelope:
            timeline_center = self.start_x + self.total_width // 2
            # Step by 4 vertical pixels for performance
            for y in range(0, h, 4):
                t = self.editor_time + (self.receptor_y - y) / self.scroll_speed
                if 0 <= t < self.song_duration:
                    env_idx = int(t * self.wave_fps)
                    if 0 <= env_idx < len(self.wave_envelope):
                        val = self.wave_envelope[env_idx]
                        wave_w = int(val * (self.total_width // 2 - 10))
                        if wave_w > 0:
                            # Symmetrical deep glowing violet waveform bars
                            pygame.draw.line(surface, (45, 25, 75), (timeline_center - wave_w, y), (timeline_center + wave_w, y), 4)

        # Draw selection highlight block (translucent)
        if self.selection_start is not None and self.selection_end is not None:
            y_start = self.receptor_y - (self.selection_start - self.editor_time) * self.scroll_speed
            y_end = self.receptor_y - (self.selection_end - self.editor_time) * self.scroll_speed
            
            rect_y = min(y_start, y_end)
            rect_h = abs(y_start - y_end)
            
            if rect_h > 0:
                # Clip to visible screen area to avoid drawing massive surfaces
                clip_y_start = max(0.0, rect_y)
                clip_y_end = min(float(h), rect_y + rect_h)
                
                clip_h = clip_y_end - clip_y_start
                if clip_h > 0:
                    sel_surf = pygame.Surface((self.total_width + self.lane_spacing * 2, int(clip_h)), pygame.SRCALPHA)
                    # Semi-transparent teal highlight
                    sel_surf.fill((0, 255, 204, 60))
                    surface.blit(sel_surf, (self.start_x - self.lane_spacing, int(clip_y_start)))
            
        # 2. Draw receptor bar (horizontal line across lanes)
        pygame.draw.line(surface, (0, 255, 204), (self.start_x - self.lane_spacing, self.receptor_y), (self.start_x + self.total_width + self.lane_spacing, self.receptor_y), 2)
        
        # 3. Draw Grid Lines (ticks for beats)
        # We find what beat indices are visible on the screen
        # y_offset = (note_time - editor_time) * scroll_speed
        # So note_y is on screen if: 0 <= receptor_y - (note_time - editor_time)*scroll_speed <= h
        # Which means: (receptor_y - h) / scroll_speed <= note_time - editor_time <= receptor_y / scroll_speed
        min_time = self.editor_time - (h - self.receptor_y) / self.scroll_speed
        max_time = self.editor_time + self.receptor_y / self.scroll_speed
        
        # Grid line division (e.g. 16th notes)
        step = self.get_snap_duration()
        
        # Find first visible grid step index
        first_step = int(math.floor(min_time / step))
        last_step = int(math.ceil(max_time / step))
        
        for s in range(first_step, last_step + 1):
            t = s * step
            if 0 <= t <= self.song_duration:
                # Calculate Y coordinate
                y = self.receptor_y - (t - self.editor_time) * self.scroll_speed
                
                # Check color based on note division (quarter, eighth, sixteenth)
                beat_idx = s / (self.grid_snaps[self.snap_index] / 4.0)
                if beat_idx % 1.0 == 0:
                    # Quarter note beat (Red line)
                    color = (150, 40, 40)
                    thickness = 2
                elif (beat_idx * 2) % 1.0 == 0:
                    # Eighth note beat (Blue line)
                    color = (40, 60, 150)
                    thickness = 1
                else:
                    # Sixteenth note beat (Yellow line)
                    color = (120, 120, 40)
                    thickness = 1
                    
                pygame.draw.line(surface, color, (self.start_x - self.lane_spacing, y), (self.start_x + self.total_width + self.lane_spacing, y), thickness)
                
                # Print beat numbers on the side of quarter notes
                if beat_idx % 1.0 == 0:
                    font_small = pygame.font.SysFont("Trebuchet MS", 12)
                    lbl = font_small.render(f"Beat {int(beat_idx) + 1}", True, (100, 100, 110))
                    surface.blit(lbl, (self.start_x - 70, y - 6))

        # 4. Draw Notes
        for note in self.chart:
            t = note["time"]
            y = self.receptor_y - (t - self.editor_time) * self.scroll_speed
            if -50 < y < h + 50:
                for lane in note["lanes"]:
                    note_x = self.lane_x[lane]
                    lane_colors = [(255, 0, 128), (0, 191, 255), (50, 205, 50), (255, 165, 0)]
                    
                    # Draw hold note trail first
                    if note.get("type") == "hold" and "endtime" in note:
                        end_y = self.receptor_y - (note["endtime"] - self.editor_time) * self.scroll_speed
                        trail_h = int(y - end_y)
                        if trail_h > 0:
                            trail_color = lane_colors[lane]
                            trail_surf = pygame.Surface((24, trail_h), pygame.SRCALPHA)
                            trail_surf.fill((trail_color[0], trail_color[1], trail_color[2], 130))
                            surface.blit(trail_surf, (note_x - 12, int(end_y)))
                            pygame.draw.rect(surface, trail_color, (note_x - 15, int(end_y) - 4, 30, 8), border_radius=2)
                            
                    # Draw main tap note head block
                    pygame.draw.rect(surface, lane_colors[lane], (note_x - self.lane_width // 2 + 5, y - 10, self.lane_width - 10, 20), border_radius=4)
                    pygame.draw.rect(surface, (255, 255, 255), (note_x - self.lane_width // 2 + 5, y - 10, self.lane_width - 10, 20), width=1, border_radius=4)

        # Draw Ghost Note Snapped Preview
        if not self.playing:
            mx, my = pygame.mouse.get_pos()
            if self.start_x <= mx <= self.start_x + self.total_width:
                hovered_lane = -1
                for lane_idx, lx in enumerate(self.lane_x):
                    if lx - self.lane_width // 2 <= mx <= lx + self.lane_width // 2:
                        hovered_lane = lane_idx
                        break
                        
                if hovered_lane != -1:
                    time_offset = (self.receptor_y - my) / self.scroll_speed
                    target_time = self.editor_time + time_offset
                    if 0 <= target_time <= self.song_duration:
                        snapped_t = self.snap_time(target_time)
                        y = self.receptor_y - (snapped_t - self.editor_time) * self.scroll_speed
                        
                        lane_colors = [(255, 0, 128), (0, 191, 255), (50, 205, 50), (255, 165, 0)]
                        # Draw ghost transparent block
                        ghost_surf = pygame.Surface((self.lane_width - 10, 20), pygame.SRCALPHA)
                        col = lane_colors[hovered_lane]
                        ghost_surf.fill((col[0], col[1], col[2], 120)) # Alpha 120
                        
                        note_x = self.lane_x[hovered_lane]
                        surface.blit(ghost_surf, (note_x - self.lane_width // 2 + 5, y - 10))
                        pygame.draw.rect(surface, (255, 255, 255, 180), (note_x - self.lane_width // 2 + 5, y - 10, self.lane_width - 10, 20), width=1, border_radius=4)

        # Draw Scrollbar Timeline Track & Note Minimap
        scrollbar_x = self.start_x + self.total_width + 15
        scrollbar_w = 15
        
        # Track background
        pygame.draw.rect(surface, (15, 12, 20), (scrollbar_x, 0, scrollbar_w, h))
        pygame.draw.line(surface, (45, 40, 55), (scrollbar_x, 0), (scrollbar_x, h), 1)
        
        # Note ticks on scrollbar minimap
        for note in self.chart:
            t = note["time"]
            tick_y = (t / self.song_duration) * h
            for lane in note["lanes"]:
                lane_colors = [(255, 0, 128), (0, 191, 255), (50, 205, 50), (255, 165, 0)]
                pygame.draw.line(surface, lane_colors[lane], (scrollbar_x + 2, tick_y), (scrollbar_x + scrollbar_w - 2, tick_y), 1)
                
        # Scrollbar Handle
        y_handle = (self.editor_time / self.song_duration) * h
        pygame.draw.rect(surface, (0, 255, 204), (scrollbar_x, y_handle - 10, scrollbar_w, 20), border_radius=4)
        pygame.draw.rect(surface, (255, 255, 255), (scrollbar_x, y_handle - 10, scrollbar_w, 20), width=1, border_radius=4)

        # 5. Draw Sidebar Panel (Controls, Stats)
        sidebar_x = 520
        pygame.draw.rect(surface, (30, 28, 35), (sidebar_x - 20, 0, SCREEN_WIDTH - sidebar_x + 20, h))
        
        # Load fonts
        title_font = pygame.font.SysFont("Impact", 36)
        label_font = pygame.font.SysFont("Segoe UI", 18, bold=True)
        lbl_val_font = pygame.font.SysFont("Segoe UI", 18)
        help_font = pygame.font.SysFont("Segoe UI", 14)
        
        # Title
        title_surf = title_font.render("CHART EDITOR", True, (0, 255, 204))
        surface.blit(title_surf, (sidebar_x, 40))
        
        # Selection string formatting
        if self.selection_start is not None and self.selection_end is not None:
            sel_str = f"{min(self.selection_start, self.selection_end):.1f}s - {max(self.selection_start, self.selection_end):.1f}s"
        elif self.selection_start is not None:
            sel_str = f"{self.selection_start:.1f}s - [Set End]"
        else:
            sel_str = "None"
            
        clip_str = f"{len(self.clipboard)} notes" if self.clipboard else "Empty"

        # Info Card (7 rows)
        info_rows = [
            ("Song Title:", self.metadata["title"]),
            ("Difficulty:", self.difficulty.upper()),
            ("Tempo BPM:", f"{self.bpm:.2f}"),
            ("Song Time:", f"{self.editor_time:.2f}s / {self.song_duration:.2f}s"),
            ("Notes Count:", str(len(self.chart))),
            ("Selection:", sel_str),
            ("Clipboard:", clip_str)
        ]
        
        for idx, (label, val) in enumerate(info_rows):
            y_pos = 95 + idx * 26
            lbl_s = label_font.render(label, True, (200, 200, 210))
            val_s = lbl_val_font.render(val, True, (255, 255, 255))
            surface.blit(lbl_s, (sidebar_x, y_pos))
            # Shift value right, but make sure it doesn't wrap or clip
            val_x = sidebar_x + 130 if label in ["Song Title:", "Song Time:"] else sidebar_x + 140
            surface.blit(val_s, (val_x, y_pos))
            
        # Grid Snap selector (drawn at Y=280)
        snap_lbl = label_font.render("Grid Snap:", True, (200, 200, 210))
        snap_val = self.grid_snaps[self.snap_index]
        snap_str = "Free" if snap_val == "Free" else f"1/{snap_val} Note"
        snap_val_lbl = lbl_val_font.render(snap_str, True, (0, 255, 204))
        surface.blit(snap_lbl, (sidebar_x, 280))
        pygame.draw.rect(surface, (45, 40, 55), (sidebar_x + 140, 275, 120, 30), border_radius=4)
        surface.blit(snap_val_lbl, (sidebar_x + 150, 280))
        
        # Controls / Action Buttons (drawn at Y=330)
        btn_y = 330
        btn_color = (40, 100, 60) if self.playing else (50, 45, 65)
        pygame.draw.rect(surface, btn_color, (sidebar_x, btn_y, 140, 40), border_radius=5)
        play_lbl = label_font.render("STOP" if self.playing else "PLAY (SPACE)", True, (255, 255, 255))
        surface.blit(play_lbl, (sidebar_x + 15, btn_y + 10))
        
        # Save / Save New buttons
        pygame.draw.rect(surface, (100, 40, 40) if self.unsaved_changes else (50, 45, 65), (sidebar_x + 160, btn_y, 65, 40), border_radius=5)
        save_lbl = help_font.render("SAVE", True, (255, 255, 255))
        surface.blit(save_lbl, (sidebar_x + 160 + (65 - save_lbl.get_width()) // 2, btn_y + 12))
        
        pygame.draw.rect(surface, (45, 40, 70), (sidebar_x + 235, btn_y, 65, 40), border_radius=5)
        new_lbl = help_font.render("+NEW", True, (255, 255, 255))
        surface.blit(new_lbl, (sidebar_x + 235 + (65 - new_lbl.get_width()) // 2, btn_y + 12))
        
        # UNDO and REDO buttons (drawn at Y=385)
        undo_color = (60, 50, 80) if self.undo_stack else (40, 40, 45)
        pygame.draw.rect(surface, undo_color, (sidebar_x, 385, 140, 35), border_radius=4)
        undo_lbl = label_font.render("UNDO (Z)", True, (255, 255, 255) if self.undo_stack else (120, 120, 125))
        surface.blit(undo_lbl, (sidebar_x + 35, 390))

        redo_color = (60, 50, 80) if self.redo_stack else (40, 40, 45)
        pygame.draw.rect(surface, redo_color, (sidebar_x + 160, 385, 140, 35), border_radius=4)
        redo_lbl = label_font.render("REDO (Y)", True, (255, 255, 255) if self.redo_stack else (120, 120, 125))
        surface.blit(redo_lbl, (sidebar_x + 195, 390))

        # Clear Chart Button (drawn at Y=435)
        pygame.draw.rect(surface, (120, 25, 25), (sidebar_x, 435, 300, 35), border_radius=5)
        clear_lbl = label_font.render("CLEAR ALL STEPS IN CHART", True, (255, 255, 255))
        surface.blit(clear_lbl, (sidebar_x + 40, 440))
        
        # Record button (drawn at Y=485)
        if self.recording:
            flash = (pygame.time.get_ticks() // 250) % 2 == 0
            rec_color = (255, 45, 45) if flash else (180, 20, 20)
            rec_text = "🔴 RECORDING LIVE..."
        else:
            rec_color = (130, 30, 30)
            rec_text = "🔴 LIVE RECORD (R)"
            
        pygame.draw.rect(surface, rec_color, (sidebar_x, 485, 300, 35), border_radius=5)
        rec_lbl = label_font.render(rec_text, True, (255, 255, 255))
        surface.blit(rec_lbl, (sidebar_x + 65, 490))
        
        # Playback Speed selector (drawn at Y=535)
        speed_y = 535
        speed_lbl = help_font.render("PLAYBACK SPEED:", True, (200, 200, 210))
        surface.blit(speed_lbl, (sidebar_x, speed_y + 8))
        
        speeds = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0]
        for s_idx, sp in enumerate(speeds):
            sp_rect = pygame.Rect(sidebar_x + 130 + s_idx * 28, speed_y + 4, 25, 22)
            is_active = (self.playback_speed == sp)
            bg_col = (0, 255, 204) if is_active else (45, 40, 55)
            txt_col = (10, 10, 15) if is_active else (220, 220, 230)
            pygame.draw.rect(surface, bg_col, sp_rect, border_radius=3)
            sp_lbl = help_font.render(f"{sp}", True, txt_col)
            surface.blit(sp_lbl, (sp_rect.centerx - sp_lbl.get_width()//2, sp_rect.centery - sp_lbl.get_height()//2))
            
        # Instructions list (drawn at Y=575)
        y_help = 575
        pygame.draw.line(surface, (60, 55, 75), (sidebar_x, y_help), (SCREEN_WIDTH - 40, y_help), 1)
        
        help_title = label_font.render("SHORTCUT GUIDE:", True, (200, 200, 210))
        surface.blit(help_title, (sidebar_x, y_help + 8))
        
        shortcuts = [
            ("SPACE", "Play / Pause timeline"),
            ("R", "Record Mode Play/Pause"),
            ("UP / DOWN", "Step forward / backward"),
            ("LEFT/RIGHT", "Cycle grid snap interval"),
            ("D,F,J,K", "Add note (Guitar: A,S,D,F,G)"),
            ("H", "Hover + H: Toggle Hold Note"),
            ("Ctrl+Z / Y", "Undo / Redo change"),
            ("[  /  ]", "Set selection start / end"),
            ("Ctrl+C / V / X", "Copy / Paste / Cut selection"),
            ("ESC", "Exit editor / Clear selection")
        ]
        
        for idx, (shortcut, desc) in enumerate(shortcuts):
            sc_pos_y = y_help + 30 + idx * 16
            sc_s = help_font.render(shortcut, True, (0, 255, 204))
            desc_s = help_font.render(desc, True, (240, 240, 240))
            
            surface.blit(sc_s, (sidebar_x, sc_pos_y))
            surface.blit(desc_s, (sidebar_x + 105, sc_pos_y))

        # Save success notifications
        if self.save_notification_timer > 0:
            pygame.draw.rect(surface, (40, 120, 60), (sidebar_x, h - 80, 300, 40), border_radius=5)
            notif_lbl = label_font.render("SAVED SUCCESSFULLY!", True, (255, 255, 255))
            surface.blit(notif_lbl, (sidebar_x + 60, h - 70))
            
        elif self.unsaved_changes:
            pygame.draw.rect(surface, (120, 60, 20), (sidebar_x, h - 80, 300, 40), border_radius=5)
            notif_lbl = label_font.render("UNSAVED CHANGES...", True, (255, 255, 255))
            surface.blit(notif_lbl, (sidebar_x + 60, h - 70))

        # 6. Draw glowing screen status banner when recording is live
        if self.recording:
            status_font = pygame.font.SysFont("Impact", 28)
            status_text = status_font.render("🔴 RECORDING LIVE", True, (255, 45, 45))
            
            # Subtitle showing grid snapping status
            snap_val = self.grid_snaps[self.snap_index]
            snap_desc = "Grid Snapped" if snap_val != "Free" else "Free Placement"
            sub_lbl = help_font.render(f"Mode: {snap_desc}", True, (200, 200, 210))
            
            pygame.draw.rect(surface, (10, 8, 15, 220), (10, 10, 230, 60), border_radius=6)
            surface.blit(status_text, (20, 15))
            surface.blit(sub_lbl, (20, 44))
