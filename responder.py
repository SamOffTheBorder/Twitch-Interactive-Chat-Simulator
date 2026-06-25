import asyncio
import math
import queue
import random
import re
import threading
import time
from typing import Callable, Coroutine

import llm
import config
from stream_info import StreamInfo

# Matches a unicode emoji (with optional skin tone / ZWJ continuation) or a common Twitch text emote.
_EMOJI_TOKEN_RE = re.compile(
    r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F9FF]"
    r"[‍️\U0001F3FB-\U0001F3FF\U0001F300-\U0001FAFF]*"
    r"|\b(?:KEKW|LUL|LULW|PogChamp|Pog|POGGERS|Sadge|monkaS|Kappa|PepeHands|"
    r"OMEGALUL|EZ|Clap|4Head|BibleThump|TriHard|FeelsBadMan|FeelsGoodMan|"
    r"COPIUM|GIGACHAD|pepeLaugh|pepeD|Pepega|NOTED|catJAM|HYPERS|"
    r"widepeepoHappy|PauseChamp|Madge|ComfyChamp)\b"
)


def _emoji_filter(text: str) -> str:
    """P(keep nth emoji/emote) = 1/log2(n+1). First always kept, rest taper off."""
    matches = list(_EMOJI_TOKEN_RE.finditer(text))
    if len(matches) <= 1:
        return text
    to_drop = [m for i, m in enumerate(matches) if random.random() > 1.0 / math.log2(i + 2)]
    for m in reversed(to_drop):
        left = text[:m.start()].rstrip()
        right = text[m.end():].lstrip()
        text = left + (" " if left and right else "") + right
    return text.strip()


_CLAUSE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_PARENTHETICAL_RE = re.compile(r"\s*\([^)]*\)")


def _fragment_filter(text: str) -> str:
    """P(keep nth sentence clause) = 1/log2(n+1). Also strips parenthetical asides."""
    text = _PARENTHETICAL_RE.sub("", text).strip()
    clauses = _CLAUSE_SPLIT_RE.split(text)
    if len(clauses) <= 1:
        return text
    kept = [clauses[0]]
    for i, clause in enumerate(clauses[1:], start=1):
        if clause.strip() and random.random() <= 1.0 / math.log2(i + 2):
            kept.append(clause.strip())
    return " ".join(kept)


_BRACKET_RE = re.compile(r"\[.*?\]")
_NUMBERED_RE = re.compile(r"\b\d+(?:st|nd|rd|th)\s+\w+", re.IGNORECASE)
_HR_RE = re.compile(r"\s*[-*_]{2,}\s*")  # markdown horizontal rules: ---, ***, ___

def _clean(text: str) -> str:
    text = text.strip()
    # Chat is single-line — keep only the first line
    text = text.split("\n")[0].strip()
    # Strip markdown horizontal rule and everything after (model reasoning separator)
    m = _HR_RE.search(text)
    if m:
        text = text[:m.start()].strip()
    # Strip outer quotes the LLM sometimes wraps the whole message in
    if len(text) >= 2 and text[0] in ('"', "'") and text[-1] == text[0]:
        text = text[1:-1].strip()
    # Remove [Tag] artifacts the model echoes back
    text = _BRACKET_RE.sub("", text).strip()
    # Strip unclosed parenthetical — model reasoning leaking out e.g. "(If a specific action..."
    open_idx = text.find("(")
    if open_idx >= 0 and ")" not in text[open_idx:]:
        text = text[:open_idx].strip()
    # Strip numbered-example artifacts e.g. "1st example based on current context"
    m = _NUMBERED_RE.search(text)
    if m:
        text = text[:m.start()].strip()
    text = _fragment_filter(_emoji_filter(text))
    # Hard cap — split at first sentence boundary before 80 chars, or just truncate
    if len(text) > 80:
        boundary = max(
            (text.rfind(c, 0, 80) for c in ".!?"), default=-1
        )
        text = text[:boundary + 1] if boundary > 20 else text[:80]
    return text.strip()


