import asyncio
import random
import threading
import time
from typing import Callable, Coroutine

import llm
import config
import rewards

TTS_SYSTEM = """\
You are a real Twitch viewer typing a TTS message. It gets read aloud — keep it SHORT.

Rules:
- 3 to 6 words MAX. Absolute hard limit.
- No emotes, no emojis, no punctuation beyond a comma.
- Lowercase. Sound like a real person typing fast.
- Output ONLY the words — nothing else, no quotes.
- Examples: chat we are so back / ngl that was insane / bro I was not ready / he actually did it / stream is unreal rn / ok that actually happened
"""


class TTSSender:
    def __init__(
        self,
        send_fns: list[Callable[[str], Coroutine]],
        loop: asyncio.AbstractEventLoop,
    ):
        self._send_fns = send_fns
        self._loop = loop

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        initial = random.uniform(120, 240)
        print(f"[TTS] First message in {initial / 60:.1f}m")
        time.sleep(initial)
        while True:
            self._fire()
            interval = random.uniform(config.TTS_MIN_INTERVAL, config.TTS_MAX_INTERVAL)
            print(f"[TTS] Next message in {interval / 60:.1f}m")
            time.sleep(interval)

    def _fire(self):
        try:
            text = llm.complete(TTS_SYSTEM, "Generate a TTS message for the stream.", max_tokens=8)
            if not text:
                return
            text = text.strip().split("\n")[0].strip().strip('"\'')
            # Hard-cap at 6 words
            words = text.split()
            if len(words) > 6:
                text = " ".join(words[:6])
            text = text[:45]
            print(f"[TTS] → {text}")
            idx = random.randrange(len(config.TWITCH_TOKENS))
            token = config.TWITCH_TOKENS[idx]
            if not rewards.redeem(token, config.TTS_REWARD_ID, text):
                print(f"[TTS] Redemption failed (reward_id={config.TTS_REWARD_ID!r}, token=…{token[-6:]}) — falling back to chat")
                send_fn = self._send_fns[idx] if idx < len(self._send_fns) else random.choice(self._send_fns)
                future = asyncio.run_coroutine_threadsafe(send_fn(text), self._loop)
                future.result(timeout=10)
        except Exception as e:
            print(f"[TTS] Error: {e}")
