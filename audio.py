from __future__ import annotations

import math
from typing import Dict, List, Optional

import numpy as np
import pygame

# A pentatonic scale, so overlapping plinks from several rings stay consonant.
PENTATONIC = [523.25, 587.33, 659.25, 783.99, 880.00, 1046.50, 1174.66]


class Audio:
    """Tiny synthesized sound kit. Every sound is generated with numpy at
    start-up, so there are no asset files. Silently does nothing when no
    audio device is available."""

    SAMPLE_RATE = 22050
    MIN_GAP_MS = 45  # throttle so a burst of absorptions doesn't become noise

    def __init__(self) -> None:
        self.enabled = False
        self.muted = False
        self.sounds: Dict[str, pygame.mixer.Sound] = {}
        self._last_played: Dict[str, int] = {}
        try:
            pygame.mixer.pre_init(self.SAMPLE_RATE, -16, 1, 512)
            pygame.mixer.init()
            pygame.mixer.set_num_channels(24)
            self._channels = pygame.mixer.get_init()[2]
            self._build()
            self.enabled = True
        except (pygame.error, ValueError, TypeError):
            self.enabled = False

    def _to_sound(self, wave: np.ndarray, volume: float) -> pygame.mixer.Sound:
        samples = np.clip(wave * volume, -1.0, 1.0)
        data = (samples * 32767).astype(np.int16)
        if self._channels > 1:
            data = np.repeat(data[:, np.newaxis], self._channels, axis=1)
        return pygame.sndarray.make_sound(np.ascontiguousarray(data))

    def _tone(self, frequency: float, duration: float, decay: float = 18.0, harmonics: float = 0.25) -> np.ndarray:
        t = np.arange(int(self.SAMPLE_RATE * duration)) / self.SAMPLE_RATE
        envelope = np.exp(-t * decay) * np.minimum(1.0, t * 400.0)
        wave = np.sin(2 * math.pi * frequency * t) + harmonics * np.sin(4 * math.pi * frequency * t)
        return wave * envelope

    def _build(self) -> None:
        for index, frequency in enumerate(PENTATONIC):
            self.sounds[f"plink{index}"] = self._to_sound(self._tone(frequency, 0.25), 0.18)

        t = np.arange(int(self.SAMPLE_RATE * 0.35)) / self.SAMPLE_RATE
        sweep = np.sin(2 * math.pi * (180.0 - 260.0 * t) * t) * np.exp(-t * 9.0)
        self.sounds["lost"] = self._to_sound(sweep, 0.35)

        self.sounds["fill"] = self._to_sound(
            self._tone(PENTATONIC[0], 0.9, 4.0) + self._tone(PENTATONIC[2], 0.9, 4.0) + self._tone(PENTATONIC[4], 0.9, 4.0),
            0.15,
        )
        self.sounds["place"] = self._to_sound(self._tone(1400.0, 0.06, 60.0, 0.0), 0.15)
        self.sounds["lift"] = self._to_sound(self._tone(900.0, 0.06, 60.0, 0.0), 0.12)

        notes: List[np.ndarray] = []
        for frequency in (PENTATONIC[0], PENTATONIC[2], PENTATONIC[3], PENTATONIC[5]):
            notes.append(self._tone(frequency, 0.16, 10.0))
        arpeggio = np.concatenate(notes + [self._tone(PENTATONIC[5], 1.0, 3.5) + self._tone(PENTATONIC[3], 1.0, 3.5)])
        self.sounds["win"] = self._to_sound(arpeggio, 0.2)

        t = np.arange(int(self.SAMPLE_RATE * 0.8)) / self.SAMPLE_RATE
        fall = np.sin(2 * math.pi * (330.0 - 160.0 * t) * t) * np.exp(-t * 3.5)
        self.sounds["fail"] = self._to_sound(fall, 0.25)

    def play(self, name: str, throttle: Optional[str] = None) -> None:
        if not self.enabled or self.muted or name not in self.sounds:
            return
        key = throttle or name
        now = pygame.time.get_ticks()
        if now - self._last_played.get(key, -10_000) < self.MIN_GAP_MS:
            return
        self._last_played[key] = now
        self.sounds[name].play()

    def toggle_mute(self) -> None:
        self.muted = not self.muted
