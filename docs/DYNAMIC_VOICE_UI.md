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
