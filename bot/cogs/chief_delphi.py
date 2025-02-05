from discord.ext import tasks
import discord
from discord.ext import commands
from discord import app_commands
from ..utils import ChiefDelphiAPI
from typing import Optional, Literal
import json
from pathlib import Path


class ChiefDelphi(commands.Cog):
    """Monitor and search Chief Delphi forums for posts and updates."""

    def __init__(self, bot):
        self.bot = bot
        self.cd_api = ChiefDelphiAPI()
        self.triggers = self.bot.config['triggers']
        self.check_posts.start()

    def cog_unload(self):
        self.check_posts.cancel()

    @tasks.loop(seconds=15)
    async def check_posts(self):
        """Check for new posts and send notifications."""
        try:
            posts = await self.cd_api.get_recent_posts()

            channel = self.bot.get_channel(int(self.bot.config['channel_id']))
            if not channel:
                return

            for post in posts:
                # Clean up HTML tags from preview
                import re
                preview = re.sub(r'<[^>]+>', '', post['preview'])  # Remove HTML tags
                preview = re.sub(r'\s+', ' ', preview).strip()      # Clean up whitespace

                # Check for triggers
                matched_triggers = self.cd_api.check_triggers(post, [self.triggers])

                # Only send message if triggers match or if there are no triggers configured
                if matched_triggers or not (self.triggers.get('keywords') or self.triggers.get('authors')):
                    # Create embed
                    embed = discord.Embed(
                        title=post['title'],
                        url=post['thread_url'],
                        description=(
                            f"{preview[:1800]}..."
                            if len(preview) > 1800
                            else preview
                        ),
                        color=discord.Color.blue(),
                    )

                    embed.add_field(name="Author", value=f"**[{post['author']}](https://chiefdelphi.com/u/{post['author'].replace(' ', '')}/summary)**", inline=True)
                    embed.add_field(name="Post ID", value=post['id'], inline=True)

                    # Check for image in preview
                    if '<img' in post['preview']:
                        if img_match := re.search(
                            r'src="([^"]+)"', post['preview']
                        ):
                            embed.set_thumbnail(url=img_match.group(1))

                    await channel.send(content=f"Post found with **{matched_triggers[0]['matches'][0]}**", embed=embed)

        except Exception as e:
            raise e

    @commands.hybrid_command(name="search")
    @app_commands.describe(
        query="The keyword or author name to search for",
        limit="Maximum number of results (default: 10)",
        search_type="Where to search: title, preview, author, or all"
    )
    async def search(
        self, 
        ctx: commands.Context, 
        query: str, 
        limit: Optional[int] = 10,
        search_type: Optional[Literal["title", "preview", "author", "all"]] = "all"
    ):
        """Search Chief Delphi posts by keyword or author name."""
        await ctx.defer()  # Defer the response since this might take a moment

        try:
            # Get search results from the API
            results = await self.cd_api.search_posts(query, limit, search_type)
            
            if not results:
                await ctx.send(f"No results found for '{query}'")
                return

            # Create embed
            embed = discord.Embed(
                title=f"Found {len(results)} matches for '{query}'",
                color=discord.Color.blue()
            )

            # Add results to embed
            for post in results:
                embed.add_field(
                    name=f"**{post['title'][:256]}**",
                    value=f" By **[{post['author']}](https://chiefdelphi.com/u/{post['author'].replace(' ', '')}/summary)** | [Link]({post['thread_url']}) | {post['id']}",
                    inline=False
                )

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"Error performing search: {str(e)}")

    @check_posts.before_loop
    async def before_check_posts(self):
        """Wait for the bot to be ready before starting the task."""
        await self.bot.wait_until_ready()

    @commands.hybrid_group(name="cd")
    async def cd(self, ctx: commands.Context):
        """Chief Delphi commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Available commands: `cd config channel/refresh`, `cd trigger add/remove/list`, `cd search`")

    def _save_config(self):
        """Save the current configuration to file."""
        config_path = Path('config.json')
        with config_path.open('w') as f:
            json.dump(self.bot.config, f, indent=4)
  
    @commands.command(name="sync")
    @commands.has_permissions(administrator=True)
    async def sync(self, ctx: commands.Context):
        """Sync the bot's commands with Discord."""
        await self.bot.tree.sync()
        await ctx.send("Commands synced!")

    @cd.group(name="config")
    @commands.has_permissions(administrator=True)
    async def cd_config(self, ctx: commands.Context):
        """Configure bot settings."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Available commands: `channel`, `refresh`")

    @cd_config.command(name="channel")
    @commands.has_permissions(administrator=True)
    async def set_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set the notification channel."""
        self.bot.config['channel_id'] = str(channel.id)
        self._save_config()
        await ctx.send(f"Notification channel set to {channel.mention}")

    @cd_config.command(name="refresh")
    @commands.has_permissions(administrator=True)
    async def set_refresh(self, ctx: commands.Context, seconds: int):
        """Set the refresh rate in seconds."""
        if seconds < 5:
            await ctx.send("Refresh rate must be at least 5 seconds")
            return
        
        self.bot.config['triggers']['refresh_rate'] = seconds * 1000  # Convert to milliseconds
        self._save_config()
        
        # Restart the check_posts task with new refresh rate
        self.check_posts.cancel()
        self.check_posts.change_interval(seconds=seconds)
        self.check_posts.start()
        
        await ctx.send(f"Refresh rate set to {seconds} seconds")

    @cd.group(name="trigger")
    @commands.has_permissions(administrator=True)
    async def cd_trigger(self, ctx: commands.Context):
        """Manage notification triggers."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Available commands: `add`, `remove`, `list`")

    @cd_trigger.command(name="add")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(
        trigger_type="Type of trigger to add",
        value="Keyword or author name to add"
    )
    async def add_trigger(
        self, 
        ctx: commands.Context, 
        trigger_type: Literal["keyword", "author"],
        value: str
    ):
        """Add a keyword or author trigger."""
        key = "keywords" if trigger_type == "keyword" else "authors"
        
        if value in self.bot.config['triggers'][key]:
            await ctx.send(f"{trigger_type.title()} '{value}' already exists")
            return
            
        self.bot.config['triggers'][key].append(value)
        self._save_config()
        await ctx.send(f"Added {trigger_type} trigger: {value}")

    @cd_trigger.command(name="remove")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(
        trigger_type="Type of trigger to remove",
        value="Keyword or author name to remove"
    )
    async def remove_trigger(
        self, 
        ctx: commands.Context, 
        trigger_type: Literal["keyword", "author"],
        value: str
    ):
        """Remove a keyword or author trigger."""
        key = "keywords" if trigger_type == "keyword" else "authors"
        
        if value not in self.bot.config['triggers'][key]:
            await ctx.send(f"{trigger_type.title()} '{value}' not found")
            return
            
        self.bot.config['triggers'][key].remove(value)
        self._save_config()
        await ctx.send(f"Removed {trigger_type} trigger: {value}")

    @cd_trigger.command(name="list")
    async def list_triggers(self, ctx: commands.Context):
        """List all current triggers."""
        embed = discord.Embed(
            title="Current Triggers",
            color=discord.Color.blue()
        )
        
        keywords = self.bot.config['triggers']['keywords']
        authors = self.bot.config['triggers']['authors']
        
        embed.add_field(
            name="Keywords",
            value="\n".join(keywords) if keywords else "None",
            inline=False
        )
        embed.add_field(
            name="Authors",
            value="\n".join(authors) if authors else "None",
            inline=False
        )
        
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(ChiefDelphi(bot))
