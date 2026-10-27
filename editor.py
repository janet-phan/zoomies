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
        self.start_x = 350  # Centered for three-column layout
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
        
        # Inline textbox editing state
        self.active_textbox = None
        self.textbox_buffer = ""

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
        ddr_keys = {
            pygame.K_d: 0,
            pygame.K_f: 1,
            pygame.K_j: 2,
            pygame.K_k: 3
        }
        if key in ddr_keys:
            return ddr_keys[key]
            
        for idx, direction in enumerate(["left", "down", "up", "right"]):
            k_val = settings.keys.get(direction)
            if isinstance(k_val, list):
                if key in k_val:
                    return idx
            elif key == k_val:
                return idx
        return -1

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

    def confirm_and_save(self):
        """Asks whether to overwrite the current difficulty or rename it to save as a new custom chart."""
        import sys
        import subprocess

        if sys.platform == "darwin":
            try:
                ascript = (
                    'tell application "System Events"\n'
                    '    activate\n'
                    f'    set theDialog to display alert "Overwrite Chart?" message "You are about to overwrite the existing \'{self.difficulty}\' chart for this song.\\n\\nDo you want to overwrite it?" as critical buttons {{"Cancel", "Rename", "Overwrite"}} default button "Overwrite" cancel button "Cancel"\n'
                    '    return button returned of theDialog\n'
                    'end tell'
                )
                res = subprocess.run(["osascript", "-e", ascript], capture_output=True, text=True)
                choice = res.stdout.strip()
                if choice == "Overwrite":
                    self.save_chart()
                elif choice == "Rename":
                    rename_script = (
                        'tell application "System Events"\n'
                        '    activate\n'
                        f'    set theResp to display dialog "Enter new custom difficulty name:" default answer "{self.difficulty} Custom" with title "Rename Difficulty"\n'
                        '    return text returned of theResp\n'
                        'end tell'
                    )
                    r_res = subprocess.run(["osascript", "-e", rename_script], capture_output=True, text=True)
                    new_diff = r_res.stdout.strip()
                    if new_diff:
                        charts = self.metadata.get("charts", {})
                        charts[new_diff] = self.chart
                        self.difficulty = new_diff
                        self.save_chart()
                        self.save_notification_timer = 3.0
                return
            except Exception as e:
                print(f"macOS dialog error, falling back to Tkinter: {e}")

        try:
            import tkinter as tk
            from tkinter import messagebox, simpledialog
            
            root = tk.Tk()
            root.withdraw()
            
            title = "Overwrite Chart?"
            msg = f"You are about to overwrite the existing '{self.difficulty}' chart for this song.\n\nDo you want to overwrite it?\n(Select 'No' to rename and save as a custom difficulty instead)"
            
            resp = messagebox.askyesnocancel(title, msg, default=messagebox.YES)
            if resp is True:
                self.save_chart()
            elif resp is False:
                new_diff = simpledialog.askstring("Rename Difficulty", "Enter new custom difficulty name:", initialvalue=self.difficulty + " Custom")
                if new_diff:
                    new_diff = new_diff.strip()
                    if new_diff:
                        charts = self.metadata.get("charts", {})
                        charts[new_diff] = self.chart
                        self.difficulty = new_diff
                        self.save_chart()
                        self.save_notification_timer = 3.0
                        print(f"Chart saved as new custom difficulty: {new_diff}")
            root.destroy()
        except Exception as e:
            print(f"Error showing confirmation dialog: {e}")
            self.save_chart()

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

    def save_as(self):
        """Saves a copy of the current song and all its charts under a new title and filename."""
        import sys
        import subprocess
        import shutil

        new_title = None
        default_val = self.metadata.get("title", "") + " (Copy)"

        if sys.platform == "darwin":
            try:
                ascript = (
                    'tell application "System Events"\n'
                    '    activate\n'
                    f'    set theResp to display dialog "Enter new Song Title:" default answer "{default_val}" with title "Save As New Song"\n'
                    '    return text returned of theResp\n'
                    'end tell'
                )
                res = subprocess.run(["osascript", "-e", ascript], capture_output=True, text=True)
                new_title = res.stdout.strip()
            except Exception as e:
                print(f"macOS dialog error: {e}")

        if not new_title:
            try:
                import tkinter as tk
                from tkinter import simpledialog
                
                root = tk.Tk()
                root.withdraw()
                
                new_title = simpledialog.askstring("Save As New Song", "Enter new Song Title:", initialvalue=default_val)
                root.destroy()
            except Exception as e:
                print(f"Error opening save as dialog: {e}")
                return

        if not new_title:
            return
            
        new_title = new_title.strip()
        if not new_title:
            return
            
        # Clean title to create a safe filename
        safe_name = "".join([c if c.isalnum() or c in " _-" else "" for c in new_title]).strip().replace(" ", "_")
        if not safe_name:
            safe_name = "copy_song"
            
        rel_dir = os.path.dirname(self.song_filename)
        ext = self.song_filename.rsplit(".", 1)[-1]
        
        new_rel_audio = os.path.join(rel_dir, f"{safe_name}.{ext}").replace("\\", "/")
        new_wav_path = os.path.join(settings.SONGS_DIR, new_rel_audio)
        new_json_path = os.path.join(settings.SONGS_DIR, os.path.join(rel_dir, f"{safe_name}.json")).replace("\\", "/")
        
        counter = 1
        while os.path.exists(new_wav_path) or os.path.exists(new_json_path):
            counter += 1
            new_rel_audio = os.path.join(rel_dir, f"{safe_name}_{counter}.{ext}").replace("\\", "/")
            new_wav_path = os.path.join(settings.SONGS_DIR, new_rel_audio)
            new_json_path = os.path.join(settings.SONGS_DIR, os.path.join(rel_dir, f"{safe_name}_{counter}.json")).replace("\\", "/")
            
        try:
            shutil.copy2(self.song_wav_path, new_wav_path)
            
            import copy
            new_meta = copy.deepcopy(self.metadata)
            new_meta["title"] = new_title
            new_meta["filename"] = new_rel_audio
            
            with open(new_json_path, "w") as f:
                json.dump(new_meta, f, indent=4)
                
            self.save_notification_timer = 3.0
            sound_helper.play_select()
            print(f"Song saved as copy: {new_title} at {new_json_path}")
            
        except Exception as e:
            print(f"Error in Save As: {e}")

    def get_chart_stats(self):
        stats = {
            "taps": 0,
            "jumps": 0,
            "hands": 0,
            "holds": 0,
            "mines": 0,
            "rolls": 0,
            "lifts": 0,
            "fakes": 0
        }
        for note in self.chart:
            n_type = note.get("type", "single")
            lanes_count = len(note.get("lanes", []))
            
            if n_type == "mine":
                stats["mines"] += 1
            elif n_type == "roll":
                stats["rolls"] += 1
            elif n_type == "lift":
                stats["lifts"] += 1
            elif n_type == "fake":
                stats["fakes"] += 1
            elif n_type == "hold":
                stats["holds"] += 1
            else:
                if lanes_count == 1:
                    stats["taps"] += 1
                elif lanes_count == 2:
                    stats["jumps"] += 1
                elif lanes_count >= 3:
                    stats["hands"] += 1
        return stats

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
        col2_x = SCREEN_WIDTH - 280
        
        # Commit active textbox if clicked elsewhere
        if getattr(self, "active_textbox", None) is not None:
            clicked_inside = False
            if col2_x <= mx <= col2_x + 250:
                if self.active_textbox == "title" and 70 <= my <= 102:
                    clicked_inside = True
                elif self.active_textbox == "bpm" and 110 <= my <= 142:
                    clicked_inside = True
                elif self.active_textbox == "difficulty" and 150 <= my <= 182:
                    clicked_inside = True
            if not clicked_inside:
                self.commit_textbox()

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

        # 2. Check sidebar controls clicks (X-range is col2_x to col2_x + 250)
        if col2_x <= mx <= col2_x + 250:
            # 2.1 Metadata boxes
            # Song Title Box: Rect(col2_x, 70, 250, 32)
            if 70 <= my <= 102:
                self.active_textbox = "title"
                self.textbox_buffer = self.metadata.get("title", "")
                sound_helper.play_select()
                return
            # BPM Box: Rect(col2_x, 110, 250, 32)
            elif 110 <= my <= 142:
                self.active_textbox = "bpm"
                self.textbox_buffer = f"{self.bpm:.2f}"
                sound_helper.play_select()
                return
            # Difficulty Box: Rect(col2_x, 150, 250, 32)
            elif 150 <= my <= 182:
                self.active_textbox = "difficulty"
                self.textbox_buffer = self.difficulty
                sound_helper.play_select()
                return
            # Save As New Song Button: Rect(col2_x, 190, 250, 32)
            elif 190 <= my <= 222:
                self.save_as()
                return
            
            # 2.2 Editor actions
            y_sec4 = 530
            btn_play = pygame.Rect(col2_x, y_sec4 + 30, 120, 30)
            btn_save = pygame.Rect(col2_x + 130, y_sec4 + 30, 120, 30)
            btn_undo = pygame.Rect(col2_x, y_sec4 + 70, 120, 30)
            btn_redo = pygame.Rect(col2_x + 130, y_sec4 + 70, 120, 30)
            btn_clear = pygame.Rect(col2_x, y_sec4 + 110, 250, 30)
            btn_filler = pygame.Rect(col2_x, y_sec4 + 150, 250, 30)
            btn_export = pygame.Rect(col2_x, y_sec4 + 190, 250, 30)
            
            if btn_play.collidepoint(mx, my):
                self.toggle_play()
                return
            elif btn_save.collidepoint(mx, my):
                self.confirm_and_save()
                return
            elif btn_undo.collidepoint(mx, my):
                self.undo()
                return
            elif btn_redo.collidepoint(mx, my):
                self.redo()
                return
            elif btn_clear.collidepoint(mx, my):
                self.push_undo()
                self.chart.clear()
                self.unsaved_changes = True
                sound_helper.play_select()
                return
            elif btn_filler.collidepoint(mx, my):
                self.generate_filler_beats()
                return
            elif btn_export.collidepoint(mx, my):
                self.export_to_sm()
                return

    def commit_textbox(self):
        if not self.active_textbox:
            return
            
        val = self.textbox_buffer.strip()
        if self.active_textbox == "title":
            if val:
                self.metadata["title"] = val
                self.unsaved_changes = True
                sound_helper.play_select()
        elif self.active_textbox == "bpm":
            try:
                new_bpm = float(val)
                if new_bpm > 10.0:
                    self.bpm = new_bpm
                    self.metadata["bpm"] = new_bpm
                    self.beat_interval = 60.0 / self.bpm
                    self.unsaved_changes = True
                    sound_helper.play_select()
            except ValueError:
                pass
        elif self.active_textbox == "difficulty":
            if val and val != self.difficulty:
                charts = self.metadata.get("charts", {})
                charts[val] = charts.pop(self.difficulty, self.chart)
                self.difficulty = val
                self.unsaved_changes = True
                sound_helper.play_select()
                
        self.active_textbox = None

    def generate_filler_beats(self):
        self.push_undo()
        
        # Sort current chart by time
        self.chart.sort(key=lambda n: n["time"])
        
        # Determine step subdivision based on difficulty
        diff_lower = self.difficulty.lower()
        if "easy" in diff_lower:
            step_div = 1  # 4th notes
        elif "medium" in diff_lower:
            step_div = 2  # 8th notes
        else:
            step_div = 4  # 16th notes
            
        step_duration = self.beat_interval / step_div
        
        # Identify gaps and inject
        injected_count = 0
        gaps = []
        
        # First gap from start of song
        if len(self.chart) > 0:
            if self.chart[0]["time"] > 2.0:
                gaps.append((0.5, self.chart[0]["time"] - 0.5))
        else:
            gaps.append((0.5, self.song_duration - 0.5))
            
        # Middle gaps
        for idx in range(len(self.chart) - 1):
            n1 = self.chart[idx]
            n2 = self.chart[idx + 1]
            t1 = n1.get("endtime", n1["time"])
            t2 = n2["time"]
            if t2 - t1 > 2.0:
                gaps.append((t1 + 0.5, t2 - 0.5))
                
        # Final gap
        if len(self.chart) > 0:
            last_t = self.chart[-1].get("endtime", self.chart[-1]["time"])
            if self.song_duration - last_t > 2.0:
                gaps.append((last_t + 0.5, self.song_duration - 0.5))
                
        # Inject notes into gaps
        lane_cycle = 0
        for g_start, g_end in gaps:
            # Align start time to step grid
            start_aligned = math.ceil(g_start / step_duration) * step_duration
            t = start_aligned
            while t <= g_end:
                too_close = any(abs(n["time"] - t) < 0.010 for n in self.chart)
                if not too_close:
                    lane = lane_cycle % 4
                    self.chart.append({
                        "time": float(round(t, 3)),
                        "lanes": [lane],
                        "type": "tap"
                    })
                    injected_count += 1
                    lane_cycle += 1
                t += step_duration
                
        if injected_count > 0:
            self.chart.sort(key=lambda n: n["time"])
            self.unsaved_changes = True
            sound_helper.play_hit()
            print(f"Injected {injected_count} filler beats into chart!")
        else:
            print("No gaps found to fill!")

    def export_to_sm(self):
        sm_path = self.output_json_path.rsplit(".", 1)[0] + ".sm"
        self.chart.sort(key=lambda n: n["time"])
        
        # Basic SM Header
        lines = [
            f"#TITLE:{self.metadata.get('title', 'Unknown')};",
            f"#ARTIST:{self.metadata.get('artist', 'Unknown')};",
            f"#MUSIC:{self.song_filename};",
            f"#OFFSET:0.000;",
            f"#BPMS:0.000={self.bpm:.3f};",
            f"#NOTES:",
            f"     dance-single:",
            f"     :",
            f"     {self.difficulty}:",
            f"     1:",
            f"     0.000:",
        ]
        
        # Calculate maximum measure
        if len(self.chart) > 0:
            last_t = self.chart[-1].get("endtime", self.chart[-1]["time"])
            max_beat = last_t * (self.bpm / 60.0)
            max_measure = math.ceil(max_beat / 4.0)
        else:
            max_measure = 1
            
        measure_rows = 16
        total_rows = max_measure * measure_rows
        note_grid = [["0", "0", "0", "0"] for _ in range(total_rows)]
        
        for note in self.chart:
            beat = note["time"] * (self.bpm / 60.0)
            row_idx = round(beat * 4.0)
            if 0 <= row_idx < total_rows:
                n_type = "1"
                if note.get("type") == "mine":
                    n_type = "M"
                elif note.get("type") == "hold":
                    n_type = "2"
                    
                for lane in note["lanes"]:
                    note_grid[row_idx][lane] = n_type
                    
                if note.get("type") == "hold" and "endtime" in note:
                    end_beat = note["endtime"] * (self.bpm / 60.0)
                    end_row = round(end_beat * 4.0)
                    if 0 <= end_row < total_rows:
                        for lane in note["lanes"]:
                            note_grid[end_row][lane] = "3"
                            
        for m in range(max_measure):
            for r in range(measure_rows):
                row_str = "".join(note_grid[m * measure_rows + r])
                lines.append(row_str)
            if m < max_measure - 1:
                lines.append(",")
            else:
                lines.append(";")
                
        try:
            with open(sm_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            print(f"Exported SM file to {sm_path}!")
            self.save_notification_timer = 3.0
            sound_helper.play_hit()
        except Exception as e:
            print(f"Error exporting SM: {e}")

    def handle_key_down(self, event):
        key = event.key
        
        # Intercept typing if a textbox is active
        if getattr(self, "active_textbox", None) is not None:
            if key == pygame.K_RETURN:
                self.commit_textbox()
            elif key == pygame.K_ESCAPE:
                self.active_textbox = None
            elif key == pygame.K_BACKSPACE:
                self.textbox_buffer = self.textbox_buffer[:-1]
            else:
                char = event.unicode
                if char and (char.isprintable() or char in " .-_"):
                    self.textbox_buffer += char
            return

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
            self.confirm_and_save()
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
        
        # Toggling other note types: H (Hold), M (Mine), O (Roll), L (Lift), F (Fake)
        if key in [pygame.K_h, pygame.K_m, pygame.K_o, pygame.K_l, pygame.K_f]:
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
                        prev_type = closest_note.get("type", "single")
                        
                        if key == pygame.K_h:
                            if prev_type == "hold":
                                closest_note["type"] = "single"
                                if "endtime" in closest_note:
                                    del closest_note["endtime"]
                                print("Toggled hold note back to tap note.")
                            else:
                                closest_note["type"] = "hold"
                                if "endtime" not in closest_note:
                                    closest_note["endtime"] = closest_note["time"] + self.get_snap_duration() * 2
                                print("Toggled note to hold.")
                        
                        elif key == pygame.K_o:
                            if prev_type == "roll":
                                closest_note["type"] = "single"
                                if "endtime" in closest_note:
                                    del closest_note["endtime"]
                                print("Toggled roll note back to tap note.")
                            else:
                                closest_note["type"] = "roll"
                                if "endtime" not in closest_note:
                                    closest_note["endtime"] = closest_note["time"] + self.get_snap_duration() * 2
                                print("Toggled note to roll.")
                        
                        elif key == pygame.K_m:
                            closest_note["type"] = "single" if prev_type == "mine" else "mine"
                            if "endtime" in closest_note:
                                del closest_note["endtime"]
                            print("Toggled note mine state.")
                                
                        elif key == pygame.K_l:
                            closest_note["type"] = "single" if prev_type == "lift" else "lift"
                            if "endtime" in closest_note:
                                del closest_note["endtime"]
                            print("Toggled note lift state.")
                                
                        elif key == pygame.K_f:
                            closest_note["type"] = "single" if prev_type == "fake" else "fake"
                            if "endtime" in closest_note:
                                del closest_note["endtime"]
                            print("Toggled note fake state.")
                                
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
        
        # Background: ArrowVortex style pure black
        surface.fill((0, 0, 0))
        
        # 1. Draw lanes container
        pygame.draw.rect(surface, (0, 0, 0), (self.start_x - self.lane_spacing, 0, self.total_width + self.lane_spacing * 2, h))
        for x in self.lane_x:
            pygame.draw.line(surface, (45, 45, 45), (x, 0), (x, h), 1)

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
                    # Quarter note beat (White line)
                    color = (220, 220, 220)
                    thickness = 2
                elif (beat_idx * 2) % 1.0 == 0:
                    # Eighth note beat (Blue line)
                    color = (40, 60, 150)
                    thickness = 1
                else:
                    # Sixteenth note beat (Yellow/Grey line)
                    color = (80, 80, 80)
                    thickness = 1
                    
                pygame.draw.line(surface, color, (self.start_x - self.lane_spacing, y), (self.start_x + self.total_width + self.lane_spacing, y), thickness)
                
                # Print beat numbers on the side of quarter notes (StepMania style: 0, 1, 2...)
                if beat_idx % 1.0 == 0:
                    font_small = pygame.font.SysFont("Segoe UI", 12, bold=True)
                    lbl = font_small.render(str(int(beat_idx)), True, (210, 210, 210))
                    surface.blit(lbl, (self.start_x - 30, y - 8))

        # 4. Draw Notes
        for note in self.chart:
            t = note["time"]
            y = self.receptor_y - (t - self.editor_time) * self.scroll_speed
            if -50 < y < h + 50:
                for lane in note["lanes"]:
                    note_x = self.lane_x[lane]
                    lane_colors = [(255, 0, 128), (0, 191, 255), (50, 205, 50), (255, 165, 0)]
                    
                    # Draw trails for holds and rolls first
                    n_type = note.get("type", "single")
                    if n_type == "hold" and "endtime" in note:
                        end_y = self.receptor_y - (note["endtime"] - self.editor_time) * self.scroll_speed
                        trail_h = int(y - end_y)
                        if trail_h > 0:
                            trail_color = lane_colors[lane]
                            trail_surf = pygame.Surface((24, trail_h), pygame.SRCALPHA)
                            trail_surf.fill((trail_color[0], trail_color[1], trail_color[2], 130))
                            surface.blit(trail_surf, (note_x - 12, int(end_y)))
                            pygame.draw.rect(surface, trail_color, (note_x - 15, int(end_y) - 4, 30, 8), border_radius=2)
                    elif n_type == "roll" and "endtime" in note:
                        end_y = self.receptor_y - (note["endtime"] - self.editor_time) * self.scroll_speed
                        trail_h = int(y - end_y)
                        if trail_h > 0:
                            trail_color = (180, 0, 220)
                            trail_surf = pygame.Surface((24, trail_h), pygame.SRCALPHA)
                            for sy in range(0, trail_h, 8):
                                pygame.draw.rect(trail_surf, (trail_color[0], trail_color[1], trail_color[2], 160), (0, sy, 24, 4))
                            surface.blit(trail_surf, (note_x - 12, int(end_y)))
                            pygame.draw.rect(surface, trail_color, (note_x - 15, int(end_y) - 4, 30, 8), border_radius=2)
                            
                    # Draw main note head based on type
                    if n_type == "mine":
                        pygame.draw.circle(surface, (180, 20, 20), (note_x, int(y)), 12)
                        pygame.draw.circle(surface, (40, 40, 40), (note_x, int(y)), 8)
                        pygame.draw.circle(surface, (255, 255, 255), (note_x, int(y)), 12, width=1)
                    elif n_type == "roll":
                        pygame.draw.polygon(surface, (200, 0, 255), [
                            (note_x, y - 12),
                            (note_x - 22, y),
                            (note_x, y + 12),
                            (note_x + 22, y)
                        ])
                        pygame.draw.polygon(surface, (255, 255, 255), [
                            (note_x, y - 12),
                            (note_x - 22, y),
                            (note_x, y + 12),
                            (note_x + 22, y)
                        ], width=1)
                    elif n_type == "lift":
                        pygame.draw.rect(surface, (0, 255, 204), (note_x - self.lane_width // 2 + 5, y - 10, self.lane_width - 10, 20), border_radius=4)
                        pygame.draw.rect(surface, (255, 255, 255), (note_x - self.lane_width // 2 + 5, y - 10, self.lane_width - 10, 20), width=2, border_radius=4)
                        pygame.draw.lines(surface, (255, 255, 255), False, [
                            (note_x - 8, y + 4),
                            (note_x, y - 4),
                            (note_x + 8, y + 4)
                        ], 2)
                    elif n_type == "fake":
                        pygame.draw.rect(surface, (100, 100, 110), (note_x - self.lane_width // 2 + 5, y - 10, self.lane_width - 10, 20), border_radius=4)
                        pygame.draw.rect(surface, (255, 255, 255), (note_x - self.lane_width // 2 + 5, y - 10, self.lane_width - 10, 20), width=1, border_radius=4)
                        fake_font = pygame.font.SysFont("Segoe UI", 11, bold=True)
                        fake_s = fake_font.render("FAKE", True, (240, 240, 240))
                        surface.blit(fake_s, (note_x - fake_s.get_width()//2, y - fake_s.get_height()//2))
                    else:
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

        # 5. Draw Sidebar Panels (Controls, Stats)
        # Load fonts
        label_font = pygame.font.SysFont("Impact" if theme == "DDR-Retro" else "Segoe UI", 18, bold=True)
        lbl_val_font = pygame.font.SysFont("Segoe UI", 16)
        help_font = pygame.font.SysFont("Segoe UI", 14)
        
        # Helper to draw procedural heart decals
        def draw_heart(surf, hx, hy, size=12, color=(255, 45, 45)):
            pygame.draw.circle(surf, color, (hx - size // 4, hy - size // 4), size // 4)
            pygame.draw.circle(surf, color, (hx + size // 4, hy - size // 4), size // 4)
            pygame.draw.polygon(surf, color, [
                (hx - size // 2, hy - size // 8),
                (hx + size // 2, hy - size // 8),
                (hx, hy + size // 2)
            ])
            
        # Draw ArrowVortex Heart Decals around receptors at self.receptor_y
        # Left Decal
        dec_ly = self.receptor_y
        dec_lx = self.start_x - 55
        draw_heart(surface, dec_lx, dec_ly)
        lbl_l1 = help_font.render("1", True, (0, 191, 255))
        lbl_l2 = help_font.render("132", True, (255, 255, 255))
        lbl_l3 = help_font.render("4", True, (255, 215, 0))
        surface.blit(lbl_l1, (dec_lx - 22, dec_ly - 8))
        surface.blit(lbl_l2, (dec_lx - lbl_l2.get_width()//2, dec_ly - 22))
        surface.blit(lbl_l3, (dec_lx - lbl_l3.get_width()//2, dec_ly + 8))
        
        # Right Decal
        dec_rx = self.start_x + self.total_width + 15
        draw_heart(surface, dec_rx, dec_ly)
        lbl_r1 = help_font.render("1", True, (0, 191, 255))
        lbl_r2 = help_font.render("8", True, (255, 255, 255))
        lbl_r3 = help_font.render("4", True, (255, 215, 0))
        lbl_r4 = help_font.render("1/1", True, (0, 230, 100))
        lbl_r5 = help_font.render("Song Start", True, (240, 50, 50))
        surface.blit(lbl_r1, (dec_rx - 16, dec_ly - 8))
        surface.blit(lbl_r2, (dec_rx - lbl_r2.get_width()//2, dec_ly - 22))
        surface.blit(lbl_r3, (dec_rx - lbl_r3.get_width()//2, dec_ly + 8))
        surface.blit(lbl_r4, (dec_rx + 12, dec_ly - 8))
        surface.blit(lbl_r5, (dec_rx + 36, dec_ly - 8))

        # --- LEFT COLUMN: SHORTCUTS GUIDE ---
        col1_x = 25
        yellow_col = (255, 220, 0)
        grey_col = (175, 175, 180)
        white_col = (240, 240, 245)
        
        y_cursor = 40
        sections = [
            ("NAVIGATING", [
                ("Up/Down Key:", "Move One Beat"),
                ("Left/Right Key:", "Change Grid Snap"),
                ("PageUp/PageDown:", "Fast Timeline Scroll"),
                ("Home / End:", "Start / End of Song")
            ]),
            ("WRITING NOTES", [
                ("Click on Lanes:", "Place/Remove standard note"),
                ("H + Mouse Hover:", "Toggle Hold Note state"),
                ("O + Mouse Hover:", "Toggle Roll Note state"),
                ("M / L / F Keys:", "Toggle Mine / Lift / Fake state")
            ]),
            ("AVAILABLE MENUS", [
                ("ESC Key:", "Exit Editor / Selection Menu"),
                ("Click BPM/Diff:", "Prompt to Edit BPM/Difficulty"),
                ("Spacebar:", "Toggle Play / Pause")
            ]),
            ("RECORD MODE", [
                ("R Key:", "Toggle Live Recording Mode"),
                ("D, F, J, K keys:", "Tap Live Steps in lanes")
            ]),
            ("KEYMAPPINGS", [
                ("F11 Key:", "Toggle Fullscreen Window")
            ])
        ]
        
        for section_title, rows in sections:
            hdr_s = label_font.render(section_title, True, yellow_col)
            surface.blit(hdr_s, (col1_x, y_cursor))
            pygame.draw.line(surface, (60, 60, 65), (col1_x, y_cursor + 24), (col1_x + 290, y_cursor + 24), 1)
            y_cursor += 30
            
            for shortcut, desc in rows:
                sc_s = help_font.render(shortcut, True, white_col)
                desc_s = help_font.render(desc, True, grey_col)
                surface.blit(sc_s, (col1_x, y_cursor))
                surface.blit(desc_s, (col1_x + 12, y_cursor + 16))
                y_cursor += 34
            y_cursor += 15

        # --- RIGHT COLUMN: INFO, STATS & METADATA EDITORS ---
        col2_x = SCREEN_WIDTH - 280
        mx, my = pygame.mouse.get_pos()
        
        # 1. EDIT SONG METADATA
        y_sec1 = 40
        hdr_meta = label_font.render("EDIT SONG METADATA", True, yellow_col)
        surface.blit(hdr_meta, (col2_x, y_sec1))
        pygame.draw.line(surface, (60, 60, 65), (col2_x, y_sec1 + 22), (col2_x + 250, y_sec1 + 22), 1)
        
        # Blinking cursor index
        cursor_show = (pygame.time.get_ticks() // 500) % 2
        cursor_char = "|" if cursor_show else ""
        
        # Song Title Box
        title_rect = pygame.Rect(col2_x, y_sec1 + 30, 250, 32)
        title_hover = title_rect.collidepoint(mx, my)
        title_active = (getattr(self, "active_textbox", None) == "title")
        pygame.draw.rect(surface, (30, 25, 45) if title_active else (15, 12, 22), title_rect, border_radius=4)
        border_col = (0, 255, 204) if title_active else ((255, 255, 0) if title_hover else (60, 55, 75))
        pygame.draw.rect(surface, border_col, title_rect, width=2 if title_active else 1, border_radius=4)
        t_text = "TITLE: " + (self.textbox_buffer + cursor_char if title_active else self.metadata.get("title", ""))
        t_lbl = help_font.render(t_text, True, (0, 255, 204) if title_active else white_col)
        surface.blit(t_lbl, (title_rect.x + 8, title_rect.y + 7))
        
        # BPM Box
        bpm_rect = pygame.Rect(col2_x, y_sec1 + 70, 250, 32)
        bpm_hover = bpm_rect.collidepoint(mx, my)
        bpm_active = (getattr(self, "active_textbox", None) == "bpm")
        pygame.draw.rect(surface, (30, 25, 45) if bpm_active else (15, 12, 22), bpm_rect, border_radius=4)
        border_col = (0, 255, 204) if bpm_active else ((255, 255, 0) if bpm_hover else (60, 55, 75))
        pygame.draw.rect(surface, border_col, bpm_rect, width=2 if bpm_active else 1, border_radius=4)
        b_text = "BPM: " + (self.textbox_buffer + cursor_char if bpm_active else f"{self.bpm:.2f}")
        b_lbl = help_font.render(b_text, True, (0, 255, 204) if bpm_active else white_col)
        surface.blit(b_lbl, (bpm_rect.x + 8, bpm_rect.y + 7))
        
        # Difficulty Box
        diff_rect = pygame.Rect(col2_x, y_sec1 + 110, 250, 32)
        diff_hover = diff_rect.collidepoint(mx, my)
        diff_active = (getattr(self, "active_textbox", None) == "difficulty")
        pygame.draw.rect(surface, (30, 25, 45) if diff_active else (15, 12, 22), diff_rect, border_radius=4)
        border_col = (0, 255, 204) if diff_active else ((255, 255, 0) if diff_hover else (60, 55, 75))
        pygame.draw.rect(surface, border_col, diff_rect, width=2 if diff_active else 1, border_radius=4)
        d_text = "DIFF: " + (self.textbox_buffer + cursor_char if diff_active else self.difficulty.upper())
        d_lbl = help_font.render(d_text, True, (0, 255, 204) if diff_active else white_col)
        surface.blit(d_lbl, (diff_rect.x + 8, diff_rect.y + 7))
        
        # Save As Song Copy Button
        saveas_rect = pygame.Rect(col2_x, y_sec1 + 150, 250, 32)
        saveas_hover = saveas_rect.collidepoint(mx, my)
        pygame.draw.rect(surface, (60, 20, 80) if saveas_hover else (45, 15, 60), saveas_rect, border_radius=4)
        pygame.draw.rect(surface, (255, 0, 180) if saveas_hover else (140, 30, 120), saveas_rect, width=1, border_radius=4)
        sa_lbl = help_font.render("SAVE AS NEW SONG...", True, (255, 255, 255))
        surface.blit(sa_lbl, (saveas_rect.centerx - sa_lbl.get_width()//2, saveas_rect.centery - sa_lbl.get_height()//2))
        
        # 2. PLAYBACK INFO
        y_sec2 = 230
        hdr_play = label_font.render("PLAYBACK INFO", True, yellow_col)
        surface.blit(hdr_play, (col2_x, y_sec2))
        pygame.draw.line(surface, (60, 60, 65), (col2_x, y_sec2 + 22), (col2_x + 250, y_sec2 + 22), 1)
        
        curr_beat = self.editor_time * (self.bpm / 60.0)
        snap_val = self.grid_snaps[self.snap_index]
        snap_str = "Free" if snap_val == "Free" else f"1/{snap_val} notes"
        
        info_stats = [
            ("Current beat:", f"{max(0.0, curr_beat):.3f}"),
            ("Current second:", f"{max(0.0, self.editor_time):.6f}"),
            ("Snap grid:", snap_str),
        ]
        
        y_curs = y_sec2 + 30
        for label, val in info_stats:
            lbl_s = help_font.render(label, True, grey_col)
            val_col = yellow_col if label in ["Current second:"] else white_col
            val_s = help_font.render(val, True, val_col)
            surface.blit(lbl_s, (col2_x, y_curs))
            surface.blit(val_s, (col2_x + 110, y_curs))
            y_curs += 20
            
        # 3. STEP COUNTERS
        y_sec3 = 330
        hdr_stats = label_font.render("STEP COUNTERS", True, yellow_col)
        surface.blit(hdr_stats, (col2_x, y_sec3))
        pygame.draw.line(surface, (60, 60, 65), (col2_x, y_sec3 + 22), (col2_x + 250, y_sec3 + 22), 1)
        
        stats = self.get_chart_stats()
        stat_rows = [
            ("Tap Steps:", stats["taps"]),
            ("Jumps:", stats["jumps"]),
            ("Hands:", stats["hands"]),
            ("Holds:", stats["holds"]),
            ("Mines:", stats["mines"]),
            ("Rolls:", stats["rolls"]),
            ("Lifts:", stats["lifts"]),
            ("Fakes:", stats["fakes"]),
        ]
        
        y_curs = y_sec3 + 30
        for label, val in stat_rows:
            lbl_s = help_font.render(label, True, grey_col)
            val_s = help_font.render(str(val), True, white_col)
            surface.blit(lbl_s, (col2_x, y_curs))
            surface.blit(val_s, (col2_x + 110, y_curs))
            y_curs += 18
            
        # 4. EDITOR ACTIONS
        y_sec4 = 530
        hdr_act = label_font.render("EDITOR ACTIONS", True, yellow_col)
        surface.blit(hdr_act, (col2_x, y_sec4))
        pygame.draw.line(surface, (60, 60, 65), (col2_x, y_sec4 + 22), (col2_x + 250, y_sec4 + 22), 1)
        
        # PLAY / PAUSE button
        btn_play = pygame.Rect(col2_x, y_sec4 + 30, 120, 30)
        play_hover = btn_play.collidepoint(mx, my)
        pygame.draw.rect(surface, (30, 60, 45) if play_hover else (20, 40, 30), btn_play, border_radius=4)
        pygame.draw.rect(surface, (0, 255, 120) if play_hover else (0, 180, 80), btn_play, width=1, border_radius=4)
        play_txt = "PAUSE" if self.playing else "PLAY"
        play_s = help_font.render(play_txt, True, (255, 255, 255))
        surface.blit(play_s, (btn_play.centerx - play_s.get_width()//2, btn_play.centery - play_s.get_height()//2))
        
        # SAVE CHART button
        btn_save = pygame.Rect(col2_x + 130, y_sec4 + 30, 120, 30)
        save_hover = btn_save.collidepoint(mx, my)
        pygame.draw.rect(surface, (30, 50, 70) if save_hover else (20, 35, 50), btn_save, border_radius=4)
        pygame.draw.rect(surface, (0, 150, 255) if save_hover else (0, 100, 180), btn_save, width=1, border_radius=4)
        save_s = help_font.render("SAVE", True, (255, 255, 255))
        surface.blit(save_s, (btn_save.centerx - save_s.get_width()//2, btn_save.centery - save_s.get_height()//2))
        
        # UNDO button
        btn_undo = pygame.Rect(col2_x, y_sec4 + 70, 120, 30)
        undo_hover = btn_undo.collidepoint(mx, my)
        pygame.draw.rect(surface, (50, 50, 55) if undo_hover else (35, 35, 40), btn_undo, border_radius=4)
        pygame.draw.rect(surface, (180, 180, 190) if undo_hover else (100, 100, 110), btn_undo, width=1, border_radius=4)
        undo_s = help_font.render("UNDO", True, (255, 255, 255))
        surface.blit(undo_s, (btn_undo.centerx - undo_s.get_width()//2, btn_undo.centery - undo_s.get_height()//2))
        
        # REDO button
        btn_redo = pygame.Rect(col2_x + 130, y_sec4 + 70, 120, 30)
        redo_hover = btn_redo.collidepoint(mx, my)
        pygame.draw.rect(surface, (50, 50, 55) if redo_hover else (35, 35, 40), btn_redo, border_radius=4)
        pygame.draw.rect(surface, (180, 180, 190) if redo_hover else (100, 100, 110), btn_redo, width=1, border_radius=4)
        redo_s = help_font.render("REDO", True, (255, 255, 255))
        surface.blit(redo_s, (btn_redo.centerx - redo_s.get_width()//2, btn_redo.centery - redo_s.get_height()//2))
        
        # CLEAR ALL button
        btn_clear = pygame.Rect(col2_x, y_sec4 + 110, 250, 30)
        clear_hover = btn_clear.collidepoint(mx, my)
        pygame.draw.rect(surface, (100, 30, 30) if clear_hover else (70, 20, 20), btn_clear, border_radius=4)
        pygame.draw.rect(surface, (255, 60, 60) if clear_hover else (180, 40, 40), btn_clear, width=1, border_radius=4)
        clear_s = help_font.render("CLEAR ALL NOTES", True, (255, 255, 255))
        surface.blit(clear_s, (btn_clear.centerx - clear_s.get_width()//2, btn_clear.centery - clear_s.get_height()//2))
        
        # GENERATE FILLER BEATS button
        btn_filler = pygame.Rect(col2_x, y_sec4 + 150, 250, 30)
        filler_hover = btn_filler.collidepoint(mx, my)
        pygame.draw.rect(surface, (0, 80, 100) if filler_hover else (0, 50, 70), btn_filler, border_radius=4)
        pygame.draw.rect(surface, (0, 200, 255) if filler_hover else (0, 140, 180), btn_filler, width=1, border_radius=4)
        filler_s = help_font.render("GENERATE FILLER BEATS", True, (255, 255, 255))
        surface.blit(filler_s, (btn_filler.centerx - filler_s.get_width()//2, btn_filler.centery - filler_s.get_height()//2))
        
        # EXPORT TO SM button
        btn_export = pygame.Rect(col2_x, y_sec4 + 190, 250, 30)
        export_hover = btn_export.collidepoint(mx, my)
        pygame.draw.rect(surface, (80, 60, 0) if export_hover else (50, 40, 0), btn_export, border_radius=4)
        pygame.draw.rect(surface, (255, 200, 0) if export_hover else (180, 140, 0), btn_export, width=1, border_radius=4)
        export_s = help_font.render("EXPORT TO STEPMANIA (.SM)", True, (255, 255, 255))
        surface.blit(export_s, (btn_export.centerx - export_s.get_width()//2, btn_export.centery - export_s.get_height()//2))
            
        # Save success notifications
        if self.save_notification_timer > 0:
            pygame.draw.rect(surface, (40, 120, 60), (col2_x, h - 80, 250, 40), border_radius=5)
            notif_lbl = label_font.render("SAVED SUCCESSFULLY!", True, (255, 255, 255))
            surface.blit(notif_lbl, (col2_x + 20, h - 70))
        elif self.unsaved_changes:
            pygame.draw.rect(surface, (120, 60, 20), (col2_x, h - 80, 250, 40), border_radius=5)
            notif_lbl = label_font.render("UNSAVED CHANGES...", True, (255, 255, 255))
            surface.blit(notif_lbl, (col2_x + 30, h - 70))

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
