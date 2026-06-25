---
sidebar_position: 3
---

# Configuration

All settings live in `.env` in the project root. Copy `.env.example` to get started.

:::warning Never commit `.env`
It contains your API keys and tokens. It is excluded by `.gitignore` — keep it that way.
:::

## Twitch

| Variable | Description |
|---|---|
| `TWITCH_CHANNEL` | Your Twitch channel name (streamer account, not a bot) |
| `TWITCH_TOKENS` | Comma-separated OAuth tokens, one per bot account |
| `TWITCH_CLIENT_ID` | From [dev.twitch.tv/console](https://dev.twitch.tv/console) |
| `TWITCH_CLIENT_SECRET` | From the same app registration |

`TWITCH_CLIENT_ID` and `TWITCH_CLIENT_SECRET` are used to fetch your stream title and game via the Helix API. Register a free app at the Twitch developer console — set the redirect URL to `http://localhost:3000`.

## AI Models

| Variable | Description | Default |
|---|---|---|
| `LOCAL_LLM_MODEL` | Ollama model name | `dolphin-llama3` |
| `LOCAL_LLM_URL` | Ollama endpoint | `http://localhost:11434/v1` |
| `OPENROUTER_API_KEY` | From [openrouter.ai](https://openrouter.ai) | required |
| `OPENROUTER_MODEL` | Primary cloud model | `nvidia/nemotron-3-super-120b-a12b:free` |
| `OPENROUTER_FALLBACK_MODEL` | Secondary cloud model | `meta-llama/llama-3.3-70b-instruct:free` |

The bot tries **Ollama first**, then falls back to OpenRouter automatically if Ollama is unavailable or fails.

Leave `LOCAL_LLM_MODEL` blank to skip Ollama and always use OpenRouter.

## TTS Timer

| Variable | Description | Default |
|---|---|---|
| `TTS_MIN_INTERVAL` | Minimum seconds between TTS messages | `180` |
| `TTS_MAX_INTERVAL` | Maximum seconds between TTS messages | `480` |

The bot picks a random interval between these two values after each TTS message fires.

## Channel Points (optional)

| Variable | Description |
|---|---|
| `TTS_REWARD_ID` | Leave blank — auto-discovered by title match |
| `HIGHLIGHT_REWARD_ID` | Leave blank — auto-discovered by title match |

Channel point redemptions require running `python setup_sessions.py` to set up browser sessions. See [Channel Points](./channel-points).
