# Dynamic voice UI

ME4_Jarvis now uses a native Qt adaptation of the dynamic voice interface from
the separately published `cfdumalaog/ME4-Initial` project. The visual source is
the ME4-Initial `public/` voice stage: a glowing orb, animated orbit rings,
microphone/playback level spikes, state colours, a live assistant label, and a
text-input fallback.

The adaptation is deliberately presentation-only. The existing Jarvis audio
pipeline still owns the real microphone level, VAD state, speech recognition,
model turn, TTS playback, visemes, confirmations, actions, memory, and text
input. The dynamic orb consumes the already-smoothed level from `HudCanvas`, so
it cannot invent a voice event or transmit audio by itself.

The HUD centrepiece cycle is:

`Dynamic voice → Reactor core → Animated face → Dynamic voice`

The dynamic voice orb is now the default when no centrepiece has been chosen.
An existing explicit choice is preserved, and the Controls drawer can switch
between all three centrepieces.

## Qwen audio endpoints

The protected Qwen deployment used by ME4_Jarvis has two separate audio
services:

```text
ASR  http://10.153.60.233:8000/v1  Qwen/Qwen2-Audio-7B-Instruct
TTS  http://10.153.60.233:8001/v1  Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
```

Qwen2-Audio is configured through the multimodal `/v1/chat/completions`
route. The adapter sends the captured WAV as a base64 `audio_url` content item
and extracts the transcript from the assistant message. The older
`/v1/audio/transcriptions` route remains available only when `protocol` is
explicitly set to `transcriptions`. Qwen3-TTS continues to use
`/v1/audio/speech`.
