# Guitar Hero & Vocal Microphone Code Backup
# This file contains the decoupled code blocks set aside from Zoomies for future game development.

import math
import random

# ==========================================
# 1. SETTINGS DEFAULTS & CONFIGURATION KEYS
# ==========================================

DEFAULT_SETTINGS_EXTRACT = {
    "game_mode": "Guitar Hero",  # Extracted mode
    "microphone_p1": -1,
    "microphone_p2": -1,
    "microphone_p3": -1,
    "microphone_p4": -1,
    "guitar_keys_p1": {
        "green": [97, 0],
        "red": [115, 0],
        "yellow": [100, 0],
        "blue": [102, 0],
        "orange": [103, 0],
        "strum": [32, 0],
        "whammy": [306, 0],
        "tilt": [308, 0]
    },
    "guitar_keys_p2": {
        "green": [104, 0],
        "red": [106, 0],
        "yellow": [107, 0],
        "blue": [108, 0],
        "orange": [59, 0],
        "strum": [13, 0],
        "whammy": [305, 0],
        "tilt": [307, 0]
    },
    "guitar_keys_p3": {
        "green": [105, 0],        # I
        "red": [111, 0],          # O
        "yellow": [112, 0],       # P
        "blue": [91, 0],          # [
        "orange": [93, 0],          # ]
        "strum": [305, 0],         # RCTRL
        "whammy": [308, 0],         # LALT
        "tilt": [306, 0]
    },
    "guitar_keys_p4": {
        "green": [1073741916, 0],  # Numpad 4
        "red": [1073741917, 0],    # Numpad 5
        "yellow": [1073741918, 0],  # Numpad 6
        "blue": [1073741920, 0],   # Numpad 8
        "orange": [1073741922, 0], # Numpad +
        "strum": [1073741912, 0],  # Numpad Enter
        "whammy": [1073741921, 0], # Numpad PageUp
        "tilt": [1073741913, 0]    # Numpad PageDown
    }
}

# Settings Property Getters/Setters:
"""
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
"""


# ==========================================
# 2. MICROPHONE PITCH TRACKING CLASSES
# ==========================================

class MicrophonePitchTracker:
    def __init__(self, device_id, sample_rate=22050, block_size=1024):
        self.device_id = device_id
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.latest_pitch = 0.0
        self.running = False
        self.stream = None
        
    def start(self):
        try:
            import sounddevice as sd
        except ImportError:
            return
            
        self.running = True
        
        def callback(indata, frames, time, status):
            if not self.running:
                return
            signal = indata[:, 0]
            self.latest_pitch = self.detect_pitch(signal, self.sample_rate)
            
        try:
            dev_idx = None if self.device_id < 0 else self.device_id
            self.stream = sd.InputStream(
                device=dev_idx,
                channels=1,
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                callback=callback
            )
            self.stream.start()
        except Exception as e:
            print(f"Error starting audio stream: {e}")
            self.running = False
            
    def detect_pitch(self, signal, sr):
        import numpy as np
        signal = signal - np.mean(signal)
        rms = np.sqrt(np.mean(signal**2))
        if rms < 0.008:  # Gate out soft noise
            return 0.0
            
        corr = np.correlate(signal, signal, mode='full')
        corr = corr[len(corr)//2:]
        
        d = np.diff(corr)
        start = 0
        for i in range(len(d)):
            if d[i] > 0:
                start = i
                break
        if start == 0:
            return 0.0
            
        peak = start + np.argmax(corr[start:])
        if peak == 0:
            return 0.0
            
        freq = sr / peak
        if 70 <= freq <= 800:  # Human vocal range C2 to G5
            return freq
        return 0.0
        
    def stop(self):
        self.running = False
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except:
                pass
            self.stream = None


# ==========================================
# 3. PITCH ANALYSIS & VISUAL LAYOUT HELPERS
# ==========================================

def analyze_song_vocal_pitch(audio_path):
    import miniaudio
    import numpy as np
    target_notes = []
    try:
        print(f"Pre-analyzing song vocal pitch for: {audio_path}...")
        decoded = miniaudio.decode_file(audio_path)
        sr = decoded.sample_rate
        nchannels = decoded.nchannels
        raw_samples = np.frombuffer(decoded.samples, dtype=np.int16)
        
        # Convert to mono
        if nchannels == 2:
            raw_samples = (raw_samples[0::2].astype(np.float32) + raw_samples[1::2].astype(np.float32)) / 2.0
        else:
            raw_samples = raw_samples.astype(np.float32)
            
        # Normalize
        max_val = np.max(np.abs(raw_samples))
        if max_val > 0:
            raw_samples /= max_val
            
        # Segment every 0.12 seconds for spacing
        chunk_duration = 0.12
        chunk_size = int(chunk_duration * sr)
        total_chunks = len(raw_samples) // chunk_size
        
        for i in range(total_chunks):
            start_idx = i * chunk_size
            end_idx = start_idx + chunk_size
            chunk = raw_samples[start_idx:end_idx]
            
            pitch = detect_pitch_mono(chunk, sr)
            if pitch > 0:
                target_notes.append({
                    "time": i * chunk_duration,
                    "pitch": pitch
                })
        print(f"Pre-analysis complete! Generated {len(target_notes)} target vocal notes.")
    except Exception as e:
        print(f"Error pre-analyzing vocal pitch: {e}")
    return target_notes


def detect_pitch_mono(signal, sr):
    import numpy as np
    signal = signal - np.mean(signal)
    rms = np.sqrt(np.mean(signal**2))
    if rms < 0.005:  # Lower noise gate
        return 0.0
        
    corr = np.correlate(signal, signal, mode='full')
    corr = corr[len(corr)//2:]
    
    d = np.diff(corr)
    start = 0
    for i in range(len(d)):
        if d[i] > 0:
            start = i
            break
    if start == 0:
        return 0.0
        
    peak = start + np.argmax(corr[start:])
    if peak == 0:
        return 0.0
        
    freq = sr / peak
    if 35 <= freq <= 700:
        return freq
    return 0.0


def freq_to_y(freq, min_f=80, max_f=550, height=120):
    if freq <= 0:
        return height
    ratio = (math.log(freq) - math.log(min_f)) / (math.log(max_f) - math.log(min_f))
    ratio = max(0.0, min(1.0, ratio))
    return int(height - ratio * height)
