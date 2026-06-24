---
sidebar_position: 1
slug: /
---

# Introduction

**Twitch Interactive Chat Simulator** listens to your live stream audio, transcribes what you say in real time, and generates authentic-looking chat reactions from multiple bot accounts using AI.

## How it works

```
Your voice → Audio capture → Whisper STT → LLM → Twitch chat
                                               ↑
                                         Stream context
                                      (game, title, etc.)
```

1. **Audio** — `streamlink` pulls your live Twitch stream audio, `ffmpeg` converts it to the format Whisper needs
2. **Transcription** — Local Whisper (`base.en`) converts your speech to text with no cloud fees
3. **LLM** — Local Ollama (primary) or OpenRouter (fallback) generates a short, natural chat message
4. **Chat** — Each bot account sends the message via its own Twitch IRC connection

## Key features

- 🎙️ Real-time speech-to-text via local Whisper
- 🤖 Multiple viewer archetypes — hype, casual, react, lurker
- 💬 "Chat" keyword detection — say "Chat, spam W's" and bots respond instantly
- 🎮 Stream context awareness — bots know your current game and stream title
- 🔁 Real viewer reactions — bots also react to actual chat messages
- 📢 Periodic TTS-style messages on a timer
- 🏆 Channel point redemptions via browser sessions (optional)

## Requirements

| Tool | Purpose |
|---|---|
| Python 3.11+ | Runtime |
| ffmpeg | Audio conversion |
| Ollama (optional) | Local LLM — faster, free, offline |
| Node.js 20+ | Docusaurus docs only |

## Next steps

Head to [Setup](./setup) to get started.
