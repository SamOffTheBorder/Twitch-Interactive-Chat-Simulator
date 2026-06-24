import asyncio
import datetime
import sys

import twitchio
from twitchio.ext import commands

import config
import logger as chatlog
import data_collector


class TwitchBot(commands.Bot):
    def __init__(self, discord_client=None):
        super().__init__(
            token=config.TWITCH_ACCESS_TOKEN,
            client_id=config.TWITCH_CLIENT_ID,
            nick=config.TWITCH_BOT_NICK,
            prefix=config.COMMAND_PREFIX,
            initial_channels=config.TWITCH_CHANNELS,
        )
        self._start_time = datetime.datetime.utcnow()
        self._discord = discord_client

    # ------------------------------------------------------------------
    # Lifecycle events
    # ------------------------------------------------------------------

    async def event_ready(self):
        print(f"[Bot] Connected as: {self.nick}")
        print(f"[Bot] Watching channels: {', '.join(config.TWITCH_CHANNELS)}")

    async def event_message(self, message: twitchio.Message):
        if message.echo:
            return

        chatlog.log_message(
            channel=message.channel.name,
            author=message.author.name,
            content=message.content,
        )

        await self._relay_to_discord(message)
        await self.handle_commands(message)

    async def _relay_to_discord(self, message: twitchio.Message):
        if not self._discord or not config.DISCORD_LOG_CHANNEL_ID:
            return
        try:
            channel = self._discord.get_channel(config.DISCORD_LOG_CHANNEL_ID)
            if channel:
                await channel.send(
                    f"`#{message.channel.name}` **{message.author.name}**: {message.content}"
                )
        except Exception as exc:
            print(f"[Discord] Relay error: {exc}", file=sys.stderr)

    async def event_command_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, commands.CommandNotFound):
            await ctx.send(f"@{ctx.author.name} Unknown command. Try !help")
            return
        print(f"[Error] {error}", file=sys.stderr)

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    @commands.command(name="help")
    async def cmd_help(self, ctx: commands.Context):
        cmds = "!help · !uptime · !hello · !ping · !stats · !lurk"
        await ctx.send(f"@{ctx.author.name} Available commands: {cmds}")

    @commands.command(name="hello")
    async def cmd_hello(self, ctx: commands.Context):
        await ctx.send(f"Hello @{ctx.author.name}! Welcome to the channel PogChamp")

    @commands.command(name="ping")
    async def cmd_ping(self, ctx: commands.Context):
        await ctx.send(f"@{ctx.author.name} Pong! Bot is online.")

    @commands.command(name="uptime")
    async def cmd_uptime(self, ctx: commands.Context):
        delta = datetime.datetime.utcnow() - self._start_time
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        await ctx.send(
            f"@{ctx.author.name} Bot uptime: {hours}h {minutes}m {seconds}s"
        )

    @commands.command(name="stats")
    async def cmd_stats(self, ctx: commands.Context):
        await ctx.send(
            f"@{ctx.author.name} Watching {len(config.TWITCH_CHANNELS)} channel(s). "
            f"Logging to {config.LOG_FILE}"
        )

    @commands.command(name="lurk")
    async def cmd_lurk(self, ctx: commands.Context):
        await ctx.send(
            f"@{ctx.author.name} is lurking! Thanks for the support SeemsGood"
        )

    @commands.command(name="so")
    async def cmd_shoutout(self, ctx: commands.Context, *, target: str = ""):
        if not target:
            await ctx.send(f"@{ctx.author.name} Usage: !so <username>")
            return
        target = target.lstrip("@")
        await ctx.send(
            f"Big shoutout to @{target}! Go check them out at twitch.tv/{target} !"
        )


# ------------------------------------------------------------------
# Optional Discord bridge
# ------------------------------------------------------------------

async def start_discord_bridge():
    if not config.DISCORD_BOT_TOKEN or not config.DISCORD_LOG_CHANNEL_ID:
        return None
    try:
        import discord

        intents = discord.Intents.default()
        client = discord.Client(intents=intents)

        @client.event
        async def on_ready():
            print(f"[Discord] Logged in as {client.user}")

        asyncio.create_task(client.start(config.DISCORD_BOT_TOKEN))
        return client
    except ImportError:
        print("[Discord] discord.py not installed — skipping bridge.")
        return None


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

async def main():
    config.validate()
    discord_client = await start_discord_bridge()
    bot = TwitchBot(discord_client=discord_client)
    await asyncio.gather(
        bot.start(),
        data_collector.run_collector(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Bot] Shutting down.")
