from discord.ext import tasks
import discord
from discord.ext import commands
from discord import app_commands
from ..utils.api import ChiefDelphiAPI
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

                    await channel.send(content=f"Post found with **{matched_triggers[0]["matches"][0]}**", embed=embed)

        except Exception as e:
            print(f"Error checking posts: {e}")

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

    @commands.command(name="sync_slash")
    @commands.has_permissions(administrator=True)
    async def sync_slash(self, ctx: commands.Context):
        await self.bot.tree.sync()
        await ctx.send("Slash commands synced!")

    @commands.Cog.listener()
    async def on_message(self, message):
        """Listen for messages containing #post_id and respond with the post embed."""
        # Ignore messages from bots (including self)
        if message.author.bot:
            return

        # Look for #number pattern
        import re
        if matches := re.findall(r'#(\d+)', message.content):
            print(f"Found post IDs in message: {matches}")  # Debug print
            for post_id in matches[:3]:  # Limit to first 3 matches to prevent spam
                try:
                    post = await self.cd_api.get_post(post_id)
                    if not post:
                        print(f"No post found for ID: {post_id}")  # Debug print
                        continue

                    # Clean up HTML tags from preview
                    preview = re.sub(r'<[^>]+>', '', post['preview'])
                    preview = re.sub(r'\s+', ' ', preview).strip()

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

                    embed.add_field(name="Author", value=post['author'], inline=True)
                    embed.add_field(name="Post ID", value=post['id'], inline=True)

                    # Check for image in preview
                    if '<img' in post['preview']:
                        if img_match := re.search(
                            r'src="([^"]+)"', post['preview']
                        ):
                            embed.set_thumbnail(url=img_match.group(1))

                    await message.channel.send(embed=embed)
                    print(f"Sent embed for post ID: {post_id}")  # Debug print

                except Exception as e:
                    print(f"Error fetching post {post_id}: {e}")

    @commands.command(name="sync")
    @commands.has_permissions(administrator=True)
    async def sync(self, ctx: commands.Context):
        """Sync the bot's commands with Discord."""
        await self.bot.tree.sync()
        await ctx.send("Commands synced!")


async def setup(bot):
    await bot.add_cog(ChiefDelphi(bot))
