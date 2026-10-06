import concurrent.futures
import queue
import re
import threading
from typing import NamedTuple

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


class _ModelResult(NamedTuple):
    model_name: str
    raw: str
    cleaned: str
    word_count: int
    no_speech_prob: float


def _jaccard(a: str, b: str) -> float:
    """Word-level Jaccard similarity between two strings."""
    wa, wb = set(a.lower().split()), set(b.lower().split())
    if not wa and not wb:
        return 1.0
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def _score(r: _ModelResult, candidates: "list[_ModelResult]", max_words: int) -> float:
    """60% avg similarity to peers + 40% normalized word count."""
    peers = [c for c in candidates if c.model_name != r.model_name]
    if peers:
        avg_sim = sum(_jaccard(r.cleaned, p.cleaned) for p in peers) / len(peers)
    else:
        avg_sim = 1.0  # only one candidate, no peers to compare
    return avg_sim * 0.6 + (r.word_count / max_words) * 0.4


class EnsembleTranscriber:
    def __init__(self, audio_queue: queue.Queue, models: list[str]):
        self._audio_q = audio_queue
        self._text_q: queue.Queue[str] = queue.Queue()
        self._model_names = models
        self._models: dict[str, whisper.Whisper] = {}

    @property
    def queue(self) -> queue.Queue:
        return self._text_q

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _load_models(self):
        print(f"[Transcriber] Loading models: {', '.join(self._model_names)}")
        for name in self._model_names:
            try:
                self._models[name] = whisper.load_model(name)
                print(f"[Transcriber] {name} ready")
            except Exception as e:
                print(f"[Transcriber] Failed to load {name}: {e}")
        if not self._models:
            raise RuntimeError("[Transcriber] No models loaded — cannot transcribe")
        print(f"[Transcriber] All models ready — waiting for audio chunks...")

    def _transcribe_one(self, name: str, model: whisper.Whisper, audio: np.ndarray) -> _ModelResult | None:
        try:
            result = model.transcribe(audio, language="en", fp16=False)
            raw = (result.get("text") or "").strip()
            no_speech = result.get("segments", [{}])[0].get("no_speech_prob", 0.0) if result.get("segments") else 0.0
            cleaned = _strip_fillers(raw)
            return _ModelResult(name, raw, cleaned, len(cleaned.split()), no_speech)
        except Exception as e:
            print(f"[Transcriber] {name} error: {e}")
            return None

    def _run(self):
        self._load_models()
        models_list = list(self._models.items())
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(models_list)) as pool:
            while True:
                pcm: bytes = self._audio_q.get()
                try:
                    audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0

                    futures = {
                        pool.submit(self._transcribe_one, name, model, audio): name
                        for name, model in models_list
                    }
                    results: list[_ModelResult] = []
                    for fut in concurrent.futures.as_completed(futures):
                        r = fut.result()
                        if r is not None:
                            results.append(r)

                    # Discard results where no_speech_prob is too high
                    candidates = [r for r in results if r.no_speech_prob <= 0.6]

                    if not candidates:
                        print("[Transcript] Chunk discarded (all models: no speech detected)")
                        continue

                    # Score each candidate by consensus (avg word overlap with peers) + word count.
                    # Consensus catches when two models agree but one goes off-script.
                    max_words = max(r.word_count for r in candidates) or 1
                    winner = max(candidates, key=lambda r: _score(r, candidates, max_words))
                    if not winner.cleaned:
                        continue

                    print(f"[Transcript] {winner.model_name}: {winner.raw!r} → {winner.cleaned!r}")
                    self._text_q.put(winner.cleaned)

                except Exception as e:
                    print(f"[Transcriber] Error: {e}")
