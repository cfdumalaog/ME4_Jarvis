# ME4_Jarvis Raspberry Pi compatibility

## Result

The application is designed to run on a 64-bit Raspberry Pi OS/Linux desktop,
but a live Pi launch has not been verified in this checkout because the known
Pi hostname was not resolvable during the compatibility check. No Pi files were
changed.

The safe target is a Raspberry Pi 5 running 64-bit Raspberry Pi OS with a
working desktop session (X11 is the least-surprising target for the full HUD).
The voice pipeline itself does not require a GPU:

```text
USB microphone -> Mark-LVII audio capture/VAD -> Qwen2-Audio ASR
               -> Qwen/Qwen3.8-27B vLLM -> Qwen3-TTS CustomVoice
               -> USB speaker
```

Text input and the local action/plugin surface use the same model path.

## What is compatible

- `main.py` guards Windows-only subprocess and accessibility paths by OS.
- Windows-only Python packages are marked with `sys_platform == "win32"`.
- Linux speech output uses `espeak-ng` or `espeak`; install `espeak-ng` if the
  Qwen TTS endpoint is unavailable.
- Local Whisper is CPU-oriented and selects `int8` on CPU. It is a fallback,
  not a requirement when the Qwen ASR endpoint is reachable.
- The Qwen text, ASR, and TTS adapters use HTTP and the Python standard audio
  WAV reader; they do not require CUDA on the Pi.

## Pi-specific cautions

- The full Qt HUD needs a graphical display. A headless SSH session needs a
  display service or should run a voice-only wrapper instead of `main.py`.
- Browser automation requires a Playwright browser build and may be omitted on
  the Pi. Core text, voice, tools, and Qwen HTTP calls do not depend on it.
- `opencv-python`, `PyQt6`, and `faster-whisper` are the packages most likely to
  need Raspberry-Pi-specific wheels or extra build time. Install them in the
  shared Pi runtime only after checking the Pi's Python version and architecture.
- `pynvml` is optional for a CPU-only Pi and should not be treated as evidence
  of GPU support.
- The configured Qwen endpoints currently use unencrypted HTTP. Keep them on
  the trusted institutional network/VPN, or replace them with administrator-
  provided HTTPS endpoints before exposing the agent beyond that network.
- A real microphone/speaker test is still required. Offline tests cannot prove
  acoustic VAD, echo suppression, barge-in, or ALSA device selection.

## Verification still required on the board

Run these read-only checks on the Pi before installing anything:

```bash
uname -m
python3 --version
python3 -c "import platform; print(platform.platform())"
```

Then install the project dependencies into the Pi's shared environment and
verify the runtime in this order:

```bash
python3 -m compileall -q .
python3 -m providers._tests
python3 -m providers.schema
python3 scripts/test_agent.py --skip-live --skip-github
```

Only after those pass should an operator run the live Qwen checks with the
protected environment variables and perform the controlled microphone/speaker
acceptance test.
