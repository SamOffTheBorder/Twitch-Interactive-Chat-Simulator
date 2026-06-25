import asyncio
import random
import threading
import time
from typing import Callable, Coroutine

import llm
import config
import rewards

TTS_SYSTEM = """\
You are a real viewer redeeming Text-to-Speech on a Twitch stream.
Your message will be read aloud so no emotes or emojis.

Rules:
- 100 characters max, short is better
- Sound natural and a little unhinged — like something a real person types without thinking
- NO questions. NO compliments. NO advice.
- NO emotes or emojis — they sound weird in TTS
- Casual, slightly random, maybe a little chaotic
- Good examples:
    "this is actually insane bro"
    "chat we are so back"
    "ngl I was not expecting that"
    "I literally just sat down and this happened"
    "stream is going crazy rn"
    "bro woke up and chose violence"
    "ok that was actually wild"
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
            text = llm.complete(TTS_SYSTEM, "Generate a TTS message for the stream.", max_tokens=25)
            if not text:
                return
            text = text.strip().split("\n")[0].strip().strip('"\'')
            text = text[:100]
            print(f"[TTS] → {text}")
            idx = random.randrange(len(config.TWITCH_TOKENS))
            token = config.TWITCH_TOKENS[idx]
            if not rewards.redeem(token, config.TTS_REWARD_ID, text):
                # Fall back to regular chat if redemption fails
                send_fn = self._send_fns[idx] if idx < len(self._send_fns) else random.choice(self._send_fns)
                future = asyncio.run_coroutine_threadsafe(send_fn(text), self._loop)
                future.result(timeout=10)
        except Exception as e:
            print(f"[TTS] Error: {e}")
