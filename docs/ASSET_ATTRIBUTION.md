# Asset provenance

## Phase 13 generated feedback

The following mono PCM16 WAVs are generated directly by the repository's
[`scripts/generate_feedback_audio.py`](../scripts/generate_feedback_audio.py),
using only Python standard-library math, struct and wave. They contain simple
sine chirps with a smooth envelope, without a sampled recording, melody, voice,
external artist asset or cloud dependency.

| Resource | Approximate duration | Frequency sweep |
| --- | --- | --- |
| `android/app/src/main/res/raw/feedback_countdown.wav` | 60ms | 660Hz |
| `android/app/src/main/res/raw/feedback_accepted.wav` | 55ms | 740–980Hz |
| `android/app/src/main/res/raw/feedback_rejected.wav` | 85ms | 300–220Hz |
| `android/app/src/main/res/raw/feedback_urgent.wav` | 120ms | 600–900Hz |

All use 44,100Hz, one channel and a source amplitude bounded by 0.3. The Android
player uses a single nonlooping stream at gain 0.18 and releases audio focus
promptly. Actual audibility relative to voices still needs the human device gate.

Reproduce from repository root with `python scripts/generate_feedback_audio.py`.
The generator intentionally replaces only those four named resource files.
Validation records durations, format, peaks and hashes. No third-party sample
license is required for a sample library because none was used. This document
records provenance; it does not select the repository's license, make a new
license grant, dedicate assets to the public domain or assign copyright ownership.

The P/E/S role monograms and text labels use the existing platform typography;
no external icon, artwork or font file is bundled. Role tints are code constants,
with text redundancy in both themes. Existing Android/Compose library notices
are unchanged.

Platform implementation references: [Android View haptics](https://developer.android.com/develop/ui/views/haptics/haptic-feedback)
and [audio focus](https://developer.android.com/media/optimize/audio-focus).
View haptics use system feedback policy without ignoring system settings; audio
is requested only while the activity has a focused, resumed window and stops on
focus loss. Physical sensation, spoken accessibility and group listening remain
separate manual checks.
