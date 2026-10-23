# Runtime artwork

`clock/000.png`–`047.png`: 48 transparent 512×512 frames rendered from the user's
`/Users/cryptoclock/Desktop/CryptoClockPro/Videos/Sample1-Emerald/V5/Production/Technical-Speaker-First.blend`.

The source file was opened read-only by Blender. The camera, lighting and a mild
emerald emission finish were adjusted in memory to make a looping product
turntable for the dark mirror interface. No source blend file was saved.

Regenerate (requires Blender installed at the path below):

```sh
/Applications/Blender.app/Contents/MacOS/Blender --background --python tools/render_clock.py
```

`listen.wav` and `confirm.wav`: small original synthesized UI tones. Regenerate
with `.venv/bin/python tools/generate_cues.py`.

These files are intentional runtime assets, not temporary render caches.

`models/lbfmodel.yaml`: required OpenCV 68-point LBF model; source and checksum
are in `models/SOURCES.md`.

`voice-preview.wav`: short synthesized Thai female greeting generated with
Gemini Live / Leda. Intentional audition asset, not a user recording.
