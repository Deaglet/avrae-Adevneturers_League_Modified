import asyncio

import discord
from discord.ext.commands import BucketType, UserInputError
from discord.ext import commands

import subprocess


class Reboot(commands.Cog):
    """Commands to help streamline using the bot."""

    def __init__(self, bot):
        self.bot = bot

    async def canRestartServer(self,ctx):
        for role in ctx.message.author.roles:
            if "Bot Necromancers" == role.__str__():
                return True
        await ctx.send("Stop kicking me.")
        return False

    @commands.command(name='reboot', aliases=['kick','restart','meow'])
    @commands.cooldown(1, 5, BucketType.user)
    async def reboot(self,ctx):

        bool = await self.canRestartServer(ctx)
        if bool:
            bashCommand = "sudo kill $(ps aux | grep 'python3 dbot' | awk '{print $2}')"
            #output = subprocess.check_output(['bash','-c', bashCommand])
            output = subprocess.check_output(['bash',check=False, bashCommand])


def setup(bot):
    bot.add_cog(Reboot(bot))