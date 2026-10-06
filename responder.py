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
    """Keep up to 6 emoji/emote tokens; drop any beyond that."""
    matches = list(_EMOJI_TOKEN_RE.finditer(text))
    if len(matches) <= 6:
        return text
    to_drop = matches[6:]
    for m in reversed(to_drop):
        left = text[:m.start()].rstrip()
        right = text[m.end():].lstrip()
        text = left + (" " if left and right else "") + right
    return text.strip()


_SPAM_EMOJIS = ["💀", "🗣️", "🔥", "😭", "🐐", "👀", "🤣", "💯", "😤", "🫡", "🤯", "👏"]


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

def _randomize_caps(text: str) -> str:
    """Shift capitalization on individual words to mimic uneven real-chat typing."""
    words = text.split()
    out = []
    for w in words:
        r = random.random()
        if w.isupper() and len(w) > 2 and r < 0.30:
            out.append(w.lower())        # soften a full-caps word 30% of the time
        elif not w.isupper() and r < 0.07:
            out.append(w.upper())        # randomly shout a word 7% of the time
        else:
            out.append(w)
    return " ".join(out)


_LABEL_RE = re.compile(r'^\w[\w ]{0,15}[:\-–]\s*')  # "React: " "REACTION - " "Output: " etc.

# Patterns that mean the LLM leaked meta-commentary or generated dangerous content
_FILTER_RE = re.compile(
    r'https?://'                          # URLs — never let bots post links
    r'|No streamer'                       # "No streamer interaction at the moment"
    r'|\binteraction\b'                   # meta-commentary
    r'|at the moment'                     # "at the moment"
    r'|The streamer (is|was|just|said)'   # describing the streamer
    r'|streamer (just|is|was) (said|play|do)'
    , re.IGNORECASE
)

# Adjacent keys on a QWERTY keyboard — used to generate realistic transposition typos
_ADJACENT: dict[str, str] = {
    "a": "sqwz", "b": "vghn", "c": "xdfv", "d": "serfcx", "e": "wrsdf",
    "f": "drtgvc", "g": "ftyhbv", "h": "gyujnb", "i": "uojkl", "j": "huikmn",
    "k": "jiolm", "l": "kop", "m": "njk", "n": "bhjm", "o": "iplk",
    "p": "ol", "q": "wa", "r": "edft", "s": "aewdxz", "t": "rfgy",
    "u": "yhij", "v": "cfgb", "w": "qase", "x": "zsdc", "y": "tghu", "z": "asx",
}


def _add_typos(text: str) -> str:
    """6% chance per word to introduce a realistic typo (adjacent-key swap or missing letter)."""
    words = text.split()
    out = []
    for w in words:
        if len(w) >= 3 and random.random() < 0.06:
            typo_type = random.random()
            idx = random.randint(0, len(w) - 1)
            ch = w[idx].lower()
            if typo_type < 0.45 and ch in _ADJACENT:
                # Replace with an adjacent key
                replacement = random.choice(_ADJACENT[ch])
                w = w[:idx] + replacement + w[idx + 1:]
            elif typo_type < 0.70:
                # Drop a letter
                w = w[:idx] + w[idx + 1:]
            else:
                # Double a letter
                w = w[:idx] + w[idx] + w[idx:]
        out.append(w)
    return " ".join(out)

def _clean(text: str) -> str:
    text = text.strip()
    # Chat is single-line — keep only the first line
    text = text.split("\n")[0].strip()
    # Strip markdown horizontal rule and everything after (model reasoning separator)
    m = _HR_RE.search(text)
    if m:
        text = text[:m.start()].strip()
    # Strip LLM meta-label prefixes like "React: " "REACTION - " "Message: "
    text = _LABEL_RE.sub("", text).strip()
    # Reject URLs and meta-commentary that leaked from the model
    if _FILTER_RE.search(text):
        return ""
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
    text = _randomize_caps(text)
    text = _add_typos(text)
    return text.strip()


