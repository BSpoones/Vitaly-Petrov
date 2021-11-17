import json, time, discord, asyncio
import sqlite3
from sqlite3.dbapi2 import DatabaseError
from sqlite3 import connect
from glob import glob
from datetime import datetime
from discord import Embed, Intents
from discord.ext import commands
from discord.errors import Forbidden, InvalidArgument
from discord.ext.commands import Bot as BotBase
from discord.ext.commands.errors import BadArgument, BadUnionArgument, CheckFailure, CommandNotFound, CommandOnCooldown, MissingRequiredArgument
from discord.ext.commands.context import Context
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from humanfriendly import format_timespan
from ..db import db
from discord.ext.commands import when_mentioned_or

COGS = [path.split("/")[-1][:-3] for path in glob("./lib/cogs/*.py")] #Selects all .py files in cog

with open("./data/BotInfo.json") as f: # Inputs required constants from JSON
    BOT_INFO = json.load(f)
    VERSION = BOT_INFO["version"]
    ACTIVITY_TYPE = BOT_INFO["activity type"]
    ACTIVITY_NAME = BOT_INFO["activity name"]
    TRUSTED_IDS = BOT_INFO["trusted ids"]
    OWNER_IDS = BOT_INFO["owner ids"]

def is_owner_func(ctx) -> bool:
    return ctx.author.id in OWNER_IDS
is_owner = commands.check(is_owner_func)

def is_trusted_func(ctx) -> bool:
    return ctx.author.id in TRUSTED_IDS
is_trusted = commands.check(is_trusted_func)

def get_prefix_value(ctx) -> str:
    return db.field("SELECT Prefix FROM guilds WHERE GuildID = ?", ctx.guild.id)

def get_prefix(bot,message) -> list:
    prefix = db.field("SELECT Prefix FROM guilds WHERE GuildID = ?", message.guild.id)
    return when_mentioned_or(prefix)(bot,message)


class Ready(object):
    """
    Cogs return True if running, return False if not
    """
    # try:#This is an insanely low effort solution to linux and windows breaking
    #     COGS = [path.split("/")[-1][:-3] for path in glob("./lib/cogs/*.py")]
    # except:
    #     COGS = [path.split("\\")[-1][:-3] for path in glob("./lib/cogs/*.py")]

    def __init__(self):
        for cog in COGS:
            setattr(self, cog, False)

    def ready_up(self, cog):
        setattr(self, cog, True)
        print(f"{cog} cog ready!")

    def all_ready(self):
        return all([getattr(self,cog) for cog in COGS])

