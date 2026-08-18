"""Generate English VO lines locally via Qwen3-TTS CustomVoice.

Read-only usage of the shared /home/benjamin_graf/qwen3_tts/.venv and
checkpoint — this script does not modify that environment. Run it with that
venv's own python (see campaign/README.md), not this repo's venv.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel

MODEL_PATH = "/home/benjamin_graf/models/qwen3-tts/Qwen3-TTS-12Hz-1.7B-CustomVoice"

LINES = json.loads(sys.argv[1])  # [{"id": ..., "text": ..., "speaker": ..., "instruct": ...}]
OUT_DIR = Path(sys.argv[2])
OUT_DIR.mkdir(parents=True, exist_ok=True)

model = Qwen3TTSModel.from_pretrained(
    MODEL_PATH,
    device_map="cuda:0",
    dtype=torch.bfloat16,
    attn_implementation="sdpa",
    local_files_only=True,
)

for item in LINES:
    wavs, sample_rate = model.generate_custom_voice(
        text=item["text"],
        language="English",
        speaker=item["speaker"],
        instruct=item["instruct"],
    )
    out_path = OUT_DIR / f"{item['id']}.wav"
    sf.write(out_path, wavs[0], sample_rate)
    print(out_path)
