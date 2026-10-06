## 1. Reward Discovery on Startup

- [x] 1.1 Add `rewards.discover()` call in `main.py` after `_ensure_ollama()`, before `ChatBot` instances are created
- [x] 1.2 After `discover()` returns, print a summary: log whether `TTS_REWARD_ID` and `HIGHLIGHT_REWARD_ID` were resolved or still blank, with a warning if blank

## 2. Structured Redemption Failure Logging

- [x] 2.1 In `tts_sender._fire()`, after `rewards.redeem()` returns `False`, print `[TTS] Redemption failed (reward_id=<id>, token=…<last6>) — falling back to chat` before the chat fallback send
- [x] 2.2 In `responder._do_highlight()`, after `rewards.redeem()` returns `False`, print `[Highlight] Redemption failed (reward_id=<id>, token=…<last6>) — falling back to chat` before the chat fallback send

## 3. VPN Extension Detection

- [x] 3.1 In `browser_sessions.py`, add a `_CHROMIUM_FAMILY` set of browser names that support Chromium extension ID detection (`brave`, `chrome`, `msedge`, `opera`, `vivaldi`)
- [x] 3.2 Add `_VPN_EXTENSIONS` dict mapping VPN name → Chromium extension ID for ProtonVPN, NordVPN, ExpressVPN, Windscribe, TunnelBear, CyberGhost, Hola VPN, Browsec
- [x] 3.3 Add `_detect_vpn_extension(profile_dir)` that checks `profile_dir/Default/Extensions/<id>/` and returns `(vpn_name, ext_id)` or `None`

## 4. VPN Activation via Headless Playwright

- [x] 4.1 Add `activate_vpns()` function in `browser_sessions.py` that iterates over all account profiles
- [x] 4.2 For each session: if browser type is not in `_CHROMIUM_FAMILY`, log "skipped (Firefox not supported)" and continue
- [x] 4.3 For each Chromium-family session: call `_detect_vpn_extension()` on the profile dir; if `None`, fall through to built-in VPN check
- [x] 4.4 Extension VPN: Playwright `launch_persistent_context` (non-headless, offscreen window) opens popup BEFORE subprocess launch to avoid profile lock
- [x] 4.5 Navigate to `chrome-extension://<ext_id>/popup.html`, check connected selectors; log "already connected" and close if already active
- [x] 4.6 If not connected: click Connect with VPN-specific + generic selectors, wait 15s for connected state, log result, close context
- [x] 4.7 All per-browser activation wrapped in try/except; errors logged and startup continues unblocked
- [x] 4.8 Built-in VPN (Opera/Opera GX): `_patch_preferences()` writes `Preferences` JSON before subprocess launch to enable built-in VPN on startup

## 5. Wire activate_vpns into main.py

- [x] 5.1 In `main.py`, call `browser_sessions.activate_vpns()` BEFORE `launch_sessions()` (pre-launch required to avoid Chromium profile locking)
- [x] 5.2 `get_status()` reads from `_vpn_states` dict populated by `activate_vpns()`, returning name and status per browser including "skipped" for Firefox

## 6. Voice Transcription Ensemble

- [x] 6.1 Add `TRANSCRIBER_MODELS` to `config.py` — parse comma-separated env var, default to `["base.en", "small.en", "medium.en"]`
- [x] 6.2 Rewrite `transcriber.py`: replace `Transcriber` with `EnsembleTranscriber` that accepts a list of model names and loads each as a separate `whisper.load_model()` call on startup
- [x] 6.3 On startup, print "[Transcriber] Loading models: <list>" and a per-model "[Transcriber] <model> ready" (or warning on failure); wrap each load in try/except so a bad model name doesn't crash startup
- [x] 6.4 In `_run()`, for each audio chunk: fan out to one thread per model, each calling `self._model.transcribe(audio, language="en", fp16=False)`; collect all results with `concurrent.futures.ThreadPoolExecutor`
- [x] 6.5 Implement best-result selection: discard results where `no_speech_prob > 0.6`; among remaining, pick the one with the most words; if all discarded, skip chunk
- [x] 6.6 Print per-chunk log: `[Transcript] <winning_model>: <raw> → <cleaned>` on success, or `[Transcript] Chunk discarded (all models: no speech detected)` if none pass
- [x] 6.7 Update `main.py` import — `EnsembleTranscriber` now takes `(audio_queue, models)` signature; pass `config.TRANSCRIBER_MODELS`

## 7. Verification

- [ ] 7.1 Run `python main.py` with `BROWSER_SESSIONS_ENABLED=true` and confirm `[Rewards]` discovery output appears before bots connect
- [ ] 7.2 Type `tts` in terminal, confirm either "[Rewards] Redeemed" or "[TTS] Redemption failed … falling back to chat" appears (never silent)
- [ ] 7.3 Type `highlight` in terminal, confirm same structured log output
- [ ] 7.4 Type `diag` and confirm VPN status line appears per browser
- [ ] 7.5 Speak near the mic and confirm `[Transcript]` lines show the winning model name and cleaned text