ARCHETYPES = [
    {
        "name": "hype",
        "style": 'Hype viewer. Short energy bursts. NO greetings, NO questions. Examples: "LETS GO", "W", "POG", "bro no way", "KEKW", "AYOOO", "NOOO", "he cooked".',
        "weight": 0.20,
    },
    {
        "name": "casual",
        "style": 'Chill viewer, all lowercase. NO greetings, NO questions. Examples: "lol", "ngl tho", "bro what", "same", "wild", "welp", "nah", "L", "mid".',
        "weight": 0.40,
    },
    {
        "name": "react",
        "style": 'Reacts briefly to what just happened. NO questions, NO greetings. Examples: "wait that worked??", "bro same lmao", "this guy", "he cooked", "sold", "real".',
        "weight": 0.20,
    },
    {
        "name": "lurker",
        "style": 'Rarely talks. When you do, 1-3 words max. NO greetings, NO questions. Examples: "lol", "gg", "nah", "ok", "same", "W".',
        "weight": 0.20,
    },
]

_BASE_PROMPT = """\
You are a real Twitch viewer in chat. {style}

Output ONLY your chat message — nothing else. No labels, no quotes, no explanations, no reasoning.
- 1-5 words usually. Absolute max 80 characters.
- ALL CAPS ok. Repeated letters ok (AYOOO, NOOOOO).
- No questions. No greetings. No advice. No hashtags.
- Never reveal you are a bot or AI. Never explain your response.
- Good: REAL, L, bro lol, ngl, W, welp, BRUH, he cooked, nah, mid, AYOOOO
- Bad: questions, greetings, meta-commentary, parenthetical explanations
- If nothing happened worth reacting to, reply: SKIP
"""

_JOIN_WINDOW = 60  # viewers join within the first minute


