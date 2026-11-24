"""Qwen-compatible speech synthesis over ``/v1/audio/speech``."""
from __future__ import annotations

import asyncio
import os
from importlib.util import find_spec
from typing import AsyncIterator

from . import audio
from .base import DEFAULT_CAPS, Field
from .llm_openai import _is_loopback, _normalise, _terse


class QwenTTS:
    def __init__(self, cfg: dict):
        self.base_url = _normalise(cfg.get("base_url") or "")
        self.model = str(cfg.get("model") or
                         "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice").strip()
        self.voice = str(cfg.get("voice") or "aiden").strip()
        self.api_key = str(cfg.get("api_key") or "").strip()
        if not self.api_key:
            env_name = str(cfg.get("api_key_env") or "QWEN_AUDIO_API_KEY").strip()
            self.api_key = (os.getenv(env_name) or
                            os.getenv("QWEN_INSTRUCT_API_KEY") or "").strip()
        self.caps = dict(DEFAULT_CAPS)
        self.caps["audio_out"] = True

    async def speak(self, text: str, voice: str = "") -> AsyncIterator[bytes]:
        import httpx

        text = (text or "").strip()
        if not text:
            return
        if voice:
            self.voice = voice
        if not self.base_url:
            raise RuntimeError("Qwen TTS has no base URL")
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        headers["Content-Type"] = "application/json"
        payload = {"model": self.model, "input": text, "voice": self.voice,
                   "response_format": "wav"}
        async with httpx.AsyncClient(timeout=60.0,
                                     trust_env=not _is_loopback(self.base_url)) as cl:
            response = await cl.post(f"{self.base_url}/audio/speech",
                                     headers=headers, json=payload)
            if response.status_code >= 400:
                raise RuntimeError(f"{response.status_code} {_terse(response.text)}")
            pcm = await asyncio.to_thread(audio.wav_to_pcm, response.content,
                                          audio.SPEAKER_RATE)
        for piece in audio.chunk(pcm):
            yield piece

    def probe(self) -> tuple[bool, str]:
        if not self.base_url:
            return False, "No Qwen TTS address set."
        return True, f"Qwen TTS {self.model} ({self.voice}) will be checked on first use."


def _make(cfg: dict) -> QwenTTS:
    return QwenTTS(cfg)


PROVIDER = {
    "id": "qwen_tts",
    "kind": "tts",
    "label": "Qwen TTS",
    "hint": "Qwen-compatible speech synthesis endpoint",
    "requires": ("httpx",),
    "catalog": (
        {"id": "qwen", "label": "Qwen3-TTS CustomVoice",
         "note": "remote endpoint · protected key at runtime", "local": None,
         "values": {"base_url": "http://10.153.60.233:8001/v1",
                    "model": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
                    "voice": "aiden",
                    "api_key_env": "QWEN_AUDIO_API_KEY"}},
    ),
    "needs": (
        Field("base_url", "Address", kind="choice",
              default="http://10.153.60.233:8001/v1"),
        Field("model", "Model", default="Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"),
        Field("voice", "Voice", default="aiden"),
        Field("api_key", "API key", kind="secret", required=False,
              hint="Loaded from QWEN_AUDIO_API_KEY when left empty"),
        Field("api_key_env", "Key environment variable", default="QWEN_AUDIO_API_KEY",
              required=False, advanced=True),
    ),
    "caps": {"audio_out": True},
    "factory": _make,
}


def available() -> bool:
    return find_spec("httpx") is not None