ARCHETYPES = [
    {
        "name": "hype",
        "style": 'Hype viewer. Short energy bursts. Use emojis and emotes freely — spam them. NO greetings, NO questions. Examples: "LETS GO 🔥", "W 💀💀💀", "POG", "bro no way 😭😭", "KEKW", "AYOOO 🗣️🗣️🗣️", "NOOO 💀", "he cooked 🐐", "💀💀💀", "🔥🔥🔥🔥", "🗣️🗣️🗣️🗣️🗣️".',
        "weight": 0.15,
    },
    {
        "name": "casual",
        "style": 'Chill viewer, mostly lowercase, mixed caps. Use emojis sometimes. NO greetings, NO questions. Examples: "lol 💀", "ngl tho", "bro what 😭", "same", "wild", "welp", "nah", "L", "mid", "😭😭😭", "👀".',
        "weight": 0.30,
    },
    {
        "name": "react",
        "style": 'Reacts briefly to what just happened. Use emojis. NO questions, NO greetings. Examples: "wait that worked?? 💀", "bro same lmao", "this guy 🗣️", "he cooked 🐐🐐", "sold", "real 💯", "😤😤", "🔥🔥🔥".',
        "weight": 0.20,
    },
    {
        "name": "lurker",
        "style": 'Rarely talks. When you do, 1-3 words or pure emoji spam. NO greetings, NO questions. Examples: "lol", "gg", "nah", "W", "💀", "👀", "🔥🔥", "😭😭😭".',
        "weight": 0.15,
    },
    {
        "name": "questioner",
        "style": 'Curious casual viewer. Ask ONE short question about what just happened — genuinely curious, not sarcastic. Under 8 words. NO greetings. Examples: "wait did it land tho", "bro where was this 👀", "nah fr tho?", "did he make it 😭", "wait really?? 💀", "how tho", "bro what happened next".',
        "weight": 0.20,
    },
]

