---
sidebar_position: 6
---

# Runtime Commands

While the bot is running, type these into the terminal:

| Command | What it does |
|---|---|
| `test` | Forces a random active viewer to send a message immediately |
| `tts` | Fires a TTS-style message right now (ignores the timer) |
| `highlight` | Forces a Highlight My Message redemption from a random viewer |
| `diag` | Shows live viewer count, real chatters, bot status, and config |
| `restart` | Restarts the entire bot |
| `stop` | Shuts everything down |
| `help` | Shows the command list |

## diag output example

```
[Diagnostics] ══════════════════════════════
  TWITCH_CHANNEL     : your_channel
  OPENROUTER_MODEL   : nvidia/nemotron-3-ultra-550b-a55b:free
  TTS_INTERVAL       : 43s – 208s
  OPENROUTER_API_KEY : set

  Twitch viewers     : 12 (live from Helix API)
  Real chatters      : 3 unique this session — viewer1, viewer2, viewer3
  Bot accounts       : 6 connected — account1, account2, ...
  Viewer 1 [hype]: ACTIVE, cooldown=90s (ready in 12s), prob=45%
  Viewer 2 [casual]: ACTIVE, cooldown=75s (ready in 0s), prob=30%
  ...
```
