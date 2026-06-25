# Twitch Interactive Chat Simulator

Listens to your live Twitch stream audio, transcribes what you say in real time, and generates authentic-looking chat reactions from multiple bot accounts using a local or cloud LLM. Bots have distinct personalities (hype, casual, react, lurker), respond naturally to your voice, and react to other viewers chatting.

---

## Features

- **Real-time speech-to-text** via local Whisper (`base.en`) — no cloud STT fees
- **LLM-generated chat reactions** — local Ollama (primary) with OpenRouter fallback
- **6 distinct viewer archetypes** — hype, casual, react, lurker, each with their own cooldown and response rate
- **"Chat" keyword detection** — say "Chat, spam W's" and bots respond immediately
- **TTS periodic messages** — bots send random unhinged messages on a timer
- **Stream context awareness** — bots know your current game and stream title
- **Real viewer reactions** — bots react to actual chat messages from real viewers
- **Channel point redemptions** — Highlight My Message and TTS via browser sessions (optional)

---

## Requirements

| Tool | Purpose | Install |
|---|---|---|
| Python 3.11+ | Runtime | [python.org](https://www.python.org) |
| ffmpeg | Audio conversion | `winget install Gyan.FFmpeg` |
| Ollama | Local LLM (optional) | [ollama.com](https://ollama.com) |

---

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/SamOffTheBorder/Twitch-Interactive-Chat-Simulator.git
cd Twitch-Interactive-Chat-Simulator
pip install -r requirements.txt
python -m playwright install chromium
```

### 2. Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in:

| Variable | Where to get it |
|---|---|
| `TWITCH_CHANNEL` | Your Twitch username |
| `TWITCH_TOKENS` | One token per bot account — see step 3 below |
| `TWITCH_CLIENT_ID` / `TWITCH_CLIENT_SECRET` | [dev.twitch.tv/console](https://dev.twitch.tv/console) → Register an app |
| `OPENROUTER_API_KEY` | [openrouter.ai](https://openrouter.ai) — free tier available |
| `LOCAL_LLM_MODEL` | Name of your Ollama model e.g. `dolphin-llama3` — leave blank to use OpenRouter only |

### 3. Generate bot tokens

For each bot account, go to **[twitchtokengenerator.com](https://twitchtokengenerator.com)** and generate a token with only these two scopes:

- `chat:read`
- `chat:edit`

Log in as the bot account when prompted. Copy the **Access Token** and paste it into `TWITCH_TOKENS` in `.env`, comma-separated:

```
TWITCH_TOKENS=token_account1,token_account2,token_account3
```

Repeat for each bot account. These tokens last much longer than tokens generated via standard OAuth flows and don't require running any local scripts.

### 4. Install local LLM (optional but recommended)

```bash
# Install Ollama from https://ollama.com, then:
ollama pull dolphin-llama3
```

If you skip this, the bot falls back to OpenRouter (free tier, slower).

### 5. Set up browser sessions (optional — for channel point redemptions)

```bash
python setup_sessions.py
```

Opens a Chromium window for each bot account. Log in as each one — sessions are saved locally and loaded headlessly at runtime. Skip this if you don't use channel points.

### 6. Run

```bash
python main.py
```

---

## Runtime commands

Type these into the terminal while the bot is running:

| Command | Action |
|---|---|
| `test` | Force a random viewer to send a message right now |
| `tts` | Fire a TTS-style message immediately |
| `highlight` | Force a Highlight My Message redemption |
| `diag` | Show viewer status, real viewer count, bot connections |
| `restart` | Restart everything |
| `stop` | Shut down |

---

## AI Models

### Primary — Local Ollama
- Model: `dolphin-llama3` (or any Ollama model)
- Runs on your machine, no API cost, works offline
- Set `LOCAL_LLM_MODEL=` in `.env` to disable

### Fallback — OpenRouter
- Default: `meta-llama/llama-3.3-70b-instruct:free`
- Used automatically when Ollama is unavailable
- Free tier requires an account at [openrouter.ai](https://openrouter.ai)

### Speech-to-text — Whisper
- Model: `base.en` (downloads ~140MB on first run, cached after)
- Runs fully locally via `openai-whisper`
- No API key needed

---

## File overview

| File | Purpose |
|---|---|
| `main.py` | Entry point — starts everything, command console |
| `audio.py` | Pulls stream audio via streamlink + ffmpeg |
| `transcriber.py` | Whisper speech-to-text |
| `responder.py` | Viewer personas, LLM calls, message dispatch |
| `chat.py` | Twitch IRC connections via twitchio |
| `llm.py` | Ollama / OpenRouter abstraction |
| `stream_info.py` | Fetches live stream title and game via Helix API |
| `tts_sender.py` | Periodic TTS-style messages |
| `browser_sessions.py` | Playwright browser pool for channel point redemptions |
| `setup_sessions.py` | One-time browser login setup |
| `token_gen.py` | Alternative OAuth token generator (optional) |
| `config.py` | Loads all settings from `.env` |

---

## Security notes

- **Never commit `.env`** — it contains your tokens and API keys. It is excluded by `.gitignore`.
- **Never commit `sessions/`** — it contains browser auth data. Also excluded.
- Bot account tokens have `chat:read` and `chat:edit` scopes only — they cannot access your streamer account.
