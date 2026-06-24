import datetime
import sys

import streamlink as sl_lib

import config
import logger


class StreamViewer:
    def __init__(self, channel: str, instance_id: int = 0):
        self.channel = channel
        self.instance_id = instance_id
        self._label = f"Viewer-{instance_id}"

    def watch(self):
        start = datetime.datetime.utcnow()
        label = self._label
        channel = self.channel

        print(f"[{label}] Connecting to {channel}...")
        logger.log_event(label, channel, "connecting")

        try:
            session = sl_lib.Streamlink()
            if config.TWITCH_ACCESS_TOKEN:
                session.set_plugin_option(
                    "twitch", "api-header",
                    f"Authorization=OAuth {config.TWITCH_ACCESS_TOKEN}"
                )

            streams = session.streams(f"https://twitch.tv/{channel}")
            if not streams:
                print(f"[{label}] No stream found for {channel} — is it live?")
                logger.log_event(label, channel, "no_stream")
                return

            quality = config.STREAM_QUALITY
            stream = (
                streams.get(quality)
                or streams.get("best")
                or next(iter(streams.values()), None)
            )
            if stream is None:
                print(f"[{label}] Could not select quality '{quality}' for {channel}")
                return

            fd = stream.open()
            print(f"[{label}] Watching {channel} [{quality}]")
            logger.log_event(label, channel, "watching", quality=quality)

            bytes_read = 0
            while True:
                chunk = fd.read(8192)
                if not chunk:
                    break
                bytes_read += len(chunk)

            fd.close()
            elapsed = datetime.datetime.utcnow() - start
            print(f"[{label}] Stream ended — watched {elapsed}, consumed {bytes_read:,} bytes")
            logger.log_event(label, channel, "ended", bytes_read=bytes_read)

        except KeyboardInterrupt:
            pass
        except Exception as exc:
            print(f"[{label}] Error: {exc}", file=sys.stderr)
            logger.log_event(label, channel, "error", error=str(exc))
