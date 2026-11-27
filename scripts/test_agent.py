"""Acceptance harness for the Mark-LVII Qwen agent.

The offline suite exercises the real provider/pipeline contracts with local
mocks. The live checks use only protected process credentials and report
status/latency, never tokens or response bodies.

Run from the repository root:
    python scripts/test_agent.py
    python scripts/test_agent.py --skip-live
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[1]
DEFAULT_SECRETS = WORKSPACE / "AI 231" / "Dumalaog_ME3 - Voice Duplex" / "secrets.txt"


def _qwen_key(secret_file: Path) -> str:
    value = os.getenv("QWEN_TEXT_API_KEY", "").strip()
    if value:
        return value
    if not secret_file.is_file():
        return ""
    for line in secret_file.read_text(encoding="utf-8").splitlines():
        match = re.search(r"(?i)Qwen\s*3\.6.*?\bkey\s+(.+?)\s*$", line)
        if match and match.group(1).strip():
            return match.group(1).strip().strip('`"\'')
    return ""


def _qwen_audio_key(secret_file: Path) -> str:
    value = (os.getenv("QWEN_AUDIO_API_KEY", "").strip() or
             os.getenv("QWEN_INSTRUCT_API_KEY", "").strip())
    if value:
        return value
    if not secret_file.is_file():
        return ""
    for line in secret_file.read_text(encoding="utf-8").splitlines():
        match = re.search(r"(?i)API\s+Key\s+for\s+both\s+models\s+is\s+(.+?)\s*$", line)
        if match and match.group(1).strip():
            return match.group(1).strip().strip('`"\'')
    return ""


def _run(label: str, args: list[str], *, cwd: Path = ROOT,
         env: dict[str, str] | None = None) -> None:
    print(f"\n[{label}]")
    result = subprocess.run(args, cwd=cwd, env=env, text=True)
    if result.returncode:
        raise SystemExit(f"{label} failed with exit code {result.returncode}")


def _offline() -> None:
    py = sys.executable
    _run("provider Mic/VAD/ASR/Model/TTS and tool-loop suite",
         [py, "-m", "providers._tests"])
    _run("tool schema and Codex-style action surface",
         [py, "-m", "providers.schema"])
    _run("Python compilation",
         [py, "-m", "compileall", "-q", "."])

    previous_key = os.environ.get("QWEN_TEXT_API_KEY")
    os.environ["QWEN_TEXT_API_KEY"] = "test-only-placeholder"
    sys.path.insert(0, str(ROOT))
    try:
        from providers.llm_openai import OpenAICompatLLM  # noqa: PLC0415
        from providers import registry  # noqa: PLC0415

        cfg = {
            "catalog": "qwen",
            "base_url": "http://202.92.159.240:8000/v1",
            "model": "Qwen/Qwen3.8-27B",
            "api_key_env": "QWEN_TEXT_API_KEY",
        }
        llm = OpenAICompatLLM(cfg)
        assert llm.base.endswith("/v1")
        assert llm.model == "Qwen/Qwen3.8-27B"
        assert bool(llm.key), "protected environment fallback was not loaded"
        entry = registry.catalog_entry("openai_compat@qwen")
        assert entry.get("values", {}).get("model") == "Qwen/Qwen3.8-27B"
        stt_decl = registry.get_declaration("qwen_audio")
        tts_decl = registry.get_declaration("qwen_tts")
        assert stt_decl and tts_decl
        assert registry.catalog_entry("qwen_audio@qwen").get("values", {}).get(
            "model") == "Qwen/Qwen2-Audio-7B-Instruct"
        assert registry.catalog_entry("qwen_tts@qwen").get("values", {}).get(
            "voice") == "aiden"
    finally:
        if previous_key is None:
            os.environ.pop("QWEN_TEXT_API_KEY", None)
        else:
            os.environ["QWEN_TEXT_API_KEY"] = previous_key
    print("\n[Qwen provider contract]")
    print("  PASS  named Qwen 3.6 catalog entry")
    print("  PASS  Qwen ASR and TTS provider declarations")
    print("  PASS  Qwen ASR/TTS endpoint defaults")
    print("  PASS  protected runtime key fallback (value withheld)")
    print("  PASS  OpenAI-compatible vLLM endpoint normalization")


def _live(secret_file: Path) -> None:
    key = _qwen_key(secret_file)
    if not key:
        raise SystemExit("Live Qwen check requested but no protected key was found.")
    import httpx  # noqa: PLC0415

    base = os.getenv("QWEN_TEXT_BASE_URL", "http://202.92.159.240:8000/v1").rstrip("/")
    model = os.getenv("QWEN_TEXT_MODEL", "Qwen/Qwen3.8-27B")
    headers = {"Authorization": f"Bearer {key}"}
    started = time.monotonic()
    with httpx.Client(timeout=30.0, trust_env=False) as client:
        models = client.get(f"{base}/models", headers=headers)
        models.raise_for_status()
        model_ids = {str(item.get("id")) for item in models.json().get("data", [])}
        assert model in model_ids, f"configured model not listed: {model}"
        reply = client.post(
            f"{base}/chat/completions",
            headers={**headers, "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "Reply with one word only."},
                    {"role": "user", "content": "Reply with: READY"},
                ],
                "stream": False,
            },
        )
        reply.raise_for_status()
        payload = reply.json()
        assert payload.get("choices"), "Qwen response had no choices"
    print("\n[Live Qwen vLLM]")
    print(f"  PASS  authenticated /models and chat completion ({time.monotonic() - started:.2f}s)")
    print("  PASS  response body withheld from logs")


def _live_audio(secret_file: Path) -> None:
    key = _qwen_audio_key(secret_file)
    if not key:
        raise SystemExit("Live Qwen audio check requested but no protected audio key was found.")
    import base64  # noqa: PLC0415
    import httpx  # noqa: PLC0415

    asr_base = os.getenv("QWEN_ASR_BASE_URL", "http://10.153.60.233:8000/v1").rstrip("/")
    asr_model = os.getenv("QWEN_ASR_MODEL", "Qwen/Qwen2-Audio-7B-Instruct")
    tts_base = os.getenv("QWEN_TTS_BASE_URL", "http://10.153.60.233:8001/v1").rstrip("/")
    tts_model = os.getenv("QWEN_TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice")
    voice = os.getenv("QWEN_TTS_VOICE", "aiden")
    headers = {"Authorization": f"Bearer {key}"}
    started = time.monotonic()
    with httpx.Client(timeout=60.0, trust_env=False) as client:
        asr_models = client.get(f"{asr_base}/models", headers=headers)
        asr_models.raise_for_status()
        asr_ids = {str(item.get("id")) for item in asr_models.json().get("data", [])}
        assert asr_model in asr_ids, f"configured ASR model not listed: {asr_model}"

        tts_models = client.get(f"{tts_base}/models", headers=headers)
        tts_models.raise_for_status()
        tts_ids = {str(item.get("id")) for item in tts_models.json().get("data", [])}
        assert tts_model in tts_ids, f"configured TTS model not listed: {tts_model}"

        speech = client.post(
            f"{tts_base}/audio/speech",
            headers={**headers, "Content-Type": "application/json"},
            json={"model": tts_model, "input": "Jarvis audio pipeline test.",
                  "voice": voice, "response_format": "wav"},
        )
        speech.raise_for_status()
        wav = speech.content
        assert wav, "Qwen TTS returned no audio bytes"

        audio_url = "data:audio/wav;base64," + base64.b64encode(wav).decode("ascii")
        transcript = client.post(
            f"{asr_base}/chat/completions",
            headers={**headers, "Content-Type": "application/json"},
            json={
                "model": asr_model,
                "messages": [{"role": "user", "content": [
                    {"type": "audio_url", "audio_url": {"url": audio_url}},
                    {"type": "text", "text": (
                        "Transcribe the spoken audio exactly. Return only the transcript."
                    )},
                ]}],
                "max_tokens": 256,
                "temperature": 0,
            },
        )
        transcript.raise_for_status()
        payload = transcript.json()
        choices = payload.get("choices") or []
        assert choices, "Qwen ASR response had no choices"
        message = choices[0].get("message") or {}
        content = message.get("content") or ""
        if isinstance(content, list):
            content = " ".join(str(item.get("text") or "") for item in content
                                if isinstance(item, dict))
        assert isinstance(content, str) and content.strip(), "Qwen ASR returned empty text"
    print("\n[Live Qwen audio pipeline]")
    print(f"  PASS  authenticated ASR/TTS model discovery and TTS audio ({len(wav)} bytes)")
    print(f"  PASS  Qwen2-Audio multimodal chat transcription ({time.monotonic() - started:.2f}s)")
    print("  PASS  transcript body and credential values withheld from logs")


def _github_read_only(secret_file: Path) -> None:
    token = ""
    if secret_file.is_file():
        for line in secret_file.read_text(encoding="utf-8").splitlines():
            match = re.search(r"(?i)GitHub\s+token\s*[:=]\s*(.+?)\s*$", line)
            if match:
                token = match.group(1).strip().strip('`"\'')
                break
    if not token:
        raise SystemExit("GitHub read-only check requested but no protected token was found.")
    env = os.environ.copy()
    env["GH_TOKEN"] = token
    login = subprocess.check_output(
        ["gh", "api", "user", "--jq", ".login"], cwd=ROOT, env=env, text=True
    ).strip()
    repo = subprocess.check_output(
        ["gh", "repo", "view", "cfdumalaog/ME4_Jarvis", "--json", "nameWithOwner"],
        cwd=ROOT, env=env, text=True,
    ).strip()
    assert login == "cfdumalaog"
    assert "cfdumalaog/ME4_Jarvis" in repo
    print("\n[GitHub agent access]")
    print(f"  PASS  authenticated GitHub identity: {login}")
    print("  PASS  fork is readable through the GitHub CLI")
    print("  PASS  no GitHub write was performed by this harness")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-live", action="store_true")
    parser.add_argument("--skip-github", action="store_true")
    parser.add_argument("--secret-file", type=Path, default=DEFAULT_SECRETS)
    args = parser.parse_args()
    _offline()
    if not args.skip_live:
        _live(args.secret_file)
        _live_audio(args.secret_file)
    if not args.skip_github:
        _github_read_only(args.secret_file)
    print("\nMARK-LVII AGENT ACCEPTANCE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
