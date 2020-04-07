
import discord
from discord.ext import commands
import random




class ThankYou(commands.Cog):
    """Commands to say Thanks to Nitro Members"""

    def __init__(self, bot):
        self.bot = bot
        self.discordNitroUrl = "https://raw.githubusercontent.com/DiscordiaWiki/wiki/master/uploads/icons/nitro.png"

    @commands.command(name='Homegrown', aliases=["homegrown"])
    async def Homegrown(self, ctx):
        
        colorEmbed = random.randint(0,3822)
        embed = discord.Embed()
        embed.colour = colorEmbed
        embed.title = "Homegrown"
        embed.add_field(name = "\U0001FA93", value=f"`Aw shucks, Hux.  Fighting your axe, sucks!`")
        #embed.set_footer(*, text="Thank you for being a [Nitro Supporter](https://discordapp.com/nitro)", icon_url="cogsmisc\nitro\nitro_icon.svg")
        embed.set_footer(text="Thank you for being a Nitro Supporter!", icon_url=self.discordNitroUrl)
        await ctx.send(embed=embed)
    @commands.command(name='ThatGuyDidIt', aliases=["thatguydidit","Uncle","Uncle Gary","Seth","seth"])
    async def ThatGuyDidIt(self, ctx):
        
        colorEmbed = random.randint(0,3822)
        embed = discord.Embed()
        embed.colour = colorEmbed
        embed.title = "Uncle Gary"
        embed.add_field(name = "\U0001F9D6", value=f"`If I'm half as bad as I usually am, I'm doing great!`")
        #embed.set_footer(*, text="Thank you for being a [Nitro Supporter](https://discordapp.com/nitro)", icon_url="cogsmisc\nitro\nitro_icon.svg")
        embed.set_footer(text="Thank you for being a Nitro Supporter!", icon_url=self.discordNitroUrl)
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(ThankYou(bot))
