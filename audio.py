import queue
import subprocess
import threading
import time

from streamlink import Streamlink

import config

SAMPLE_RATE = 16000
CHUNK_SECONDS = 5
CHUNK_BYTES = SAMPLE_RATE * CHUNK_SECONDS * 2  # int16 = 2 bytes per sample
RETRY_INTERVAL = 30  # seconds between retries when stream is offline


class AudioCapture:
    def __init__(self):
        self._queue: queue.Queue[bytes] = queue.Queue(maxsize=5)
        self._running = False

    @property
    def queue(self) -> queue.Queue:
        return self._queue

    def start(self):
        self._running = True
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._running = False

    def _run(self):
        session = Streamlink()
        # Note: viewer chat tokens (chat:read/edit) can't authenticate streamlink.
        # Public streams don't require auth — a streamer-scoped token goes in TWITCH_STREAMER_TOKEN.
        streamer_token = config.TWITCH_STREAMER_TOKEN
        if streamer_token:
            try:
                session.set_plugin_option(
                    "twitch", "api-header",
                    f"Authorization=OAuth {streamer_token}",
                )
            except AttributeError:
                session.options.set(
                    "http-headers",
                    f"Authorization=OAuth {streamer_token}",
                )

        while self._running:
            print(f"[Audio] Connecting to twitch.tv/{config.TWITCH_CHANNEL}...")
            try:
                streams = session.streams(f"https://twitch.tv/{config.TWITCH_CHANNEL}")
            except Exception as e:
                print(f"[Audio] Failed to get streams: {e} — retrying in {RETRY_INTERVAL}s")
                time.sleep(RETRY_INTERVAL)
                continue

            if not streams:
                print(f"[Audio] Channel is offline — retrying in {RETRY_INTERVAL}s")
                time.sleep(RETRY_INTERVAL)
                continue

            stream = (
                streams.get("audio_only")
                or streams.get("worst")
                or next(iter(streams.values()))
            )

            print("[Audio] Opening stream...")
            try:
                fd = stream.open()
            except Exception as e:
                print(f"[Audio] Could not open stream: {e} — retrying in {RETRY_INTERVAL}s")
                time.sleep(RETRY_INTERVAL)
                continue

            _ffmpeg = (
                r"C:\Users\blaze\AppData\Local\Microsoft\WinGet\Packages"
                r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
                r"\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
            )
            ff = subprocess.Popen(
                [
                    _ffmpeg, "-loglevel", "quiet",
                    "-i", "pipe:0",
                    "-f", "s16le", "-ar", str(SAMPLE_RATE), "-ac", "1",
                    "pipe:1",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )

            def _feed():
                try:
                    while self._running:
                        chunk = fd.read(65536)
                        if not chunk:
                            break
                        ff.stdin.write(chunk)
                except Exception as e:
                    print(f"[Audio] Feed error: {e}")
                finally:
                    try:
                        ff.stdin.close()
                    except Exception:
                        pass
                    fd.close()

            threading.Thread(target=_feed, daemon=True).start()

            print("[Audio] Capturing audio...")
            buf = b""
            while self._running:
                data = ff.stdout.read(4096)
                if not data:
                    break
                buf += data
                while len(buf) >= CHUNK_BYTES:
                    chunk, buf = buf[:CHUNK_BYTES], buf[CHUNK_BYTES:]
                    if not self._queue.full():
                        self._queue.put(chunk)

            ff.terminate()
            print(f"[Audio] Stream ended — retrying in {RETRY_INTERVAL}s")
            time.sleep(RETRY_INTERVAL)
