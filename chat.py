import threading
from twitchio.ext import commands

import config

_real_chatters: set[str] = set()
_chatters_lock = threading.Lock()


def get_real_chatters() -> set[str]:
    with _chatters_lock:
        return set(_real_chatters)


class ChatBot(commands.Bot):
    def __init__(self, token: str, bot_nicks: set[str]):
        super().__init__(
            token=token,
            prefix="!",
            initial_channels=[config.TWITCH_CHANNEL],
        )
        self._bot_nicks = bot_nicks
        self.on_chat_message = None  # set by main.py after responder is ready

    async def event_ready(self):
        self._bot_nicks.add(self.nick.lower())
        print(f"[Chat] Connected as {self.nick} to #{config.TWITCH_CHANNEL}")

    async def event_message(self, message):
        if message.echo:
            return
        if message.author:
            username = message.author.name.lower()
            if username not in self._bot_nicks:
                with _chatters_lock:
                    _real_chatters.add(username)
                if self.on_chat_message:
                    self.on_chat_message(username, message.content)
        await self.handle_commands(message)

    async def event_error(self, error: Exception, data=None):
        print(f"[Chat] Error: {error}")

    async def send(self, text: str):
        # Send directly through this bot's own IRC connection to avoid the
        # shared channel-object bug where all bots post as the same account.
        await self._connection.send(f"PRIVMSG #{config.TWITCH_CHANNEL.lower()} :{text}\r\n")
