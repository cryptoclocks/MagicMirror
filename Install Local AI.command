#!/bin/zsh
smartmirror_dir="${0:A:h}"
cd "$smartmirror_dir" || exit 1
python3 -m venv .venv-ai || exit 1
.venv-ai/bin/python -m pip install -r requirements-ai.txt || exit 1
.venv-ai/bin/python tools/setup_local_ai.py || exit 1
print 'Local AI ready. Restart AURA and choose Local AI / Metal.'