_BASE_PROMPT = """\
You are a real Twitch viewer in chat. {style}

Output ONLY your chat message — nothing else. No labels, no quotes, no explanations, no reasoning.
- 1-6 words usually. Absolute max 80 characters.
- ALL CAPS ok. Repeated letters ok (AYOOO, NOOOOO). Mixed caps fine.
- Emojis and Twitch emotes welcome — spam the same one multiple times if hyped: 💀💀💀 or 🗣️🗣️🗣️🗣️ or 🔥🔥
- Sometimes your ENTIRE message can be just emoji spam: "💀💀💀" or "🗣️🗣️🗣️🗣️🗣️"
- No greetings. No advice. No hashtags.
- React specifically to what the streamer said — mention what actually happened, not just generic hype.
- Never reveal you are a bot or AI. Never explain your response.
- Good: REAL, L 💀, bro lol, ngl, W 🔥, welp, BRUH, he cooked 🐐, 💀💀💀, 🗣️🗣️🗣️, "wait did it land tho 👀"
- Bad: greetings, meta-commentary, parenthetical explanations, ignoring what was said
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
        get_transcript: "Callable[[], str] | None" = None,
    ):
        self.idx = idx
        self.archetype = archetype
        self._send = send_fn
        self._loop = loop
        self._stream_info = stream_info
        self._get_transcript = get_transcript or (lambda: "")
        self._cooldown = random.uniform(60, 120) #Message Cooldown
        self._prob = random.uniform(0.10, 0.20) #Chance Bots respond to Audio in the stream
        self._last_sent = 0.0
        self._join_delay = random.uniform(0, _JOIN_WINDOW)
        self._active = False
        self._system = _BASE_PROMPT.format(style=archetype["style"])

    def _stream_context(self) -> str:
        """Returns stream game/category as context — NOT the raw title to avoid bots echoing it."""
        if not self._stream_info:
            return ""
        info = self._stream_info.snapshot()
        if info.get("category"):
            return f" (playing {info['category']})"
        streamer = info.get("streamer") or config.TWITCH_CHANNEL
        return f" (stream: {streamer})" if streamer else ""

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
                if not text:
                    return
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
            ctx = self._stream_context()
            recent = self._get_transcript()
            system = (
                f"You are a Twitch viewer. {self.archetype['style']} "
                "Send ONE short chat message, 1-8 words. Output ONLY the message, no quotes. "
                "Real examples: lol, W, bro what, ngl, AYOOO, he cooked, same, nah, mid."
            )
            prompt = (
                f'The streamer recently said: "{recent}". Say something in chat about it{ctx}.'
                if recent else f"Say something in chat{ctx}."
            )
            text = llm.complete(system, prompt)
            if not text or text.upper() == "SKIP":
                text = "W"
            text = _clean(text) or "W"
            print(f"[Viewer {self.idx}] → {text} (highlight)")
            token_idx = self.idx - 1
            token = config.TWITCH_TOKENS[token_idx] if token_idx < len(config.TWITCH_TOKENS) else ""
            if not rewards.redeem(token, config.HIGHLIGHT_REWARD_ID, text):
                print(f"[Highlight] Redemption failed (reward_id={config.HIGHLIGHT_REWARD_ID!r}, token=…{token[-6:]}) — falling back to chat")
                future = asyncio.run_coroutine_threadsafe(self._send(text), self._loop)
                future.result(timeout=10)
        except Exception as e:
            print(f"[Viewer {self.idx}] Highlight error: {e}")

    def _spontaneous(self):
        try:
            # 10% chance: pure emoji burst without hitting the LLM
            if random.random() < 0.10:
                emoji = random.choice(_SPAM_EMOJIS)
                text = emoji * random.randint(2, 4)
                print(f"[Viewer {self.idx} / {self.archetype['name']}] → {text}")
                self._dispatch(text)
                return
            recent = self._get_transcript()
            ctx = self._stream_context()
            if recent:
                # Recent transcript exists — react to it specifically
                system = self._system
                user_prompt = (
                    f'The streamer recently said: "{recent}". '
                    f"React to this specifically{ctx}. One short message, no quotes."
                )
            else:
                # No recent context — lean toward asking what's going on
                system = (
                    self._system
                    + "\nTip: with nothing specific to react to, ask a short genuine question about what's happening (e.g. \"wait what's going on\", \"bro what happened\", \"what did I miss\")."
                )
                user_prompt = (
                    f"You've been watching the stream{ctx}. "
                    "React to something happening, or ask a short question about what's going on."
                )
            text = llm.complete(system, user_prompt)
            if text and text.upper() != "SKIP":
                text = _clean(text)
                if not text:
                    return
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
            # 15% chance: skip LLM entirely and just spam an emoji
            if random.random() < 0.15:
                emoji = random.choice(_SPAM_EMOJIS)
                text = emoji * random.randint(2, 5)
                print(f"[Viewer {self.idx} / {self.archetype['name']}] → {text}")
                self._dispatch(text)
                return
            ctx = self._stream_context()
            text = llm.complete(
                self._system,
                f'Streamer just said: "{transcript}". React specifically to what was said — pick something concrete from it{ctx}.',
            )
            if text and text.upper() != "SKIP":
                text = _clean(text)
                if not text:
                    return
                print(f"[Viewer {self.idx} / {self.archetype['name']}] → {text}")
                self._dispatch(text)
                self._maybe_follow_up(text)
        except Exception as e:
            print(f"[Viewer {self.idx}] Error: {e}")

    def _respond_to_chat(self, username: str, message: str):
        time.sleep(random.uniform(0.5, 2.0))
        try:
            ctx = self._stream_context()
            text = llm.complete(
                self._system,
                f'Viewer "{username}" just said: "{message}". React to what they said{ctx}.',
            )
            if text and text.upper() != "SKIP":
                text = _clean(text)
                if not text:
                    return
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
        self._recent_transcripts: list[tuple[float, str]] = []  # (monotonic_time, text)
        self._transcript_lock = threading.Lock()

        weights = [a["weight"] for a in ARCHETYPES]
        self._viewers = [
            ViewerPersona(
                i + 1,
                random.choices(ARCHETYPES, weights=weights)[0],
                send_fns[i],
                loop,
                stream_info,
                get_transcript=self.get_last_transcript,
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

    def get_last_transcript(self) -> str:
        """Return all transcripts from the last 30 seconds joined as one string."""
        now = time.monotonic()
        with self._transcript_lock:
            recent = [t for ts, t in self._recent_transcripts if now - ts <= 30]
        return " ".join(recent)

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
            now = time.monotonic()
            with self._transcript_lock:
                self._recent_transcripts.append((now, transcript))
                # Drop anything older than 30 seconds
                self._recent_transcripts = [(ts, t) for ts, t in self._recent_transcripts if now - ts <= 30]
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
