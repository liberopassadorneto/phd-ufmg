#!/bin/bash
export PYTHONNOUSERSITE=1          # ignora pacotes de ~/.local
cd ~/phd-ufmg
source amanda/whisper-transcript/.venv/bin/activate
exec pipeline/bootstrap/with-shared-env python amanda/whisper-transcript/src/main_s3.py "$@"
