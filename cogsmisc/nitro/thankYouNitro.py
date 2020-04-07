
import discord
from discord.ext import commands
import random




class ThankYou(commands.Cog):
    """Commands to say Thanks to Nitro Members"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=['Homegrown'])
    async def condition(self, ctx, *, name: str):

        
        colorEmbed = random.randint(0,3822)
        embed = discord.Embed()
        embed.colour = colorEmbed
        #embed.title = self.get_name()
        embed.title = "Homegrown"
        embed.add_field(value=f"`Aw shucks, Hux.  Being against your axe, sucks!`")
        embed.set_footer(*, text="Thank you for being a [Nitro Supporter](https://discordapp.com/nitro)", icon_url="cogsmisc\nitro\nitro_icon.svg")
        return embed


def setup(bot):
    bot.add_cog(Lookup(bot))
