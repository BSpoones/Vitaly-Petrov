from io import BytesIO
from discord.ext.commands import Cog, command
import random, discord, qrcode
from discord_slash import SlashCommand, cog_ext
from discord_slash.context import SlashContext

class Fun(Cog):
    def __init__(self,bot):
        # if not hasattr(bot, "slash"):
            # Creates new SlashCommand instance to bot if bot doesn't have.
        # Note that hasattr block is optional, meaning you might not have it.
        # Its completely fine, and ignore it.
        self.bot = bot

    # @cog_ext.cog_slash(name="sudoku")
    @command(name="Sudoku",brief="Shows a sudoku board with squares hidden based on difficulty", aliases=["sudoku"])
    async def sudoku(self,ctx, difficulty = 3) -> discord.Embed:
        number_dict = {1:":one:",2:":two:",3:":three:",4:":four:",5:":five:",6:":six:",7:":seven:",8:":eight:",9:":nine:"}
        base = 3
        side = base*base
        def pattern(r,c):
            return (base*(r%base)+r//base+c)%side

        # randomize rows, columns and numbers (of valid base pattern)
        from random import sample
        def shuffle(s):
            return sample(s,len(s)) 
        rBase = range(base) # 3
        rows  = [ g*base + r for g in shuffle(rBase) for r in shuffle(rBase) ] 
        cols  = [ g*base + c for g in shuffle(rBase) for c in shuffle(rBase) ]
        nums  = shuffle(range(1,base*base+1)) # nums = 9

        # produce board using randomized baseline pattern
        self.grid = [ [nums[pattern(r,c)] for c in cols] for r in rows ]


        new_grid = []
        for i,row in enumerate(self.grid):
            new_row = []
            for j, item in enumerate(row):
                randnum = random.randint(1,difficulty)
                if randnum == difficulty:
                    new_row.append(number_dict[item])
                else:
                    new_row.append(f"||{number_dict[item]}||")
            new_grid.append(new_row)
        TableTB = "|-----------------------------------------------|\n"
        TableMD = "|---------------+--------------+---------------|\n"
        output = TableTB
        for i, row in enumerate(new_grid):
            if i in (3,6):
                output += TableMD
            for j, item in enumerate(row):
                if j % 3 == 0:
                    output += "|"
                output += " "
                output += str(item)
                output += " "
            output += "|\n"
        output += TableTB
        await ctx.send(output)
        self.bot.log_command(ctx,"sudoku",difficulty)

    @command(name="QR Code",brief="Makes a QR code from a link",aliases=["qr","qrcode"])
    async def qr_code(self,ctx,link):
        wait_message = await ctx.send("Creating image, please wait.....")
        img = qrcode.make(link)

        with BytesIO() as image_binary: # Used to turn Pillow image to binary for discord to upload
            img.save(image_binary, 'PNG')
            image_binary.seek(0)
            file=discord.File(fp=image_binary, filename='image.png')
        
        title=f"**QR code**"
        description= f"Showing the QR code of {link}"
        embed = self.bot.auto_embed(
            type="info",
            title=title,
            description= description,
            ctx=ctx
        )
        embed.set_image(url=f"attachment://image.png")

        await ctx.send(file=file,embed=embed)
        await wait_message.delete()
        self.bot.log_command(ctx,"qrcode",link)
    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up("fun")
        print("fun cog ready!")

def setup(bot):
    bot.add_cog(Fun(bot))