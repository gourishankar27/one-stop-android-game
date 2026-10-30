"""Reproduce four short original PCM tones; no recordings or third-party samples."""

import math
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 44_100
# Duration in milliseconds, starting and ending sine frequency in Hz.
TONES = {
    "countdown": (60, 660, 660),
    "accepted": (55, 740, 980),
    "rejected": (85, 300, 220),
    "urgent": (120, 600, 900),
}


def generate(output: Path) -> None:
    """Write mono PCM16 with a smooth envelope, amplitude <=0.3 and no loops."""
    output.mkdir(parents=True, exist_ok=True)
    for name, (duration, start, end) in TONES.items():
        count = SAMPLE_RATE * duration // 1000
        seconds = duration / 1000
        frames = bytearray()
        for index in range(count):
            time = index / SAMPLE_RATE
            phase = 2 * math.pi * (start * time + (end - start) * time * time / (2 * seconds))
            envelope = math.sin(math.pi * index / (count - 1)) ** 2
            frames.extend(struct.pack("<h", round(32767 * 0.3 * envelope * math.sin(phase))))
        path = output / f"feedback_{name}.wav"
        with wave.open(str(path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(SAMPLE_RATE)
            audio.writeframes(frames)
        print(f"{path.name}: {duration}ms mono PCM16 {SAMPLE_RATE}Hz")


if __name__ == "__main__":
    generate(Path(__file__).resolve().parents[1] / "android/app/src/main/res/raw")
