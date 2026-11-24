"""Qwen-compatible speech recognition over ``/v1/audio/transcriptions``."""
from __future__ import annotations

import asyncio
import os
from importlib.util import find_spec

from . import audio
from .base import DEFAULT_CAPS, Field
from .llm_openai import _is_loopback, _normalise, _terse


class QwenSTT:
    def __init__(self, cfg: dict):
        self.base_url = _normalise(cfg.get("base_url") or "")
        self.model = str(cfg.get("model") or "Qwen/Qwen2-Audio-7B-Instruct").strip()
        self.api_key = str(cfg.get("api_key") or "").strip()
        if not self.api_key:
            env_name = str(cfg.get("api_key_env") or "QWEN_AUDIO_API_KEY").strip()
            self.api_key = (os.getenv(env_name) or
                            os.getenv("QWEN_INSTRUCT_API_KEY") or "").strip()
        self.language = str(cfg.get("language") or "").strip()
        self.caps = dict(DEFAULT_CAPS)

    def _transcribe_blocking(self, pcm: bytes, sample_rate: int) -> str:
        import httpx

        if not self.base_url:
            raise RuntimeError("Qwen ASR has no base URL")
        wav = audio.to_wav(pcm, sample_rate)
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        data = {"model": self.model, "response_format": "json"}
        if self.language:
            data["language"] = self.language
        with httpx.Client(timeout=60.0, trust_env=not _is_loopback(self.base_url)) as cl:
            response = cl.post(
                f"{self.base_url}/audio/transcriptions",
                headers=headers,
                data=data,
                files={"file": ("speech.wav", wav, "audio/wav")},
            )
            if response.status_code >= 400:
                raise RuntimeError(f"{response.status_code} {_terse(response.text)}")
            payload = response.json()
        text = payload.get("text") or payload.get("transcript") or ""
        if not isinstance(text, str):
            raise RuntimeError("Qwen ASR response did not contain text")
        return text.strip()

    async def transcribe(self, pcm: bytes, sample_rate: int = audio.MIC_RATE,
                         language: str = "", log=None) -> str:
        if language:
            self.language = language
        if not pcm:
            return ""
        return await asyncio.to_thread(self._transcribe_blocking, pcm, sample_rate)

    async def warmup(self, log=None) -> None:
        return None

    def probe(self) -> tuple[bool, str]:
        if not self.base_url:
            return False, "No Qwen ASR address set."
        return True, f"Qwen ASR {self.model} will be checked on first use."


def _make(cfg: dict) -> QwenSTT:
    return QwenSTT(cfg)


PROVIDER = {
    "id": "qwen_audio",
    "kind": "stt",
    "label": "Qwen Audio",
    "hint": "Qwen-compatible speech recognition endpoint",
    "requires": ("httpx",),
    "catalog": (
        {"id": "qwen", "label": "Qwen2-Audio through vLLM",
         "note": "remote endpoint · protected key at runtime", "local": None,
         "values": {"base_url": "http://10.153.60.233:8000/v1",
                    "model": "Qwen/Qwen2-Audio-7B-Instruct",
                    "api_key_env": "QWEN_AUDIO_API_KEY"}},
    ),
    "needs": (
        Field("base_url", "Address", kind="choice",
              default="http://10.153.60.233:8000/v1"),
        Field("model", "Model", default="Qwen/Qwen2-Audio-7B-Instruct"),
        Field("api_key", "API key", kind="secret", required=False,
              hint="Loaded from QWEN_AUDIO_API_KEY when left empty"),
        Field("api_key_env", "Key environment variable", default="QWEN_AUDIO_API_KEY",
              required=False, advanced=True),
        Field("language", "Language", default="", required=False, advanced=True),
    ),
    "caps": {},
    "factory": _make,
}


def available() -> bool:
    return find_spec("httpx") is not None
