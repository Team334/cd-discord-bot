from __future__ import annotations

import contextlib
import json
from traceback import format_exception

from aiohttp import ClientSession
from dotenv import load_dotenv
from discord.ext import commands
import discord
import os
import datetime
from discord import Embed
from typing import Optional, Mapping

load_dotenv()

__initial_extension__ = [
    "bot.cogs.chief_delphi"
]

__utils_extension__ = [
    "jishaku",
    # "bot.cogs.handles"
]

def get_prefix(bot, message):
    prefixes = [">", "?", ".", "-", "cd!", "CD!", "Cd!", "CD!", "cD!", "cd?", "CD?", "Cd?", "CD?", "cD?"]
    return commands.when_mentioned_or(*prefixes)(bot, message)

class CustomHelpCommand(commands.HelpCommand):
    """Custom help command for the bot."""
    
    async def send_bot_help(self, mapping: Mapping[Optional[commands.Cog], list[commands.Command]]):
        """Shows all bot commands."""
        embed = Embed(title="Bot Commands", color=discord.Color.blue())
        
        for cog, command_list in mapping.items():
            if not command_list or (cog and cog.qualified_name == "Jishaku"):
                continue

            name = cog.qualified_name if cog else "No Category"
            filtered = await self.filter_commands(command_list, sort=True)
            if filtered:
                description = cog.description if cog and cog.description else "No description"
                value = "\n".join(f"`{c.name}` - {c.short_doc or 'No description'}" for c in filtered)
                embed.add_field(name=f"{name}: {description}", value=value, inline=False)
        
        await self.get_destination().send(embed=embed)

    async def send_cog_help(self, cog: commands.Cog):
        """Shows help for a specific cog."""
        embed = Embed(
            title=f"{cog.qualified_name} Commands",
            description=cog.description or "No description",
            color=discord.Color.blue()
        )
        
        filtered = await self.filter_commands(cog.get_commands(), sort=True)
        for command in filtered:
            embed.add_field(
                name=command.name,
                value=command.help or "No description",
                inline=False
            )
        
        await self.get_destination().send(embed=embed)

    async def send_command_help(self, command: commands.Command):
        """Shows help for a specific command."""
        embed = Embed(
            title=f"Command: {command.qualified_name}",
            description=command.help or "No description",
            color=discord.Color.blue()
        )
        
        usage = f"{self.context.clean_prefix}{command.qualified_name}"
        if command.signature:
            usage += f" {command.signature}"
        embed.add_field(name="Usage", value=f"`{usage}`", inline=False)
        
        if command.aliases:
            embed.add_field(
                name="Aliases",
                value=", ".join(f"`{alias}`" for alias in command.aliases),
                inline=False
            )
        
        await self.get_destination().send(embed=embed)

    async def send_group_help(self, group: commands.Group):
        """Shows help for a command group."""
        embed = Embed(
            title=f"Group: {group.qualified_name}",
            description=group.help or "No description",
            color=discord.Color.blue()
        )
        
        filtered = await self.filter_commands(group.commands, sort=True)
        for command in filtered:
            embed.add_field(
                name=command.name,
                value=command.help or "No description",
                inline=False
            )
        
        await self.get_destination().send(embed=embed)

class Bot(commands.AutoShardedBot):
    def __init__(self):
        super().__init__(
            activity=discord.Activity(
                type=discord.ActivityType.listening, name="cd!help"
            ),
            command_prefix=get_prefix,
            intents=discord.Intents(
                members=True,
                messages=True,
                message_content=True,
                guilds=True,
                bans=True,
            ),
            allowed_mentions=discord.AllowedMentions(
                roles=False, everyone=False, users=True
            ),
            case_sensitive=True,
            strip_after_prefix=True,
            auto_sync_commands=False,
            chunk_guilds_at_startup=False,
            help_command=CustomHelpCommand(),
        )

        self._launch_time = datetime.datetime.now(datetime.timezone.utc)
        self._config = None
        self._session = None

    async def on_ready(self):
        print("Bot is ready")

    async def _load_extensions(self):
        extensions = __initial_extension__.copy() + __utils_extension__
        for extension in extensions:
            try:
                await self.load_extension(extension)
            except Exception as e:
                print(f"Failed to load extension {extension}: {e}")

    @property
    def config(self):
        if self._config is None:
            with open('config.json', 'r') as file:
                self._config = json.load(file)
        return self._config

    @config.setter
    def config(self, value):
        self._config = value

    async def start(self, token: str, *, reconnect: bool = True) -> None:
        await self._load_extensions()
        self._session = ClientSession()
        try:
            await super().start(token, reconnect=reconnect)
        finally:
            if self._session:
                await self._session.close()

    async def on_command_error(self, ctx, error):
        with contextlib.suppress(AttributeError):
            error = error.original
        if isinstance(error, commands.CommandNotFound):
            await ctx.send("Command not found. Use `cd!help` for available commands.")
        else:
            owner = await self.fetch_user(self.owner_id) if self.owner_id else None
            if owner:
                embed = Embed(
                    title=f"Error in Command: `{ctx.command}`",
                    description=f"```py\n{''.join(format_exception(type(error), error, error.__traceback__))}```",
                    color=discord.Color.red()
                )
                await owner.send(embed=embed)
            await ctx.send("An unexpected error occurred.")

    async def close(self) -> None:
        if self._session:
            await self._session.close()
        await super().close()

    def run(self):
        if token := self.config.get('token'):
            super().run(token)
        else:
            raise ValueError("Token not found in configuration.")
