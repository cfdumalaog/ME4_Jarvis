"""Select the protected Qwen pipeline without persisting any credential.

The launcher seeds QWEN_TEXT_API_KEY in the child process. This file writes
only the non-secret provider address/model and the Mic -> ASR -> Model -> TTS
selection into Mark-LVII's ignored local configuration.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory.config_manager import save_providers  # noqa: E402


def main() -> None:
    base_url = os.getenv("QWEN_TEXT_BASE_URL", "http://202.92.159.240:8000/v1")
    model = os.getenv("QWEN_TEXT_MODEL", "Qwen/Qwen3.6-27B")
    qwen_id = "openai_compat@qwen"
    stt_id = "qwen_audio@qwen"
    tts_id = "qwen_tts@qwen"
    save_providers(
        mode="pipeline",
        pipeline={"stt": stt_id, "llm": qwen_id, "tts": tts_id},
        sidecar=qwen_id,
        coding=qwen_id,
        creds={qwen_id: {
            "catalog": "qwen",
            "base_url": base_url,
            "model": model,
            "api_key_env": "QWEN_TEXT_API_KEY",
            "tools": True,
            "max_tools": 14,
            "max_tool_chars": 12000,
        },
        stt_id: {
            "catalog": "qwen",
            "base_url": os.getenv("QWEN_ASR_BASE_URL", "http://10.153.60.233:8000/v1"),
            "model": os.getenv("QWEN_ASR_MODEL", "Qwen/Qwen2-Audio-7B-Instruct"),
            "api_key_env": "QWEN_AUDIO_API_KEY",
        },
        tts_id: {
            "catalog": "qwen",
            "base_url": os.getenv("QWEN_TTS_BASE_URL", "http://10.153.60.233:8001/v1"),
            "model": os.getenv("QWEN_TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"),
            "voice": os.getenv("QWEN_TTS_VOICE", "aiden"),
            "api_key_env": "QWEN_AUDIO_API_KEY",
        },
    })
    print(f"Configured protected Qwen pipeline: {model} at {base_url}")


if __name__ == "__main__":
    main()
