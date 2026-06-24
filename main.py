import asyncio
import os
import sys
import subprocess
import threading
import time
import urllib.request

import config
from audio import AudioCapture
from chat import ChatBot, get_real_chatters
from responder import Responder
from stream_info import StreamInfo
from transcriber import Transcriber
from tts_sender import TTSSender


def _ensure_ollama() -> bool:
    """Start Ollama if it's not running, wait for it, then verify the model responds."""
    if not config.LOCAL_LLM_MODEL:
        return False

    def _ping() -> bool:
        try:
            urllib.request.urlopen("http://localhost:11434", timeout=2)
            return True
        except Exception:
            return False

    if _ping():
        print("[Ollama] Already running")
    else:
        print("[Ollama] Not running — starting...")
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        for _ in range(20):
            time.sleep(1)
            if _ping():
                print("[Ollama] Started")
                break
        else:
            print("[Ollama] Failed to start — will fall back to OpenRouter")
            return False

    # Quick smoke test
    print(f"[Ollama] Verifying model '{config.LOCAL_LLM_MODEL}'...")
    try:
        import llm
        result = llm.complete("You are a test.", "Reply with just the word: OK", max_tokens=5)
        if result:
            print(f"[Ollama] Model ready — test response: {result!r}")
            return True
        else:
            print("[Ollama] Model returned empty — will fall back to OpenRouter")
            return False
    except Exception as e:
        print(f"[Ollama] Model check failed ({e}) — will fall back to OpenRouter")
        return False


def _print_diag(responder: Responder, bots: list[ChatBot], stream_info: StreamInfo):
    print("\n[Diagnostics] ══════════════════════════════")
    print(f"  TWITCH_CHANNEL     : {config.TWITCH_CHANNEL}")
    print(f"  OPENROUTER_MODEL   : {config.OPENROUTER_MODEL}")
    print(f"  OPENROUTER_FALLBACK: {config.OPENROUTER_FALLBACK_MODEL}")
    print(f"  TTS_INTERVAL       : {config.TTS_MIN_INTERVAL}s – {config.TTS_MAX_INTERVAL}s")
    print(f"  OPENROUTER_API_KEY : {'set' if config.OPENROUTER_API_KEY else 'MISSING'}")
    print()
    info = stream_info.snapshot()
    real_chatters = get_real_chatters()
    print(f"  Twitch viewers     : {info['viewer_count']} (live from Helix API)")
    print(f"  Real chatters      : {len(real_chatters)} unique this session" + (f" — {', '.join(sorted(real_chatters))}" if real_chatters else ""))
    nicks = [b.nick for b in bots if b.nick]
    print(f"  Bot accounts       : {len(nicks)} connected — {', '.join(nicks) if nicks else 'none yet'}")
    responder.print_status()
    print("[Diagnostics] ══════════════════════════════\n")


_HELP = """
[Commands] ══════════════════════════════
  test      — force a random viewer to send a chat message right now
  tts       — fire a TTS channel point message immediately
  highlight — force a random viewer to attempt Highlight My Message
  diag      — show config, bot connections, and viewer status
  stop      — shut everything down
  restart   — restart the whole bot
  help      — show this menu
[Commands] ══════════════════════════════
"""


def _command_loop(responder: Responder, tts: TTSSender, bots: list[ChatBot], stream_info: StreamInfo):
    print(_HELP)
    while True:
        try:
            cmd = input().strip().lower()
            if cmd == "test":
                responder.trigger_test()
            elif cmd == "tts":
                print("[Commands] Firing TTS message...")
                threading.Thread(target=tts._fire, daemon=True).start()
            elif cmd == "highlight":
                print("[Commands] Firing Highlight My Message...")
                threading.Thread(target=responder.trigger_highlight, daemon=True).start()
            elif cmd == "diag":
                _print_diag(responder, bots, stream_info)
            elif cmd == "stop":
                print("[Commands] Stopping...")
                os._exit(0)
            elif cmd == "restart":
                print("[Commands] Restarting...")
                subprocess.Popen([sys.executable] + sys.argv)
                os._exit(0)
            elif cmd in ("help", "h", "?"):
                print(_HELP)
            elif cmd:
                print("[Commands] Unknown command. Type 'help' for the list.")
        except EOFError:
            break


async def main():
    config.validate()
    _ensure_ollama()

    loop = asyncio.get_running_loop()
    bot_nicks: set[str] = set()
    bots = [ChatBot(token, bot_nicks) for token in config.TWITCH_TOKENS]
    send_fns = [bot.send for bot in bots]

    stream_info = StreamInfo()
    capture = AudioCapture()
    transcriber = Transcriber(capture.queue)
    responder = Responder(transcriber.queue, send_fns, loop, stream_info)
    tts = TTSSender(send_fns, loop)

    # Wire incoming chat messages to responder (ignores our own bot accounts)
    for bot in bots:
        bot.on_chat_message = lambda u, c: responder.trigger_chat(u, c)

    stream_info.start()
    capture.start()
    transcriber.start()
    responder.start()
    tts.start()

    threading.Thread(target=_command_loop, args=(responder, tts, bots, stream_info), daemon=True).start()

    print(f"[Main] Starting {len(bots)} viewer(s) on twitch.tv/{config.TWITCH_CHANNEL}")
    print("[Main] Listening... (Ctrl+C to stop)")
    await asyncio.gather(*[bot.start() for bot in bots])


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Main] Stopped.")
