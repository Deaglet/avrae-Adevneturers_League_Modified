import asyncio

import discord
from discord.ext.commands import BucketType, UserInputError

ALIASER_ROLES = ("server aliaser", "dragonspeaker") #do i need this?


class Graveyard(commands.Cog):
    """Commands to help streamline using the bot."""

    def __init__(self, bot):
        self.bot = bot


    @commands.command(name='graveyard')
    @commands.cooldown(1, 5, BucketType.user)
    async def graveyard(self):
        await ctx.send( "Graveyard. Test STring")




