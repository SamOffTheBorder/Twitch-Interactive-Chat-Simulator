import queue
import re
import threading

import numpy as np
import whisper

SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2  # int16

_FILLERS = {
    "uh", "um", "uh-huh", "uhh", "umm", "hmm", "hm", "huh",
    "like", "you know", "you know what i mean", "i mean",
    "so", "well", "actually", "basically", "literally",
    "right", "okay", "ok", "alright", "yeah", "yep", "yup",
    "ah", "oh", "ahh", "ohh", "eh",
    "kind of", "sort of", "kinda", "sorta",
    "just", "really", "very", "quite",
}

_FILLER_RE = re.compile(
    r"\b(" + "|".join(re.escape(f) for f in sorted(_FILLERS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def _strip_fillers(text: str) -> str:
    cleaned = _FILLER_RE.sub("", text)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip().strip(",").strip()
    return cleaned


class Transcriber:
    def __init__(self, audio_queue: queue.Queue):
        self._audio_q = audio_queue
        self._text_q: queue.Queue[str] = queue.Queue()
        self._model = None

    @property
    def queue(self) -> queue.Queue:
        return self._text_q

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        print("[Transcriber] Loading Whisper model (base.en)...")
        self._model = whisper.load_model("base.en")
        print("[Transcriber] Ready — waiting for audio chunks...")
        while True:
            pcm: bytes = self._audio_q.get()
            try:
                audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
                result = self._model.transcribe(audio, language="en", fp16=False)
                text = result.get("text", "").strip()
                if not text:
                    continue
                cleaned = _strip_fillers(text)
                if cleaned:
                    print(f"[Transcript] {text!r} → {cleaned!r}")
                    self._text_q.put(cleaned)
            except Exception as e:
                print(f"[Transcriber] Error: {e}")