class ViewerPersona:
    def __init__(
        self,
        idx: int,
        archetype: dict,
        send_fn: Callable[[str], Coroutine],
        loop: asyncio.AbstractEventLoop,
        stream_info: "StreamInfo | None" = None,
    ):
        self.idx = idx
        self.archetype = archetype
        self._send = send_fn
        self._loop = loop
        self._stream_info = stream_info
        self._cooldown = random.uniform(60, 120) #Message Cooldown
        self._prob = random.uniform(0.10, 0.20) #Chance Bots respond to Audio in the stream
        self._last_sent = 0.0
        self._join_delay = random.uniform(0, _JOIN_WINDOW)
        self._active = False
        self._system = _BASE_PROMPT.format(style=archetype["style"])

    def _context_hint(self) -> str:
        """60% stream title/category, 20% streamer name, 20% no extra context."""
        if not self._stream_info:
            return ""
        info = self._stream_info.snapshot()
        roll = random.random()
        if roll < 0.60:
            parts = []
            if info["category"]:
                parts.append(info["category"])
            if info["title"]:
                parts.append(f'"{info["title"]}"')
            if parts:
                return " (stream is " + ", ".join(parts) + ")"
        elif roll < 0.80:
            streamer = info["streamer"] or config.TWITCH_CHANNEL
            return f" (streamer is {streamer})"
        return ""

    def _dispatch(self, text: str):
        future = asyncio.run_coroutine_threadsafe(self._send(text), self._loop)
        future.result(timeout=10)

    def _maybe_follow_up(self, first_text: str):
        """15% chance to send a quick second message 2-8s after the first."""
        if random.random() > 0.10: #Follow up message chance
            return
        time.sleep(random.uniform(1.5, 4.0))
        try:
            system = self._system + "\nIMPORTANT: You MUST send a message. Do NOT reply SKIP."
            text = llm.complete(
                system,
                f'You just said "{first_text}" in chat — send a quick follow-up. '
                "Could be adding to it, reacting to your own message, or just a short noise like \"lol\" or \"wait nvm\".",
            )
            if text and text.upper() != "SKIP":
                text = _clean(text)
                print(f"[Viewer {self.idx} / {self.archetype['name']}] ↩ {text}")
                self._dispatch(text)
        except Exception as e:
            print(f"[Viewer {self.idx}] Follow-up error: {e}")

    def start(self):
        threading.Thread(target=self._join_countdown, daemon=True).start()

    def _join_countdown(self):
        time.sleep(self._join_delay)
        self._active = True
        mins, secs = divmod(int(self._join_delay), 60)
        print(f"[Viewer {self.idx} / {self.archetype['name']}] Joined chat ({mins}m {secs}s after stream start)")

    def _can_send(self) -> bool:
        return time.monotonic() - self._last_sent >= self._cooldown

    def consider(self, transcript: str):
        if not self._active or not self._can_send():
            return
        if random.random() > self._prob:
            return
        self._last_sent = time.monotonic()
        threading.Thread(target=self._respond, args=(transcript,), daemon=True).start()

    def consider_chat(self, username: str, message: str):
        self._last_sent = time.monotonic()
        threading.Thread(target=self._respond_to_chat, args=(username, message), daemon=True).start()

    def respond_now(self, transcript: str):
        """Streamer said 'Chat' — bypass cooldown and probability, respond to the transcript."""
        self._last_sent = time.monotonic()
        threading.Thread(target=self._respond, args=(transcript,), daemon=True).start()

    def force_message(self):
        threading.Thread(target=self._spontaneous, daemon=True).start()

    def force_highlight(self):
        threading.Thread(target=self._do_highlight, daemon=True).start()

    def _do_highlight(self):
        try:
            import rewards
            system = (
                f"You are a Twitch viewer. {self.archetype['style']} "
                "Send ONE short chat message, 1-5 words. Output ONLY the message, no quotes. "
                "Real examples: lol, W, bro what, ngl, AYOOO, he cooked, same, nah, mid."
            )
            text = llm.complete(system, "Say something in chat." + self._context_hint())
            if not text or text.upper() == "SKIP":
                text = "W"
            text = _clean(text)
            print(f"[Viewer {self.idx}] → {text} (highlight)")
            token = config.TWITCH_TOKENS[self.idx] if self.idx < len(config.TWITCH_TOKENS) else ""
            if not rewards.redeem(token, config.HIGHLIGHT_REWARD_ID, text):
                # Fall back to regular chat if redemption fails
                future = asyncio.run_coroutine_threadsafe(self._send(text), self._loop)
                future.result(timeout=10)
        except Exception as e:
            print(f"[Viewer {self.idx}] Highlight error: {e}")

    def _spontaneous(self):
        try:
            # Skip-free prompt — don't include the SKIP rule at all so the model can't choose it
            system = (
                f"You are a Twitch viewer. {self.archetype['style']} "
                "Send ONE short chat message, 1-5 words. "
                "Output ONLY the message itself — no quotes, no labels, no punctuation outside the message. "
                "Real examples: lol, W, bro what, ngl, AYOOO, he cooked, same, nah, mid, REAL. "
                "Never greet, never ask questions, never say you are a bot or AI."
            )
            hint = self._context_hint()
            user_prompt = (
                f"React to something happening on stream{hint}. One short reaction, no quotes."
            )
            text = llm.complete(system, user_prompt)
            if text and text.upper() != "SKIP":
                text = _clean(text)
                print(f"[Viewer {self.idx} / {self.archetype['name']}] → {text}")
                self._dispatch(text)
                self._maybe_follow_up(text)
            else:
                print(f"[Viewer {self.idx}] LLM returned empty/SKIP for spontaneous message")
        except Exception as e:
            print(f"[Viewer {self.idx}] Error in spontaneous: {e}")

    def _respond(self, transcript: str):
        time.sleep(random.uniform(0.2, 2.0))
        try:
            text = llm.complete(self._system, f'Streamer said: "{transcript}"' + self._context_hint())
            if text and text != "SKIP":
                text = _clean(text)
                print(f"[Viewer {self.idx} / {self.archetype['name']}] → {text}")
                self._dispatch(text)
                self._maybe_follow_up(text)
        except Exception as e:
            print(f"[Viewer {self.idx}] Error: {e}")

    def _respond_to_chat(self, username: str, message: str):
        time.sleep(random.uniform(0.5, 2.0))
        try:
            text = llm.complete(
                self._system,
                f'Viewer "{username}" just said in chat: "{message}" — react or respond naturally.'
                + self._context_hint(),
            )
            if text and text != "SKIP":
                text = _clean(text)
                print(f"[Viewer {self.idx} / {self.archetype['name']}] → {text}")
                self._dispatch(text)
                self._maybe_follow_up(text)
        except Exception as e:
            print(f"[Viewer {self.idx}] Error in chat response: {e}")

    def status(self) -> str:
        remaining = max(0.0, self._cooldown - (time.monotonic() - self._last_sent))
        state = "ACTIVE" if self._active else f"joining in {max(0, int(self._join_delay - time.monotonic()))}s"
        return (
            f"  Viewer {self.idx} [{self.archetype['name']}]: {state}, "
            f"cooldown={self._cooldown:.0f}s (ready in {remaining:.0f}s), "
            f"prob={self._prob * 100:.0f}%"
        )


