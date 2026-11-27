"""Qwen2-Audio speech recognition over an OpenAI-compatible vLLM endpoint.

The deployed Qwen2-Audio server accepts multimodal audio messages through
``/v1/chat/completions``. A legacy transcription route is retained as an
explicit opt-in for servers that implement it, but is not the default.
"""
from __future__ import annotations

import asyncio
import base64
import os
from importlib.util import find_spec

from . import audio
from .base import DEFAULT_CAPS, Field
from .llm_openai import _is_loopback, _normalise, _terse


class QwenSTT:
    def __init__(self, cfg: dict):
        self.base_url = _normalise(cfg.get("base_url") or "")
        self.model = str(cfg.get("model") or "Qwen/Qwen2-Audio-7B-Instruct").strip()
        self.protocol = str(cfg.get("protocol") or "chat_completions").strip().lower()
        self.prompt = str(
            cfg.get("prompt") or
            "Transcribe the spoken audio exactly. Return only the transcript."
        ).strip()
        try:
            self.max_tokens = max(1, int(cfg.get("max_tokens") or 256))
        except (TypeError, ValueError):
            self.max_tokens = 256
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
        with httpx.Client(timeout=60.0, trust_env=not _is_loopback(self.base_url)) as cl:
            if self.protocol in {"transcriptions", "audio_transcriptions"}:
                data = {"model": self.model, "response_format": "json"}
                if self.language:
                    data["language"] = self.language
                response = cl.post(
                    f"{self.base_url}/audio/transcriptions",
                    headers=headers,
                    data=data,
                    files={"file": ("speech.wav", wav, "audio/wav")},
                )
            else:
                prompt = self.prompt
                if self.language:
                    prompt += f" The spoken language is {self.language}."
                audio_url = (
                    "data:audio/wav;base64," +
                    base64.b64encode(wav).decode("ascii")
                )
                response = cl.post(
                    f"{self.base_url}/chat/completions",
                    headers={**headers, "Content-Type": "application/json"},
                    json={
                        "model": self.model,
                        "messages": [{
                            "role": "user",
                            "content": [
                                {"type": "audio_url", "audio_url": {"url": audio_url}},
                                {"type": "text", "text": prompt},
                            ],
                        }],
                        "max_tokens": self.max_tokens,
                        "temperature": 0,
                    },
                )
            if response.status_code >= 400:
                raise RuntimeError(f"{response.status_code} {_terse(response.text)}")
            payload = response.json()
        text = payload.get("text") or payload.get("transcript") or ""
        if not text:
            choices = payload.get("choices") or []
            message = choices[0].get("message") if choices else {}
            content = (message or {}).get("content") or ""
            if isinstance(content, list):
                content = " ".join(
                    str(item.get("text") or "")
                    for item in content
                    if isinstance(item, dict)
                )
            text = content
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
                    "protocol": "chat_completions",
                    "api_key_env": "QWEN_AUDIO_API_KEY"}},
    ),
    "needs": (
        Field("base_url", "Address", kind="choice",
              default="http://10.153.60.233:8000/v1"),
        Field("model", "Model", default="Qwen/Qwen2-Audio-7B-Instruct"),
        Field("protocol", "Protocol", default="chat_completions", required=False,
              advanced=True,
              hint="Default: multimodal /chat/completions; legacy transcription route is opt-in"),
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
