---
sidebar_position: 5
---

# Viewer Archetypes

Each bot account is randomly assigned a personality archetype at startup. Archetypes control tone, message length, and how each bot reacts.

## Available archetypes

| Archetype | Weight | Style |
|---|---|---|
| **hype** | 30% | Short energy bursts — `LETS GO`, `W`, `AYOOO`, `he cooked` |
| **casual** | 30% | All lowercase, chill — `lol`, `ngl tho`, `bro what`, `mid` |
| **react** | 30% | Reacts to what just happened — `wait that worked??`, `sold`, `real` |
| **lurker** | 10% | 1–3 words max, rarely chats — `lol`, `gg`, `W` |

## Tuning chattiness

Edit these values in `responder.py`:

| Setting | Location | Effect |
|---|---|---|
| Cooldown | `random.uniform(60, 120)` | Minimum seconds between messages per viewer |
| Response chance | `random.uniform(0.10, 0.20)` | Probability of reacting to each audio chunk |
| Follow-up chance | `random.random() > 0.10` | Probability of a second quick message |
| Chat reaction | `random.random() < 0.30` | Probability of reacting to real viewer messages |

Lower the cooldown or raise the probabilities for a more active chat. Raise cooldown or lower probabilities for quieter behavior.

## How "Chat" detection works

When Whisper transcribes something containing the word "chat", the responder waits up to 7 seconds for the next audio chunk (to catch the full instruction), then forces 2–3 randomly selected viewers to respond immediately, bypassing their cooldowns.

Example: saying *"Chat, spam W's"* triggers this path.
