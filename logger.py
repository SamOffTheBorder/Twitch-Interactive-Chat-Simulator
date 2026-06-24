import datetime
import json

LOG_FILE = "viewer_log.jsonl"


def log_event(label: str, channel: str, event: str, **kwargs):
    record = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "viewer": label,
        "channel": channel,
        "event": event,
        **kwargs,
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
