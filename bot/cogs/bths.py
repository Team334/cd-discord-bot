import discord
from discord.ext import commands
from datetime import datetime
from ..utils.bths import BTHSCalendar

class BTHS(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.calendar = BTHSCalendar()

    @commands.hybrid_command(
        name="cycleday",
        description="Get the current cycle day or the cycle day for a specific date"
    )
    async def cycle_day(self, ctx):
        if cycle_day := self.calendar.get_cycle_day():
            await ctx.send(f"Today is Day {cycle_day}")
        else:
            await ctx.send("No cycle day information available for today")

    @commands.hybrid_command(
        name="schedule",
        aliases=["week", "events"],
        description="Get the schedule for the upcoming week"
    )
    async def schedule(self, ctx):
        week_schedule = self.calendar.get_week_schedule()
        
        if not week_schedule:
            await ctx.send("No schedule information available")
            return

        embed = discord.Embed(
            title="BTHS Weekly Schedule",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        for day in week_schedule:            
            embed.add_field(
                name=day['date'].strftime('%A, %B %d'),
                value=f"Day Cycle {day['cycle_day']}\n{day['description']}",
                inline=False
            )

        await ctx.send(embed=embed)


    @commands.hybrid_command(
        name="bths_search",
        description="Search for BTHS events"
    )
    async def search(self, ctx, query: str):
        results = self.calendar.search_events(query)

        if not results:
            await ctx.send(f"No events found matching '{query}'")
            return

        embed = discord.Embed(
            title=f"Search Results for `{query}`",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        for event in results[:5]:  # Limit to 5 results
            title = event['title']

            # Format the description with the date
            if event['date']:
                date_str = event['date'].strftime('%m/%d/%Y')
                value = date_str
                if event['description']:
                    value += f"\n{event['description']}"
            else:
                value = event['description'] or "No description available"

            if len(value) > 1024:
                value = f"{value[:1021]}..."

            embed.add_field(
                name=title,
                value=value,
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="day_cycle",
        aliases=["day", "cycle"],
        description="Get the cycle day for a specific date (MM/DD/YYYY) or today's date"
    )
    async def day_cycle(self, ctx, date_str: str = None):
        try:
            if date_str is None:
                # Use today's date if no date provided
                date = datetime.now()
            else:
                # Parse the provided date string (expecting MM/DD/YYYY format)
                try:
                    date = datetime.strptime(date_str, '%m/%d/%Y')
                except ValueError:
                    await ctx.send("Please use the format MM/DD/YYYY (e.g., 02/14/2025)")
                    return

            if cycle_day := self.calendar.get_cycle_day(date):
                await ctx.send(f"The cycle day for {date.strftime('%m/%d/%Y')} is Day {cycle_day}")
            else:
                if events := self.calendar.search_events(
                    date.strftime('%m/%d/%Y')
                ):
                    if special_events := [
                        event for event in events if 'Day' not in event['title']
                    ]:
                        event_names = ', '.join(event['title'] for event in special_events)
                        await ctx.send(f"No cycle day on {date.strftime('%m/%d/%Y')} - {event_names}")
                        return

                await ctx.send(f"No cycle day information available for {date.strftime('%m/%d/%Y')}")

        except ValueError as e:
            await ctx.send(f"Error: {str(e)}\nPlease use the format MM/DD/YYYY (e.g., 02/14/2025)")

async def setup(bot):
    await bot.add_cog(BTHS(bot))
