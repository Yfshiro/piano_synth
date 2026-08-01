from pathlib import Path

import librosa
import numpy as np

FILES = [
    ("F#7", 102, Path("data/decoded/key-082.wav")),
    ("G7", 103, Path("data/decoded/key-083.wav")),
    ("G#7", 104, Path("data/decoded/key-084.wav")),
    ("A7", 105, Path("data/decoded/key-085.wav")),
    ("A#7", 106, Path("data/decoded/key-086.wav")),
    ("B7", 107, Path("data/decoded/key-087.wav")),
    ("C8", 108, Path("data/decoded/key-088.wav")),
]

def midi_to_hz(midi: int) -> float:
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)

for name, midi, path in FILES:
    audio, sample_rate = librosa.load(
        path,
        sr=None,
        mono=True,
    )
    audio, _ = librosa.effects.trim(audio, top_db=45)

    expected_hz = midi_to_hz(midi)

    # Skip the initial hammer transient and inspect a short sustained region.
    start = min(int(0.08 * sample_rate), len(audio))
    stop = min(start + int(0.40 * sample_rate), len(audio))
    segment = audio[start:stop]

    if segment.size < 32:
        print(name, "segment too short")
        continue

    window = np.hanning(segment.size)
    spectrum = np.abs(
        np.fft.rfft(segment * window)
    )
    frequencies = np.fft.rfftfreq(
        segment.size,
        d=1.0 / sample_rate,
    )

    lower_hz = expected_hz * 2.0 ** (-100.0 / 1200.0)
    upper_hz = expected_hz * 2.0 ** (+100.0 / 1200.0)

    mask = (
        (frequencies >= lower_hz)
        & (frequencies <= upper_hz)
    )
    indices = np.flatnonzero(mask)

    if indices.size == 0:
        print(name, "no FFT bins in range")
        continue

    local_peak_index = indices[
        np.argmax(spectrum[indices])
    ]
    peak_hz = float(frequencies[local_peak_index])
    cents = 1200.0 * np.log2(
        peak_hz / expected_hz
    )

    print(
        f"{name:3s} expected={expected_hz:9.3f} Hz "
        f"peak={peak_hz:9.3f} Hz "
        f"error={cents:+7.2f} cents "
        f"sr={sample_rate}"
    )