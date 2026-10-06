## Why

The `tts` and `highlight` terminal commands fall back to regular chat instead of firing real Twitch channel point redemptions, VPN extensions in browser sessions no longer auto-connect since the switch from Playwright to subprocess launching, and the single Whisper `base.en` transcriber frequently misreads what the streamer says — causing bot responses to miss the point entirely. All three features exist but don't reliably work end-to-end.

## What Changes

- Add reward discovery on startup so `TTS_REWARD_ID` and `HIGHLIGHT_REWARD_ID` are auto-resolved even when left blank in `.env`
- Add structured error reporting when `rewards.redeem()` fails (log HTTP status, GQL error message) instead of silently falling back to chat
- Add a post-launch VPN activation phase that uses Playwright headlessly to connect VPN extensions in each browser profile after subprocess launch
- Wire startup reward discovery into `main.py` before bots connect
- Run three Whisper models (`base.en`, `small.en`, `medium.en`) in parallel on each audio chunk and pick the best result using no-speech probability and word count as a confidence signal — the ensemble almost never misses what was said

## Capabilities

### New Capabilities
- `channel-point-redemption`: Reliable channel point redemption via GQL — reward auto-discovery on startup, structured error logging, no silent chat fallback
- `voice-transcription-ensemble`: Multi-model Whisper ensemble — three models run in parallel per audio chunk; best result (lowest no_speech_prob, most words) wins; configurable via `TRANSCRIBER_MODELS` env var

### Modified Capabilities
- `vpn-extension-activation`: Re-add VPN auto-activation support after subprocess browser launch pivot — Playwright headless phase clicks Connect on VPN extension popup per browser profile
- `browser-session-management`: Post-launch VPN activation hook runs after `launch_sessions()` completes

## Impact

- `rewards.py`: Enhanced error reporting and discovery logging
- `tts_sender.py`: Uses `rewards.discover()` result, logs redemption failures clearly
- `responder.py`: Same for highlight redemptions
- `main.py`: Calls `rewards.discover()` on startup, passes reward IDs into components
- `browser_sessions.py`: New `activate_vpns()` function called after launch; requires `playwright` package (already in `requirements.txt`)
- `transcriber.py`: Replaced single-model `Transcriber` with `EnsembleTranscriber` that loads and runs multiple Whisper models in parallel threads; `TRANSCRIBER_MODELS` env var controls which models to use (default: `base.en,small.en,medium.en`)
- `config.py`: New `TRANSCRIBER_MODELS` list config
- `requirements.txt`: No new packages — `openai-whisper` already covers all model sizes
