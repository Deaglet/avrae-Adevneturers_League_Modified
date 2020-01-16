import asyncio
import shlex
import textwrap
import traceback
import uuid
import re
import subprocess

import discord
from discord.ext import commands
from discord.ext.commands import BucketType, UserInputError
from discord.ext.commands.view import StringView
from discord.utils import get

from cogs5e.funcs import scripting
from cogs5e.funcs.scripting import ScriptingEvaluator
from cogs5e.models.character import Character
from cogs5e.models.errors import AvraeException, EvaluationError, NoCharacter
from utils.functions import auth_and_chan, clean_content, confirm

ALIASER_ROLES = ("server aliaser", "dragonspeaker")


class Shadowrun(commands.Cog):
    """Commands to help streamline using the bot."""

    def __init__(self, bot):
        self.bot = bot

    async def on_ready(self):
        if getattr(self.bot, "shard_id", 0) == 0:
            cmds = list(self.bot.all_commands.keys())
            self.bot.rdb.jset('default_commands', cmds)

    async def on_message(self, message):
        if str(message.author.id) in self.bot.get_cog("AdminUtils").muted:
            return
        await self.handle_aliases(message)

    @commands.command(name='shadowrun', aliases=['sr','shadow','run'])
    async def shadowrun(self, ctx, dice_number):
        hitCount = 0
        critCount = 0
        output_str = "__Shadowrun Dice__ \n"
        dice_number = int(dice_number)
        for i in range(dice_number):
            value = random.randint(0, 5)
            output_str += " " + str(value+1) + " "
            if value >= 4:
                hitCount += 1
            elif value == 0:
                critCount += 1
        output_str += "\n Runner Hits: " + str(hitCount)
        if critCount >= dice_number/2:
            output_str += "\n"
            if hitCount == 0:
                output_str += "***CRITICAL GLITCH***"
            else:
                output_str += "*GLITCH*"
        await ctx.send(output_str)


def setup(bot):
    bot.add_cog(Shadowrun(bot))

class Context:
    """A class to pretend to be ctx."""

    def __init__(self, bot, message):
        self.bot = bot
        self.message = message

    @property
    def author(self):
        return self.message.author

    @property
    def guild(self):
        return self.message.guild

    @property
    def channel(self):
        return self.message.channel