class Bot(BotBase):
    """
    The main body of Vitaly Petrov, all cogs and databases are loaded here and
    this is what is run in launcher.py
    """
    def __init__(self):
        with open("./data/token.0","r",encoding="utf-8") as tf:
            self.TOKEN = tf.read()
        self.cogs_ready = Ready()
        self.ready = False
        self.start_time = time.time()
        self.cxn = connect("./data/db/database.db", check_same_thread=False)
        self.cur = self.cxn.cursor()
        self.scheduler = AsyncIOScheduler()

        self.ping_list = [] # Max=1000

        super().__init__(
            command_prefix=get_prefix,
            intents=Intents.all()
            )

    def setup(self):
        try:# This is a low effort solution to stop windows and linux from being bad
            COGS = [path.split("/")[-1][:-3] for path in glob("./lib/cogs/*.py")]
            for cog in COGS:
                self.load_extension(f"lib.cogs.{cog}")
                print(f"{cog} cog loaded.")
        except:
            COGS = [path.split("\\")[-1][:-3] for path in glob("./lib/cogs/*.py")]
            for cog in COGS:
                self.load_extension(f"lib.cogs.{cog}")
                print(f"{cog} cog loaded.")

    def run(self):
        self.log("Running setup....")
        self.log(f"Vitaly Petrov v{VERSION}")
        self.log("Loading cogs....")
        self.setup()

        super().run(self.TOKEN, reconnect=True)

    async def on_ready(self):
        await self.update_activity()
        await self.change_presence(
            status=discord.Status.do_not_disturb, 
            activity=discord.Activity(
                type=discord.ActivityType.playing, 
                name=(f"{ACTIVITY_NAME}{VERSION} | {len(self.users)} users on {len(self.guilds)} servers")
                )
            )
        if not self.ready:
            self.ready = True
            while not self.cogs_ready.all_ready():
                await asyncio.sleep(0.1)
            
        else:
            self.log(f"Bot reconnected at {self.current_time()}")

    async def on_connect(self) -> str:
        self.log(f"Bot connected on {self.current_time()}")

    async def on_disconnect(self) -> str:
        self.log(f"Bot disconnected on {self.current_time()}")

    async def on_guild_join(self,guild):
        print("Joined a new guild",guild)
        db.execute("INSERT INTO guilds (GuildID,Prefix) VALUES (?,?)",guild.id, "-")
        await self.update_activity()
        db.commit()

    async def on_guild_remove(self,guild):
        db.execute("DELETE FROM guilds WHERE GuildID = ?",guild.id)
        await self.update_activity()
        db.commit()
    
    async def on_member_join(self,member):
        await self.update_activity()
    async def on_member_remove(self,member):
        await self.update_activity()

    async def on_error(self, err, *args, **kwargs):
        if err == "on_command_error":
            await args[0].send("Either you did something wrong or i'm badly coded, usually it's the latter but please check what you just typed.")
        raise err

    async def on_command_error(self, ctx, exc) -> str:
        IGNORE_EXCEPTIONS = []
        if any([isinstance(exc, error) for error in IGNORE_EXCEPTIONS]):
            pass
        elif isinstance(exc,CommandNotFound):
            embed = self.auto_embed(
                type="error",
                title="Invalid command",
                description=f"That command is not in Vitaly Petrov, use `{get_prefix_value(ctx)}help` to view a full list of commands!",
                ctx=ctx
            )
            await ctx.send(embed=embed)
        elif isinstance(exc, CheckFailure):
            embed = self.auto_embed(
                type="error",
                title="Invalid permissions",
                description="You do not have the correct permissions for this command, contact a server owner or admin for more information.",
                ctx=ctx
            )
            await ctx.send(embed=embed)
        elif isinstance(exc, MissingRequiredArgument):
            embed = self.auto_embed(
                type="error",
                title="Missing argument",
                description=f"One or more required arguments are missing, use `{get_prefix_value(ctx)}help` for more information.",
                ctx=ctx
            )
            await ctx.send(embed=embed)
        elif isinstance(exc, BadArgument):
            embed = self.auto_embed(
                type="error",
                title="Invalid argument",
                description=f"You have entered one of the arguments wrong, use `{get_prefix_value(ctx)}help` for more information.",
                ctx=ctx
            )
            await ctx.send(embed=embed)

        elif isinstance(exc, CommandOnCooldown):
            embed = self.auto_embed(
                type="error",
                title="Command on cooldown",
                description=f"That command is on {str(exc.cooldown.type).split('.')[-1]} cooldown. Try again in {format_timespan(exc.retry_after)}.",
                ctx=ctx
            )
            await ctx.send(embed=embed)

        elif isinstance(exc,BadUnionArgument):
            embed = self.auto_embed(
                type="error",
                title="Could not find emoji",
                description=f"Could not find that emoji, please make sure you only use custom emoji.",
                ctx=ctx
            )
            await ctx.send(embed=embed)
        elif isinstance(exc,DatabaseError):
            print("DATABASE ERROR")
        
        elif isinstance(exc, sqlite3.OperationalError):
            print("DATABASE ERROR")
            print("ATTEMPTING RELOAD")
            try:
                db.reload()
            except:
                print("RELOAD FAILED")
        elif hasattr(exc, "original"):
            # if isinstance(exc.original, HTTPException):
            #     await ctx.send("Unable to send message.")

            if isinstance(exc.original, Forbidden):
                await ctx.send("I do not have permission to do that.")

            else:
                raise exc.original

        else:
            raise exc

   
    async def process_commands(self, message):
        ctx = await self.get_context(message,cls=Context)

        if ctx.command is not None and ctx.guild is not None:
            # if message.author.id in self.banlist:
            #     await ctx.send("You are banned from using commands")
            if not self.ready:
                await ctx.send("I am still starting up, try again in a few seconds")
            else:
                await self.invoke(ctx)

    async def update_activity(self) -> discord:
        total_users = (self.users)
        total_users = set([x.id for x in self.users])
        await self.change_presence(
            status=discord.Status.do_not_disturb, 
            activity=discord.Activity(
                type=discord.ActivityType.playing, 
                name=(f"{ACTIVITY_NAME}{VERSION} | {len(self.users)} users on {len(self.guilds)} servers")
                )
            )
    
    

    def log_command(self,*args) -> str:
        ctx = args[0]
        command = args[1]
        try:
            cmd_args = " ".join(args[2:])
        except:
            cmd_args = " "
        author = ctx.author.id
        guild = ctx.guild.id
        channel = ctx.channel.id
        try:
            db.execute("INSERT INTO CommandLogs(UserID,GuildID,ChannelID,Command,Args) VALUES (?,?,?,?,?)", author,guild,channel,command, cmd_args)
            db.commit()
        except Exception as e:
            print(e)
            print("database error",author,guild,channel,command,cmd_args)
            print("DATABASE ERROR")
            print("ATTEMPTING RELOAD")
            try:
                db.reload()
            except:
                print("RELOAD FAILED")
    def auto_embed(self, **kwargs) -> Embed:
        #  type=None, title=None, description=None, fields=None
        try:
            embed_type = kwargs["type"]
        except:
            embed_type = "default"
        try:
            ctx = kwargs["ctx"]
        except:
            pass
        try:
            user = kwargs["user"]
        except:
            pass

        if embed_type=="error":
            colour = discord.Colour.red()
        elif embed_type == "default":
            colour = discord.Colour.green()
        elif embed_type in ("schedule","info","emoji"):
            colour = ctx.author.colour
        elif embed_type == "reminder-user":
            colour = user.colour

        try:
            kwargs["colour"]
        except:
            kwargs["colour"] = colour
        
        kwargs["timestamp"] = datetime.utcnow()
        
        embed = Embed(**kwargs)
        
        try:
            thumbnail = kwargs["thumbnail"]
            embed.set_thumbnail(url=thumbnail)
        except:
            pass
        try:
            fields = kwargs["fields"]
            for name,value, inline in fields:
                embed.add_field(name=name, value=value, inline=inline)
        except:
            pass
        
        if embed_type == "error":
            embed.set_author(name="Error", icon_url="https://freeiconshop.com/wp-content/uploads/edd/error-flat.png")
        elif embed_type == "lesson":
            school = kwargs["schoolname"]
            icon = kwargs["iconurl"]
            embed.set_author(name=school, icon_url=icon)
        elif embed_type in ("schedule","info","emoji"):
            embed.set_author(name= ctx.author, icon_url = ctx.author.avatar_url)
        elif embed_type == "reminder-user":
            embed.set_author(name= user, icon_url= user.avatar_url)
        if embed_type == "emoji":
            embed.set_image(url=kwargs["emoji_url"])
        
        return embed

    def current_time(self) -> str:
        now = (datetime.now().strftime("%Y-%m-%d at %H:%M:%S"))
        return now

    def log(self,log) -> str:
        print(log)
bot = Bot()

if __name__ == "__main__":
    print("Please run the bot in launcher.py")
    exit()
