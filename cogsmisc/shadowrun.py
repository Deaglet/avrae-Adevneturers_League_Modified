import asyncio
import shlex
import textwrap
import traceback
import uuid
import re
import subprocess
import random

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

    @commands.command(name='edge', aliases=['e'])
    async def edge(self, ctx, runner_name):
        characterDocuments = self.bot.mdb.character.find({"runner_name":runner_name}).limit(1)
        await ctx.send(characterDocuments[0]["edge"])

    @commands.command(name='addRunner', aliases=['ar','add_runner'])
    async def addRunner(self, ctx, runner_name, edgeCount=0):
        if self.doesRunnerExist(runner_name):
            await ctx.send("Runner " + runner_name + " already exists")
        else:
            await self.bot.mdb.character.insert_one({"runner_name":runner_name, "edge_stat":edgeCount, "edge": edgeCount})
            await ctx.send("Runner Added")

    @commands.command(name='setEdge', aliases=['sete','setedge'])
    async def setEdge(self, ctx, runner_name, edge):
        if self.doesRunnerExist(runner_name):
            self.bot.mdb.character.update_one({"runner_name":runner_name}, {"$set":{"edge":edge}}, upsert=True)
            await ctx.send("Runner edge has been set")
        else:
            self.addRunner(runner_name, edge)


    @commands.command(name='addEdge', aliases=['ae','aEdge','aedge'])
    async def addEdge(self, ctx, runner_name, edge):
        await self.changeEdge(ctx, runner_name, edge, True)

    @commands.command(name='subtractEdge', aliases=['se','sEdge','sedge'])
    async def addEdge(self, ctx, runner_name, edge):
        await self.changeEdge(ctx, runner_name, edge, True)

    # Todo: this method probably does too much
    async def changeEdge(self, ctx, runner_name, edge, positive):
        str = ""
        if self.doesRunnerExist(runner_name):
            oldEdge = self.bot.mdb.character.find({"runner_name":runner_name}).limit(1)[0]["edge"]
            if positive:
                newEdge = oldEdge + edge
            else:
                newEdge = oldEdge + edge
            if newEdge > 7:
                newEdge = 7
                str += "Max edge of 7 reached, setting to 7. \n"
            elif newEdge <= 0:
                newEdge = 0
            self.bot.mdb.character.update_one({"runner_name":runner_name}, {"$set":{"edge":newEdge}}, upsert=True)
        else:
            await ctx.send("Runner does not exist, adding runner")
            self.addRunner(runner_name, edge)

        if positive:
            str += "Edge has been added, Total Edge: " + newEdge
        else:
            str += "Edge has been removed, Total Edge: " + newEdge
        await ctx.send(str)

    def doesRunnerExist(self, runner_name):
        characterDocument = self.bot.mdb.character.find({"runner_name":runner_name})
        listOfCharacter = yield characterDocument.to_list(None)
        if len(listOfCharacter) == 0:
            return False
        return True

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
