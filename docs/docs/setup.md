---
sidebar_position: 2
---

# Setup

## 1. Prerequisites

Install these before anything else:

- **Python 3.11+** — [python.org](https://www.python.org)
- **ffmpeg** — `winget install Gyan.FFmpeg` (Windows) or `brew install ffmpeg` (Mac)
- **Node.js 20+** — [nodejs.org](https://nodejs.org) (for docs only)
- **Ollama** (optional but recommended) — [ollama.com](https://ollama.com)

## 2. Clone the repo

```bash
git clone https://github.com/SamOffTheBorder/Twitch-Interactive-Chat-Simulator.git
cd Twitch-Interactive-Chat-Simulator
```

## 3. Install Python dependencies

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

## 4. Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in your values. See [Configuration](./configuration) for a full breakdown.

## 5. Install local LLM (recommended)

```bash
# After installing Ollama from https://ollama.com:
ollama pull dolphin-llama3
```

If you skip this, the bot uses OpenRouter's free tier instead (slower, requires internet).

## 6. Generate bot tokens

Run once per bot account — it opens a browser and handles the OAuth flow:

```bash
python token_gen.py
```

See [Bot Accounts](./bot-accounts) for the full guide.

## 7. Run

```bash
python main.py
```

The bot will:
- Start Ollama automatically if it's installed
- Connect all bot accounts to Twitch chat
- Pull your stream audio and begin listening
- Start generating chat reactions within the first minute
