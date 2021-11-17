from discord.ext.commands import Cog, command
import random

class Misc(Cog):
    def __init__(self,bot):
        self.bot = bot

    @command(name="Thonk", brief="Displays an enlarged :thonk: emote",aliases=["thonk"])
    async def thonk(self,ctx):
        await ctx.message.delete()
        await ctx.send("https://cdn.discordapp.com/emojis/758717582773190676.png?v=1")
        self.bot.log_command(ctx,"thonk")
    
    @command(name="Bonk", brief="Displays an enlarged :bonk: emote",aliases=["bonk"])
    async def bonk(self,ctx):
        await ctx.message.delete()
        await ctx.send("https://i.kym-cdn.com/entries/icons/facebook/000/033/758/Screen_Shot_2020-04-28_at_12.21.48_PM.jpg")
        self.bot.log_command(ctx,"bonk")
    @command(name="Sponk", brief="Displays an enlarged :sponk: emote",aliases=["sponk"])
    async def sponk(self,ctx):
        await ctx.message.delete()
        await ctx.send("https://cdn.discordapp.com/emojis/802260617095282700.png?v=1")
        self.bot.log_command(ctx,"sponk")

    @command(name="Brexit", brief="Displays an enlarged :brexit: emote",aliases=["brexit"])
    async def brexit(self,ctx):
        await ctx.message.delete()
        await ctx.send(content="<:brexit1:875497285440655392><:brexit2:875497285566488617><:brexit3:875497285730050099><:brexit4:875497285763629107>")
        self.bot.log_command(ctx,"brexit")

    @command(name="Hackerman", brief="Displays a hackerman GIF",aliases=["hackerman","hackermen"])
    async def hackerman(self,ctx):
        await ctx.message.delete()
        await ctx.send("https://giphy.com/gifs/YQitE4YNQNahy")
        self.bot.log_command(ctx,"hackerman")
    
    @command(name="Genuine Concern", brief="Displays an enlarged :genuineconcern: emote",aliases=["genuineconcern"])
    async def genuineconcern(self,ctx):
        await ctx.message.delete()
        await ctx.send("https://media.discordapp.net/attachments/834051635666747395/875314570992947210/image0.jpg")
        self.bot.log_command(ctx,"genuineconcern")
    
    @command(name="Top Gear", brief="Displays an enlarged :topgear: emote",aliases=["topgear"])
    async def topgear(self,ctx):
        await ctx.message.delete()
        await ctx.send("https://media.discordapp.net/attachments/834051635666747395/875408719205245028/image0.png")
        self.bot.log_command(ctx,"topgear")

    @command(name="Genuine Depression", brief="Displays an enlarged :genuinedepression: emote",aliases=["genuinedepression"])
    async def genuinedepression(self,ctx):
        await ctx.message.delete()
        await ctx.send("https://media.discordapp.net/attachments/845322493203447829/883117196467920896/image0.jpg?width=1609&height=905")
        self.bot.log_command(ctx,"genuinedepression")

    @command(name="Oh no! Anyway", brief="Shows an 'Oh No! Anyway' GIF",aliases=["ohno"])
    async def oh_no_anyway(self,ctx):
        await ctx.message.delete()
        await ctx.send("https://giphy.com/gifs/oh-no-anyway-7k2LoEykY5i1hfeWQB")
        self.bot.log_command(ctx,"ohno")

    @command(name="Woah Nigga",brief="Displays a 'woah nigga' meme",aliases=["woah","woahnigga"])
    async def woah(self,ctx):
        await ctx.message.delete()
        await ctx.send("https://cdn.discordapp.com/attachments/774301333146435607/886348964645961798/image0.png")
        self.bot.log_command(ctx,"woah")
    
    @command(name="Who Asked?",brief="Displays a random Who Asked message",aliases=["who","whoasked"])
    async def who_asked(self,ctx):
        choices = [
            "https://tenor.com/view/who-asked-gif-21207758",
            "https://tenor.com/view/bean-dance-crazy-aye-dats-fr-crazy-hoe-now-show-me-one-person-who-asked-gif-16195074",
            "https://media.discordapp.net/attachments/774301333146435607/886351170350751824/71ec7887d73486e298c59ab42dfa5c7aaf604b042934e57bcb6f8f363cb06e4b_1.jpg?width=795&height=671",
            "https://tenor.com/view/among-us-who-asked-gif-18850795",
            "https://media.discordapp.net/attachments/774301333146435607/886351722082074634/maxresdefault.jpg?width=1193&height=671"
        ]
        choice = random.choice(choices)
        await ctx.message.delete()
        await ctx.send(choice)
        self.bot.log_command(ctx,"who_asked",choice)

    @command(name="Dog",brief="Displays a dog gif",aliases=["dog"])
    async def dog(self,ctx):
        await ctx.message.delete()
        await ctx.send("https://media.giphy.com/media/LZbLMxeaSKys08I68T/giphy.gif?cid=790b7611cb6310c244356666ddbf6c231950fabc48c2e9e6&rid=giphy.gif&ct=g")
        self.bot.log_command(ctx,"dog")

    @command(name="Chair",brief="Displays the chair meme",aliases=["chair"])
    async def chair(self,ctx):
        await ctx.message.delete()
        await ctx.send("https://media.discordapp.net/attachments/755473207833657454/889817442182918194/hityouwithchair.png")
        self.bot.log_command(ctx,"chair")

    @command(name="OK KID",brief="Displays an OK KID emote",aliases=["ok","okkid"])
    async def okkid(self,ctx):
        await ctx.message.delete()
        await ctx.send("https://cdn.discordapp.com/attachments/583040931113205788/889984865515208704/okkid.jpg")
        self.bot.log_command(ctx,"okkid")
    @command(name="Oh Fuck off",brief='Displays an "OH F*CK OFF" gif.',aliases=["fuckoff","ohfuckoff"])
    async def fuckoff(self,ctx):
        await ctx.message.delete()
        await ctx.send("https://tenor.com/view/oh-fuck-off-go-away-just-go-leave-me-alone-spicy-wings-gif-14523970")
        self.bot.log_command(ctx,"fuckoff")
    @command(name="So funny",brief='Displays a "so funny" image.',aliases=["haha","sofunny","stfu"])
    async def so_funny(self,ctx):
        await ctx.message.delete()
        await ctx.send("https://media.discordapp.net/attachments/884385641373257739/895326715679760444/image0.jpg?width=703&height=671")
        self.bot.log_command(ctx,"so funny")
    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up("misc")
        print("misc cog ready!")

def setup(bot):
    bot.add_cog(Misc(bot))