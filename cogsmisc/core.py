"""
Created on Dec 26, 2016

@author: andrew
"""
import random
import time
from datetime import datetime, timedelta
from math import floor

import discord
import psutil
from discord.ext import commands

from cogs5e.models.embeds import EmbedWithAuthor

PATRON_EYLESIS = 227168575469780992


class Core(commands.Cog):
    """
    Core utilty and general commands.
    """

    def __init__(self, bot):
        self.bot = bot
        self.start_time = time.monotonic()

    async def on_message(self, message):
        if message.author.id == PATRON_EYLESIS and message.content.lower().startswith("hey avrae"):
            await message.channel.send("No, I will not reseed the RNG, even if you gave me all those cookies.")
            random.seed()  # I lied

    @commands.command(hidden=True)
    async def avatar(self, ctx, user: discord.User = None):
        """Gets a user's avatar.
        Usage: !avatar <USER>"""
        if user is None:
            user = ctx.message.author
        if user.avatar_url is not "":
            await ctx.send(user.avatar_url)
        else:
            await ctx.send(user.display_name + " is using the default avatar.")

    @commands.command()
    async def ping(self, ctx):
        """Checks the ping time to the bot."""
        now = datetime.utcnow()
        pong = await ctx.send("Pong.")
        delta = datetime.utcnow() - now
        msec = floor(delta.total_seconds() * 1000)
        await pong.edit(content="Pong.\nPing = {} ms.".format(msec))

    @commands.command()
    async def invite(self, ctx):
        """Prints a link to invite Avrae to your server."""
        await ctx.send(
            "You can invite Avrae to your server here:\n"
            "https://discordapp.com/oauth2/authorize?&client_id=261302296103747584&scope=bot&permissions=36727808")

    @commands.command()
    async def donate(self, ctx):
        """Prints a link to donate to the bot developer."""
        await ctx.send("You can donate to me here:\n<https://www.paypal.me/avrae>\n\u2764")

    @commands.command(aliases=['stats', 'info'])
    async def about(self, ctx):
        """Information about the bot."""
        botStats = {}
        statKeys = ["dice_rolled_life", "spells_looked_up_life", "monsters_looked_up_life", "commands_used_life",
                    "items_looked_up_life",
                    "rounds_init_tracked_life", "turns_init_tracked_life"]
        for k in statKeys:
            botStats[k] = int(self.bot.rdb.get(k, "0"))
        embed = discord.Embed(description='Avrae, a bot to streamline D&D 5e online.')
        embed.title = "Invite Avrae to your server!"
        embed.url = "https://discordapp.com/oauth2/authorize?&client_id=261302296103747584&scope=bot&permissions=36727808"
        embed.colour = 0x7289da
        embed.set_author(name=str(self.bot.owner), icon_url=self.bot.owner.avatar_url)
        total_members = sum(len(s.members) for s in self.bot.guilds)
        unique_members = set(self.bot.get_all_members())
        members = '%s total\n%s unique' % (total_members, len(unique_members))
        embed.add_field(name='Members', value=members)
        embed.add_field(name='Uptime', value=str(timedelta(seconds=round(time.monotonic() - self.start_time))))
        motd = random.choice(["May the RNG be with you", "May your rolls be high",
                              "Will give higher rolls for cookies", ">:3",
                              "Does anyone even read these?"])
        embed.set_footer(
            text='{} | Build {}'.format(motd, self.bot.rdb.get('build_num')))
        commands_run = "{commands_used_life} total\n{dice_rolled_life} dice rolled\n{spells_looked_up_life} spells looked up\n{monsters_looked_up_life} monsters looked up\n{items_looked_up_life} items looked up\n{rounds_init_tracked_life} rounds of initiative tracked ({turns_init_tracked_life} turns)".format(
            **botStats)
        embed.add_field(name="Commands Run", value=commands_run)
        embed.add_field(name="Servers", value=str(len(self.bot.guilds)))
        memory_usage = psutil.Process().memory_full_info().uss / 1024 ** 2
        embed.add_field(name='Memory Usage', value='{:.2f} MiB'.format(memory_usage))
        embed.add_field(name='About', value='Made with :heart: by @zhu.exe#4211\n'
                                            'Help me buy a cup of coffee [here](https://www.paypal.me/avrae)!\n'
                                            'Join the official testing server [here](https://discord.gg/pQbd4s6)!',
                        inline=False)

        await ctx.send(embed=embed)

    @commands.command(hidden=True)
    async def patron_roscoe(self, ctx):
        embed = EmbedWithAuthor(ctx)
        embed.title = "Roscoe's Feast"
        embed.description = "*6th level conjuration. (Cleric, Druid)*"
        embed.add_field(name="Casting Time", value="10 minutes")
        embed.add_field(name="Range", value="30 feet")
        embed.add_field(name="Components", value="V, S, M (A gem encrusted bowl worth 1000 gold pieces)")
        embed.add_field(name="Duration", value="Instantaneous")
        embed.add_field(
            name="Description",
            value="You call forth the Avatar of Roscoe who brings with him a magnificent feast of chicken and waffles.\n"
                  "The feast takes 1 hour to consume and disappears at the end of that time, and the beneficial effects "
                  "don't set in until this hour is over. Up to twelve creatures can partake of the feast.\n"
                  "A creature that partakes of the feast gains several benefits. "
                  "The creature is cured of all diseases and poison, becomes immune to poison and being frightened, and "
                  "makes all Wisdom saving throws with advantage. Its hit point maximum also increases by 2d10, and it "
                  "gains the same number of hit points. These benefits last for 24 hours.")

        embed.set_footer(text=f"Spell | Thanks Roscoe!")
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Core(bot))