class Responder:
    def __init__(
        self,
        transcript_queue: queue.Queue,
        send_fns: list[Callable[[str], Coroutine]],
        loop: asyncio.AbstractEventLoop,
        stream_info: "StreamInfo | None" = None,
    ):
        self._text_q = transcript_queue

        weights = [a["weight"] for a in ARCHETYPES]
        self._viewers = [
            ViewerPersona(
                i + 1,
                random.choices(ARCHETYPES, weights=weights)[0],
                send_fns[i],
                loop,
                stream_info,
            )
            for i in range(len(send_fns))
        ]
        for v in self._viewers:
            mins, secs = divmod(int(v._join_delay), 60)
            print(
                f"[Viewer {v.idx}] archetype={v.archetype['name']}, "
                f"joins in {mins}m {secs}s, "
                f"{v._cooldown:.0f}s cooldown, {v._prob * 100:.0f}% response chance"
            )

    def trigger_test(self):
        active = [v for v in self._viewers if v._active] or self._viewers
        chosen = random.choice(active)
        print(f"[Commands] Forcing message from Viewer {chosen.idx} ({chosen.archetype['name']})...")
        chosen.force_message()

    def trigger_highlight(self):
        active = [v for v in self._viewers if v._active] or self._viewers
        chosen = random.choice(active)
        print(f"[Commands] Viewer {chosen.idx} sending highlighted message...")
        chosen.force_highlight()

    def trigger_chat(self, username: str, message: str):
        """Route an incoming viewer chat message — 70% chance per eligible viewer."""
        active = [v for v in self._viewers if v._active and v._can_send()]
        for v in active:
            if random.random() < 0.30:
                v.consider_chat(username, message)

    def print_status(self):
        print("[Diagnostics] Viewer pool:")
        for v in self._viewers:
            print(v.status())

    def start(self):
        for v in self._viewers:
            v.start()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        print("[Responder] Pool ready — watching for transcripts...")
        while True:
            transcript: str = self._text_q.get()
            for viewer in self._viewers:
                viewer.consider(transcript)
            if re.search(r'\bchat\b', transcript, re.IGNORECASE):
                # Wait for the next chunk so we hear the full instruction
                # e.g. "Chat" ends one chunk, "spam w's in the chat" is the next
                try:
                    followup = self._text_q.get(timeout=7)
                    for viewer in self._viewers:
                        viewer.consider(followup)
                    combined = f"{transcript} {followup}".strip()
                except queue.Empty:
                    combined = transcript

                active = [v for v in self._viewers if v._active] or self._viewers
                count = random.randint(2, min(3, len(active)))
                chosen = random.sample(active, count)
                print(f"[Responder] 'Chat' detected — {count} viewer(s) responding to: {combined!r}")
                for v in chosen:
                    v.respond_now(combined)
