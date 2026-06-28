import numpy as np
import scipy.signal
import scipy.fft
import miniaudio
import os
import json

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
            
        estimated_bpm = round(estimated_bpm, 2)
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
        
        # 6. Generate Chart Beats for 5 Difficulties
        # Establish grid positions: subdivisions of the beat (up to 16th notes = beat / 4)
        subdiv_interval = beat_interval / 4.0 # Sixteenth note grid
        song_duration = len(samples) / sr
        
        # Build grid timestamps
        grid_times = np.arange(best_offset, song_duration - 1.0, subdiv_interval)
        
        # Create map of peak times for efficient lookup
        # Map each grid cell index to the strongest peak that falls inside it
        grid_peaks = {}
        for pt, strength in zip(peak_times, peak_strengths):
            grid_idx = int(round((pt - best_offset) / subdiv_interval))
            if 0 <= grid_idx < len(grid_times):
                if grid_idx not in grid_peaks or strength > grid_peaks[grid_idx]:
                    grid_peaks[grid_idx] = strength
                    
        # Helper to distribute arrows across lanes (Left=0, Down=1, Up=2, Right=3)
        # Prevents selecting the same arrow sequentially too much unless intended
        last_lane = -1
        def get_next_lane(exclude_lane=-1):
            nonlocal last_lane
            lanes = [0, 1, 2, 3]
            if exclude_lane in lanes:
                lanes.remove(exclude_lane)
            # Favor alternating or stepping
            if last_lane in lanes and len(lanes) > 1:
                # Slight bias against repeating the immediate last lane
                weights = [0.35 if l != last_lane else 0.1 for l in lanes]
                weights = [w / sum(weights) for w in weights]
                chosen = np.random.choice(lanes, p=weights)
            else:
                chosen = np.random.choice(lanes)
            last_lane = chosen
            return int(chosen)

        # Generate charts
        charts = {
            "Easy": [],      # 2-beat grid (half-notes). No jumps. Very low density.
            "Medium": [],    # 1-beat grid (quarter-notes). No jumps. Medium density.
            "Hard": [],      # 8th-note grid. Rare jumps. High density.
            "Harder": [],    # 8th & 16th grid. Occasional jumps. Higher complexity.
            "Crazy": []      # 16th-note grid. Frequent jumps. Crossovers & dense streams.
        }
        
        # Dynamic note generation loop
        for idx, t in enumerate(grid_times):
            # Calculate subdiv position in the bar (assuming 4/4 time, 16 sixteenths per bar)
            bar_subdiv = idx % 16
            
            # Check if there is a detected peak near this grid cell
            has_peak = idx in grid_peaks
            peak_strength = grid_peaks.get(idx, 0.0)
            
            # --- EASY ---
            # Only allow notes on major beats (0, 8 in bar_subdiv = beats 1 and 3 of the bar)
            # or every beat (0, 4, 8, 12) if peak is strong
            is_easy_subdiv = (bar_subdiv % 8 == 0) or (has_peak and bar_subdiv % 4 == 0 and peak_strength > threshold_offset * 1.5)
            if is_easy_subdiv and (has_peak or (bar_subdiv % 8 == 0 and np.random.random() < 0.4)):
                charts["Easy"].append({
                    "time": float(round(t, 3)),
                    "lanes": [get_next_lane()],
                    "type": "single"
                })
                
            # --- MEDIUM ---
            # Allow notes on any quarter note beat (0, 4, 8, 12)
            is_med_subdiv = (bar_subdiv % 4 == 0)
            if is_med_subdiv and (has_peak or (bar_subdiv % 8 == 0) or (bar_subdiv % 4 == 0 and np.random.random() < 0.5)):
                charts["Medium"].append({
                    "time": float(round(t, 3)),
                    "lanes": [get_next_lane()],
                    "type": "single"
                })
                
            # --- HARD ---
            # Allow notes on quarter notes and eighth notes (0, 2, 4, 6, 8, 10, 12, 14)
            is_hard_subdiv = (bar_subdiv % 2 == 0)
            if is_hard_subdiv and (has_peak or (bar_subdiv % 4 == 0 and np.random.random() < 0.6)):
                # Jumps: Double notes if peak is exceptionally strong and on a quarter beat
                is_jump = (has_peak and peak_strength > threshold_offset * 2.5 and bar_subdiv % 4 == 0 and np.random.random() < 0.3)
                if is_jump:
                    l1 = get_next_lane()
                    l2 = get_next_lane(exclude_lane=l1)
                    charts["Hard"].append({
                        "time": float(round(t, 3)),
                        "lanes": [l1, l2],
                        "type": "jump"
                    })
                else:
                    charts["Hard"].append({
                        "time": float(round(t, 3)),
                        "lanes": [get_next_lane()],
                        "type": "single"
                    })
                    
            # --- HARDER ---
            # Allow notes on quarter, eighth, and sixteenth notes (all grid indices)
            # High probability on eighth notes, medium probability on sixteenths if peaks exist
            is_harder_subdiv = (bar_subdiv % 2 == 0) or (has_peak and bar_subdiv % 1 == 0 and peak_strength > threshold_offset * 1.2)
            if is_harder_subdiv:
                is_jump = (has_peak and peak_strength > threshold_offset * 2.0 and bar_subdiv % 2 == 0 and np.random.random() < 0.4)
                if is_jump:
                    l1 = get_next_lane()
                    l2 = get_next_lane(exclude_lane=l1)
                    charts["Harder"].append({
                        "time": float(round(t, 3)),
                        "lanes": [l1, l2],
                        "type": "jump"
                    })
                else:
                    charts["Harder"].append({
                        "time": float(round(t, 3)),
                        "lanes": [get_next_lane()],
                        "type": "single"
                    })
                    
            # --- CRAZY ---
            # Plentiful notes. Even if no peak, force notes on beats, and follow peaks aggressively on sixteenths.
            is_crazy_subdiv = (bar_subdiv % 2 == 0) or (has_peak) or (bar_subdiv % 4 == 0)
            if is_crazy_subdiv:
                is_jump = (has_peak and peak_strength > threshold_offset * 1.8 and np.random.random() < 0.5) or (bar_subdiv % 4 == 0 and np.random.random() < 0.2)
                if is_jump:
                    l1 = get_next_lane()
                    l2 = get_next_lane(exclude_lane=l1)
                    charts["Crazy"].append({
                        "time": float(round(t, 3)),
                        "lanes": [l1, l2],
                        "type": "jump"
                    })
                else:
                    # Occasional streams
                    charts["Crazy"].append({
                        "time": float(round(t, 3)),
                        "lanes": [get_next_lane()],
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
        
        with open(output_json_path, "w") as f:
            json.dump(song_metadata, f, indent=4)
        print(f"Successfully saved beatmap to {output_json_path}!")
        return song_metadata
