import pygame
import numpy as np
from config import settings

class SoundHelper:
    def __init__(self):
        self.hit_sound = None
        self.miss_sound = None
        self.select_sound = None
        self.back_sound = None
        self.clap_sound = None
        self.is_initialized = False

    def init_sounds(self):
        """Initializes synthesized sounds in memory."""
        if self.is_initialized:
            return
        
        # Ensure pygame mixer is initialized
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)

        try:
            self.hit_sound = self._generate_tick()
            self.miss_sound = self._generate_buzz()
            self.select_sound = self._generate_chime()
            self.back_sound = self._generate_back_chime()
            self.clap_sound = self._generate_clap()
            self.is_initialized = True
            self.update_volumes()
        except Exception as e:
            print(f"Error generating sounds in-memory: {e}")

    def update_volumes(self):
        if not self.is_initialized:
            return
        vol = settings.sfx_volume
        if self.hit_sound: self.hit_sound.set_volume(vol)
        if self.miss_sound: self.miss_sound.set_volume(vol * 0.5)  # Buzz is naturally annoying, make it quieter
        if self.select_sound: self.select_sound.set_volume(vol * 0.6)
        if self.back_sound: self.back_sound.set_volume(vol * 0.6)
        if self.clap_sound: self.clap_sound.set_volume(vol * 1.0)

    def play_hit(self):
        if self.hit_sound: self.hit_sound.play()

    def play_miss(self):
        if self.miss_sound: self.miss_sound.play()

    def play_select(self):
        if self.select_sound: self.select_sound.play()

    def play_back(self):
        if self.back_sound: self.back_sound.play()

    def play_clap(self):
        if self.clap_sound: self.clap_sound.play()

    def _generate_tick(self):
        sr = 44100
        duration = 0.06  # 60ms click
        t = np.linspace(0, duration, int(sr * duration), False)
        
        # High pitched exponential decay sine wave + noise
        freq = np.linspace(2000, 800, len(t))
        wave = np.sin(2 * np.pi * freq * t) * np.exp(-t * 120)
        noise = np.random.uniform(-1.0, 1.0, len(t)) * np.exp(-t * 180) * 0.3
        
        sig = wave + noise
        sig = sig / np.max(np.abs(sig)) * 0.8
        
        pcm_16 = (sig * 32767).astype(np.int16)
        stereo = np.column_stack((pcm_16, pcm_16))
        return pygame.sndarray.make_sound(stereo)

    def _generate_buzz(self):
        sr = 44100
        duration = 0.15  # 150ms buzz
        t = np.linspace(0, duration, int(sr * duration), False)
        
        # Low pitch saw-like wave with decay
        wave = scipy_sawtooth(2 * np.pi * 90 * t) * np.exp(-t * 15)
        sig = wave / np.max(np.abs(wave)) * 0.4
        
        pcm_16 = (sig * 32767).astype(np.int16)
        stereo = np.column_stack((pcm_16, pcm_16))
        return pygame.sndarray.make_sound(stereo)

    def _generate_chime(self):
        sr = 44100
        duration = 0.12  # 120ms select chime
        t = np.linspace(0, duration, int(sr * duration), False)
        
        # High sine sweep
        freq = np.linspace(880, 1200, len(t))
        wave = np.sin(2 * np.pi * freq * t) * np.exp(-t * 25)
        sig = wave / np.max(np.abs(wave)) * 0.6
        
        pcm_16 = (sig * 32767).astype(np.int16)
        stereo = np.column_stack((pcm_16, pcm_16))
        return pygame.sndarray.make_sound(stereo)

    def _generate_back_chime(self):
        sr = 44100
        duration = 0.12
        t = np.linspace(0, duration, int(sr * duration), False)
        
        # Lower chime sweep downward
        freq = np.linspace(600, 400, len(t))
        wave = np.sin(2 * np.pi * freq * t) * np.exp(-t * 25)
        sig = wave / np.max(np.abs(wave)) * 0.6
        
        pcm_16 = (sig * 32767).astype(np.int16)
        stereo = np.column_stack((pcm_16, pcm_16))
        return pygame.sndarray.make_sound(stereo)

    def _generate_clap(self):
        sr = 44100
        duration = 0.18
        t = np.linspace(0, duration, int(sr * duration), False)
        
        env = np.zeros(len(t))
        for offset in [0.0, 0.012, 0.024]:
            idx_offset = int(offset * sr)
            if idx_offset < len(env):
                decay = np.exp(-t[:len(env)-idx_offset] * 350)
                env[idx_offset:] = np.maximum(env[idx_offset:], decay * 0.6)
                
        main_offset = int(0.036 * sr)
        if main_offset < len(env):
            main_decay = np.exp(-t[:len(env)-main_offset] * 45)
            env[main_offset:] = np.maximum(env[main_offset:], main_decay * 1.0)
            
        noise = np.random.uniform(-1.0, 1.0, len(env))
        shaping = np.sin(2 * np.pi * 1000 * t) * np.cos(2 * np.pi * 350 * t)
        sig = noise * env * (0.5 + 0.5 * shaping)
        
        sig = sig / np.max(np.abs(sig)) * 0.95
        pcm_16 = (sig * 32767).astype(np.int16)
        stereo = np.column_stack((pcm_16, pcm_16))
        return pygame.sndarray.make_sound(stereo)

def scipy_sawtooth(t):
    """Simple sawtooth helper to avoid requiring full scipy.signal if it's slow to load."""
    return 2.0 * (t / (2.0 * np.pi) - np.floor(0.5 + t / (2.0 * np.pi)))

sound_helper = SoundHelper()
