import numpy as np
import scipy.signal
import scipy.fft
import miniaudio
import os
import json
import random
from config import settings

class SongAnalyzer:
    def __init__(self):
        pass

    def analyze_song(self, filepath, output_json_path):
        """
        Decodes the song, detects BPM and onsets, and generates 5 difficulty beatmaps.
        Saves the results as a JSON file.
        """
        print(f"Loading {filepath}...")
        # 1. Decode audio using miniaudio to SIGNED16
        decoded = miniaudio.decode_file(filepath)
        sr = decoded.sample_rate
        nchannels = decoded.nchannels
        
        # Convert buffer to numpy array
        raw_samples = np.frombuffer(decoded.samples, dtype=np.int16)
        
        # Reshape to stereo/multi-channel and convert to mono float32
        if nchannels > 1:
            samples = raw_samples.reshape(-1, nchannels).mean(axis=1).astype(np.float32)
        else:
            samples = raw_samples.astype(np.float32)
            
        # Normalize to [-1.0, 1.0]
        max_val = np.max(np.abs(samples))
        if max_val > 0:
            samples /= max_val
            
        print(f"Decoded {len(samples) / sr:.2f}s of audio. Running onset detection...")
        
        # 2. Spectral Flux Onset Detection
        # Frame size = 2048, Hop size = 512 (11.6ms per frame at 44100Hz)
        frame_size = 2048
        hop_size = 512
        
        # Window function
        window = np.hanning(frame_size)
        
        # Calculate number of frames
        num_frames = (len(samples) - frame_size) // hop_size
        if num_frames <= 0:
            raise ValueError("Audio file too short to analyze.")
            
        # Compute spectrogram
        spectrogram = []
        for i in range(num_frames):
            start = i * hop_size
            end = start + frame_size
            frame = samples[start:end] * window
            # Fast Fourier Transform
            fft_res = scipy.fft.rfft(frame)
            magnitude = np.abs(fft_res)
            spectrogram.append(magnitude)
            
        spectrogram = np.array(spectrogram) # Shape: (num_frames, frame_size // 2 + 1)
        
        # Calculate Spectral Flux (positive difference between consecutive frames)
        diff = spectrogram[1:] - spectrogram[:-1]
        spectral_flux = np.sum(np.maximum(0, diff), axis=1) # Length: num_frames - 1
        
        # Pad with 0 at start to match frame indexing
        spectral_flux = np.insert(spectral_flux, 0, 0)
        
        # 3. Adaptive Thresholding for Peak Detection
        # Moving median filter window (approx 250ms on each side = 21 frames)
        median_win = 21
        threshold_offset = np.mean(spectral_flux) * 0.5  # Constant offset
        
        # Compute local median threshold
        local_median = scipy.signal.medfilt(spectral_flux, kernel_size=median_win)
        threshold = local_median + threshold_offset
        
        # Find peaks: SF > threshold and is local maximum
        peaks = []
        for i in range(1, len(spectral_flux) - 1):
            if (spectral_flux[i] > threshold[i] and
                spectral_flux[i] > spectral_flux[i-1] and
                spectral_flux[i] > spectral_flux[i+1]):
                peaks.append(i)
                
        # Convert peak frame indices to timestamps (seconds)
        peak_times = np.array(peaks) * hop_size / sr
        peak_strengths = spectral_flux[peaks]
        
        print(f"Detected {len(peak_times)} initial peaks.")
        
        # 4. BPM Estimation via Autocorrelation
        # Frame rate of spectral flux
        fps = sr / hop_size
        
        # Center the spectral flux envelope
        sf_centered = spectral_flux - np.mean(spectral_flux)
        
        # Calculate autocorrelation
        r = np.correlate(sf_centered, sf_centered, mode='full')
        r = r[len(r)//2:] # Keep positive lags only
        
        # We search for BPM between 70 and 180
        # Lag frame range for BPM: lag = fps * 60 / BPM
        lag_min = int(fps * 60 / 180)
        lag_max = int(fps * 60 / 70)
        
        # Prevent index out of bounds
        lag_max = min(lag_max, len(r) - 1)
        
        if lag_min >= lag_max:
            # Fallback if audio is extremely short
            estimated_bpm = 120.0
        else:
            best_lag = np.argmax(r[lag_min:lag_max]) + lag_min
            estimated_bpm = (fps * 60.0) / best_lag
            
        # Standardize BPM to a reasonable range [80, 160] for gameplay comfort
        while estimated_bpm < 85:
            estimated_bpm *= 2
        while estimated_bpm > 170:
            estimated_bpm /= 2
            
        # Snap to nearest integer if within 1.0 BPM to prevent drift over time
        if abs(estimated_bpm - round(estimated_bpm)) < 1.0:
            estimated_bpm = float(round(estimated_bpm))
        else:
            estimated_bpm = round(estimated_bpm, 1)
            
        print(f"Estimated BPM: {estimated_bpm}")
        
        # 5. Grid Phase Alignment (Finding the first beat offset)
        beat_interval = 60.0 / estimated_bpm
        
        # Test offsets from 0 to beat_interval in 10ms steps
        offsets = np.arange(0, beat_interval, 0.01)
        best_offset = 0
        max_score = -1
        
        for offset in offsets:
            # Score how well this offset aligns with detected peaks
            # Score is high if peak times are close to offset + n * beat_interval
            score = 0
            for pt in peak_times:
                diff_to_grid = (pt - offset) % beat_interval
                dist = min(diff_to_grid, beat_interval - diff_to_grid)
                if dist < 0.040: # Within 40ms of grid line
                    score += 1.0 - (dist / 0.040)
            if score > max_score:
                max_score = score
                best_offset = offset
                
        print(f"Aligned beat grid offset: {best_offset:.3f}s")
        
        # Establish grid positions: subdivisions of the beat (up to 32nd notes = beat / 8)
        subdiv_interval = beat_interval / 8.0 # Thirty-second note grid
        song_duration = len(samples) / sr
        
        # Build grid timestamps
        grid_times = np.arange(best_offset, song_duration - 1.0, subdiv_interval)
        
        # Create map of peak times for efficient lookup
        grid_peaks = {}
        for pt, strength in zip(peak_times, peak_strengths):
            grid_idx = int(round((pt - best_offset) / subdiv_interval))
            if 0 <= grid_idx < len(grid_times):
                if grid_idx not in grid_peaks or strength > grid_peaks[grid_idx]:
                    grid_peaks[grid_idx] = strength
                    
        # 6.1 Chorus / Repeating Section Detection
        phrase_beats = 32
        phrase_len = phrase_beats * beat_interval
        num_phrases = int(song_duration // phrase_len)
        
        phrase_vectors = []
        for i in range(num_phrases):
            t_start = i * phrase_len
            t_end = (i + 1) * phrase_len
            # Build 128-bin onset strength profile for this phrase
            vec = np.zeros(128)
            for pt, strength in zip(peak_times, peak_strengths):
                if t_start <= pt < t_end:
                    pct = (pt - t_start) / phrase_len
                    bin_idx = int(pct * 128)
                    if 0 <= bin_idx < 128:
                        vec[bin_idx] += strength
            phrase_vectors.append(vec)
            
        # Match repeating phrases (similarity threshold > 0.62)
        repeat_map = {} # Maps target phrase index to source phrase index
        for j in range(num_phrases):
            vec_j = phrase_vectors[j]
            norm_j = np.linalg.norm(vec_j)
            if norm_j < 1e-3:
                continue
            for i in range(j):
                vec_i = phrase_vectors[i]
                norm_i = np.linalg.norm(vec_i)
                if norm_i < 1e-3:
                    continue
                sim = np.dot(vec_i, vec_j) / (norm_i * norm_j)
                if sim > 0.62:
                    source_idx = repeat_map.get(i, i)
                    repeat_map[j] = source_idx
                    print(f"Detected chorus/repeat: Phrase {j} is a repeat of Phrase {source_idx} (sim: {sim:.2f})")
                    break
                    
        # Helper to distribute arrows across lanes (Left=0, Down=1, Up=2, Right=3)
        last_lane = -1
        def get_next_lane(exclude_lane=-1):
            nonlocal last_lane
            lanes = [0, 1, 2, 3]
            if exclude_lane in lanes:
                lanes.remove(exclude_lane)
            if last_lane in lanes and len(lanes) > 1:
                weights = [0.35 if l != last_lane else 0.1 for l in lanes]
                weights = [w / sum(weights) for w in weights]
                chosen = np.random.choice(lanes, p=weights)
            else:
                chosen = np.random.choice(lanes)
            last_lane = chosen
            return int(chosen)

        # Generate charts
        charts = {
            "Easy": [],      # 2-beat grid (half-notes). No jumps. Low density.
            "Medium": [],    # 1-beat grid (quarter-notes). No jumps. Medium density.
            "Hard": [],      # 8th-note grid. Rare jumps. High density.
            "Harder": [],    # 8th & 16th grid. Occasional jumps. Higher complexity.
            "Crazy": []      # 16th-note grid. Frequent jumps. Crossovers & dense streams.
        }
        
        # Partition grid times into phrase buckets
        phrase_grid = {}
        for idx, t in enumerate(grid_times):
            p_idx = int(t // phrase_len)
            if p_idx not in phrase_grid:
                phrase_grid[p_idx] = []
            phrase_grid[p_idx].append((idx, t))
            
        max_phrase_idx = max(phrase_grid.keys()) if phrase_grid else 0
        
        # State variables for linear flows, crossovers, streams, and mat/keyboard hardware protection
        last_med_lanes = []
        last_hard_triplet_step = -999
        last_hard_lanes = []
        last_harder_stream_step = -999
        last_harder_stream_len = 0
        last_harder_lanes = []
        last_crazy_stream_step = -999
        last_crazy_stream_len = 0
        last_crazy_lanes = []

        # Phrase loop
        for p_idx in range(max_phrase_idx + 1):
            grid_items = phrase_grid.get(p_idx, [])
            if not grid_items:
                continue
                
            if p_idx in repeat_map:
                # Repeat/Chorus detected! Copy notes from source phrase
                src_idx = repeat_map[p_idx]
                src_start = src_idx * phrase_len
                target_start = p_idx * phrase_len
                shift = target_start - src_start
                
                for diff_name in charts.keys():
                    src_notes = [n for n in charts[diff_name] if src_start <= n["time"] < src_start + phrase_len]
                    for sn in src_notes:
                        copied_note = sn.copy()
                        copied_note["time"] = float(round(sn["time"] + shift, 3))
                        if "endtime" in sn:
                            copied_note["endtime"] = float(round(sn["endtime"] + shift, 3))
                        charts[diff_name].append(copied_note)
            else:
                # Normal dynamic generation
                for idx, t in grid_items:
                    bar_subdiv = idx % 32  # 32 steps per measure (32nd note grid)
                    has_peak = idx in grid_peaks
                    peak_strength = grid_peaks.get(idx, 0.0)
                    
                    # --- EASY ---
                    # Strictly 4th notes (bar_subdiv % 8 == 0) and 2 beats of rest at the end of every 4 measures (128 steps)
                    is_easy_rest = (idx % 128 >= 112)
                    is_easy_subdiv = (bar_subdiv % 8 == 0) and not is_easy_rest
                    
                    if is_easy_subdiv and (has_peak or (bar_subdiv % 8 == 0 and np.random.random() < 0.6)):
                        charts["Easy"].append({
                            "time": float(round(t, 3)),
                            "lanes": [get_next_lane()],
                            "type": "single"
                        })
                        
                    # --- MEDIUM ---
                    # Max density: 8th notes (bar_subdiv % 4 == 0). No 16th notes.
                    is_med_subdiv = (bar_subdiv % 4 == 0) and (has_peak or (bar_subdiv % 4 == 0 and np.random.random() < 0.7))
                    if is_med_subdiv:
                        # 2-key jumps only on major downbeats (beats 1 and 3: bar_subdiv % 16 == 0)
                        is_jump = (bar_subdiv % 16 == 0) and (has_peak and peak_strength > threshold_offset * 2.2 and np.random.random() < 0.3)
                        if is_jump:
                            l1 = get_next_lane()
                            l2 = get_next_lane(exclude_lane=l1)
                            charts["Medium"].append({
                                "time": float(round(t, 3)),
                                "lanes": [l1, l2],
                                "type": "jump"
                            })
                            last_med_lanes = [l1, l2]
                        else:
                            # Linear flows (Left->Down->Up->Right or reverse)
                            # Avoid double taps
                            if last_med_lanes:
                                l_prev = last_med_lanes[-1]
                                chosen = (l_prev + 1) % 4 if np.random.random() < 0.5 else (l_prev - 1) % 4
                            else:
                                chosen = get_next_lane()
                            last_med_lanes = [chosen]
                            charts["Medium"].append({
                                "time": float(round(t, 3)),
                                "lanes": [chosen],
                                "type": "single"
                            })
                            
                    # --- HARD ---
                    # Consistent 8th notes (bar_subdiv % 4 == 0), occasional 16th-note triplets (cooldown 32 steps)
                    is_hard_subdiv = (bar_subdiv % 4 == 0)
                    is_triplet_part = False
                    
                    if idx - last_hard_triplet_step in [2, 4]:
                        is_triplet_part = True
                        
                    if not is_triplet_part and (idx - last_hard_triplet_step >= 32) and (bar_subdiv % 4 == 0) and has_peak and np.random.random() < 0.15:
                        last_hard_triplet_step = idx
                        is_triplet_part = True
                        
                    if is_hard_subdiv or is_triplet_part:
                        # 2-key jumps on any 4th-note beat (bar_subdiv % 8 == 0)
                        is_jump = not is_triplet_part and (bar_subdiv % 8 == 0) and (has_peak and peak_strength > threshold_offset * 2.0 and np.random.random() < 0.25)
                        if is_jump:
                            l1 = get_next_lane()
                            l2 = get_next_lane(exclude_lane=l1)
                            charts["Hard"].append({
                                "time": float(round(t, 3)),
                                "lanes": [l1, l2],
                                "type": "jump"
                            })
                            last_hard_lanes = [l1, l2]
                        else:
                            # Crossovers allowed, alternate lanes to avoid anchors
                            l_prev = last_hard_lanes[-1] if last_hard_lanes else -1
                            chosen = get_next_lane(exclude_lane=l_prev)
                            last_hard_lanes = [chosen]
                            charts["Hard"].append({
                                "time": float(round(t, 3)),
                                "lanes": [chosen],
                                "type": "single"
                            })
                            
                    # --- HARDER ---
                    # Extended 16th streams (up to 8 consecutive notes), 2-key jumps integrated, speed scale
                    speed_mult = getattr(settings, "playback_speed", 1.0)
                    stream_prob = 0.40 * (0.85 if speed_mult > 1.0 else 1.0)
                    
                    is_harder_subdiv = (bar_subdiv % 4 == 0)
                    is_stream_part = False
                    
                    if idx - last_harder_stream_step <= last_harder_stream_len * 2 and (idx - last_harder_stream_step) % 2 == 0:
                        is_stream_part = True
                        
                    if not is_stream_part and (idx - last_harder_stream_step >= 24) and (bar_subdiv % 4 == 0) and has_peak and np.random.random() < stream_prob:
                        last_harder_stream_step = idx
                        last_harder_stream_len = random.randint(4, 8)
                        is_stream_part = True
                        
                    if is_harder_subdiv or is_stream_part:
                        is_jump = (has_peak and peak_strength > threshold_offset * 1.8 and np.random.random() < 0.35)
                        if is_jump:
                            l1 = get_next_lane()
                            l2 = get_next_lane(exclude_lane=l1)
                            charts["Harder"].append({
                                "time": float(round(t, 3)),
                                "lanes": [l1, l2],
                                "type": "jump"
                            })
                            last_harder_lanes = [l1, l2]
                        else:
                            l_prev = last_harder_lanes[-1] if last_harder_lanes else -1
                            chosen = get_next_lane(exclude_lane=l_prev)
                            last_harder_lanes = [chosen]
                            charts["Harder"].append({
                                "time": float(round(t, 3)),
                                "lanes": [chosen],
                                "type": "single"
                            })
                            
                    # --- CRAZY ---
                    # Long 16th streams, occasional 32nd bursts, 3-key & 4-key hardware protection
                    is_crazy_subdiv = (bar_subdiv % 2 == 0) or (has_peak) or (bar_subdiv % 4 == 0)
                    is_burst_part = False
                    
                    if idx - last_crazy_stream_step <= 3:
                        is_burst_part = True
                        
                    if not is_burst_part and (idx - last_crazy_stream_step >= 32) and has_peak and peak_strength > threshold_offset * 2.5 and np.random.random() < 0.15:
                        last_crazy_stream_step = idx
                        is_burst_part = True
                        
                    if is_crazy_subdiv or is_burst_part:
                        device_p1 = getattr(settings, "device_p1", "Keyboard").upper()
                        is_dance_mat = any(mat_name in device_p1 for mat_name in ["MAT", "DANCE MAT", "DANCEMAT"])
                        
                        is_heavy_hit = has_peak and (peak_strength > threshold_offset * 3.0) and (bar_subdiv % 8 == 0)
                        
                        if is_heavy_hit:
                            if is_dance_mat:
                                # Mat: Forbid 3/4-key presses. Substitute with rapid 2-key jumps
                                l1 = get_next_lane()
                                l2 = get_next_lane(exclude_lane=l1)
                                charts["Crazy"].append({
                                    "time": float(round(t, 3)),
                                    "lanes": [l1, l2],
                                    "type": "jump"
                                })
                                last_crazy_lanes = [l1, l2]
                            else:
                                # Keyboard: Allow 3-key or 4-key presses
                                num_keys = 4 if np.random.random() < 0.3 else 3
                                if num_keys == 4:
                                    charts["Crazy"].append({
                                        "time": float(round(t, 3)),
                                        "lanes": [0, 1, 2, 3],
                                        "type": "quad"
                                    })
                                    last_crazy_lanes = [0, 1, 2, 3]
                                else:
                                    lanes_3 = random.sample([0, 1, 2, 3], 3)
                                    charts["Crazy"].append({
                                        "time": float(round(t, 3)),
                                        "lanes": sorted(lanes_3),
                                        "type": "triple"
                                    })
                                    last_crazy_lanes = sorted(lanes_3)
                        else:
                            is_jump = (has_peak and peak_strength > threshold_offset * 1.6 and np.random.random() < 0.45)
                            if is_jump:
                                l1 = get_next_lane()
                                l2 = get_next_lane(exclude_lane=l1)
                                charts["Crazy"].append({
                                    "time": float(round(t, 3)),
                                    "lanes": [l1, l2],
                                    "type": "jump"
                                })
                                last_crazy_lanes = [l1, l2]
                            else:
                                # Technical Rule: Never place > 2 consecutive notes on a single lane (anchors prevention)
                                exclude_lane = -1
                                if len(last_crazy_lanes) >= 2 and last_crazy_lanes[-1] == last_crazy_lanes[-2]:
                                    exclude_lane = last_crazy_lanes[-1]
                                chosen = get_next_lane(exclude_lane=exclude_lane)
                                last_crazy_lanes.append(chosen)
                                if len(last_crazy_lanes) > 4:
                                    last_crazy_lanes.pop(0)
                                    
                                charts["Crazy"].append({
                                    "time": float(round(t, 3)),
                                    "lanes": [chosen],
                                    "type": "single"
                                })
                    
        # Post-process: ensure charts are not empty, sort times, and clean duplicates
        for diff_name in charts:
            # Sort notes by timestamp
            charts[diff_name] = sorted(charts[diff_name], key=lambda x: x["time"])
            
            # Deduplicate by timing window (keep notes at least 80ms apart for safety, except on Crazy)
            min_dist = 0.15 if diff_name in ["Easy", "Medium"] else 0.08
            cleaned_chart = []
            last_t = -999.0
            for note in charts[diff_name]:
                if note["time"] - last_t >= min_dist:
                    cleaned_chart.append(note)
                    last_t = note["time"]
            
            # Convert some sparse single notes to hold notes (intervals > 0.8 seconds, 25% probability)
            final_chart = []
            i = 0
            while i < len(cleaned_chart):
                note = cleaned_chart[i]
                # If there's a big gap to the next note, maybe make it a hold
                if i + 1 < len(cleaned_chart) and cleaned_chart[i+1]["time"] - note["time"] > 0.8 and np.random.random() < 0.25:
                    next_t = cleaned_chart[i+1]["time"]
                    max_end = next_t - 0.2
                    min_end = note["time"] + 0.4
                    if max_end > min_end:
                        end_t = np.random.uniform(min_end, max_end)
                        final_chart.append({
                            "time": note["time"],
                            "endtime": float(round(end_t, 3)),
                            "lanes": note["lanes"],
                            "type": "hold"
                        })
                        i += 1
                        continue
                final_chart.append(note)
                i += 1
            
            charts[diff_name] = final_chart
            print(f"Generated chart '{diff_name}' with {len(charts[diff_name])} notes.")

        # Save song metadata and charts
        song_metadata = {
            "title": os.path.basename(filepath).rsplit('.', 1)[0].replace('_', ' ').replace('-', ' ').title(),
            "filename": os.path.basename(filepath),
            "bpm": estimated_bpm,
            "duration": song_duration,
            "charts": charts
        }
        song_metadata["fnf"] = self.generate_fnf_chart(song_metadata)
        
        with open(output_json_path, "w") as f:
            json.dump(song_metadata, f, indent=4)
        print(f"Successfully saved beatmap to {output_json_path}!")
        return song_metadata

    def generate_fnf_chart(self, song_metadata):
        """Generates FNF call-and-response dual tracks from the Medium beatmap."""
        source_chart = song_metadata["charts"].get("Medium", [])
        if not source_chart:
            source_chart = song_metadata["charts"].get("Easy", [])
            
        bpm = song_metadata["bpm"]
        beat_interval = 60.0 / bpm
        
        # Segment turn flips every 8 beats (2 measures of 4/4)
        segment_duration = 8.0 * beat_interval
        
        player_1_notes = []
        player_2_notes = []
        
        segments = {}
        for note in source_chart:
            seg_idx = int(note["time"] // segment_duration)
            if seg_idx not in segments:
                segments[seg_idx] = []
            segments[seg_idx].append(note)
            
        import random
        for seg_idx, notes in sorted(segments.items()):
            # Chorus/Duet sections occur at 4th and 5th segments of every 8-segment block
            is_duet = (seg_idx % 8 in [4, 5])
            
            if is_duet:
                # Duet: both players get notes to tap simultaneously
                for note in notes:
                    player_1_notes.append(dict(note))
                    player_2_notes.append(dict(note))
            else:
                # Call-and-response alternating
                if seg_idx % 2 == 0:
                    # Player 2 (Opponent) sings the call phrase
                    for note in notes:
                        player_2_notes.append(dict(note))
                else:
                    # Player 1 (Player) responds repeating Player 2's previous phrase pattern
                    prev_notes = segments.get(seg_idx - 1, [])
                    for note in prev_notes:
                        n_copy = dict(note)
                        n_copy["time"] = float(round(n_copy["time"] + segment_duration, 3))
                        if "endtime" in n_copy:
                            n_copy["endtime"] = float(round(n_copy["endtime"] + segment_duration, 3))
                        player_1_notes.append(n_copy)
                        
        return {
            "player_1": sorted(player_1_notes, key=lambda x: x["time"]),
            "player_2": sorted(player_2_notes, key=lambda x: x["time"])
        }
