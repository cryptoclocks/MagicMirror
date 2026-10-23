#!/bin/zsh
# Run this file, rather than pasting its contents into an interactive shell.
smartmirror_dir="${0:A:h}"
if [[ ! -f "$smartmirror_dir/smartmirror.py" || ! -f "$smartmirror_dir/requirements.txt" ]]; then
    print -u2 'Please run the Start SmartMirror.command file from the SmartMirror folder.'
    return 1 2>/dev/null || exit 1
fi
cd "$smartmirror_dir" || exit 1
if [[ ! -x .venv/bin/python ]]; then
    python3 -m venv .venv || exit 1
fi
if ! .venv/bin/python -c 'import cv2, numpy, PySide6, sounddevice, speech_recognition, websockets; assert hasattr(cv2, "face")' >/dev/null 2>&1; then
    .venv/bin/python -m pip uninstall -y opencv-python opencv-python-headless >/dev/null 2>&1
    .venv/bin/python -m pip install -r requirements.txt || exit 1
fi
.venv/bin/python tools/setup_landmarks.py || exit 1
exec .venv/bin/python smartmirror.py "$@"
