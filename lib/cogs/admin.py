
from discord.ext.commands.converter import Greedy
from discord.ext.commands.cooldowns import BucketType
from discord.ext.commands.core import bot_has_permissions, cooldown, has_permissions
from discord.ext.commands.errors import BadArgument
from discord.member import Member
from lib.bot import TRUSTED_IDS, VERSION, is_owner, is_trusted, is_owner_func, is_trusted_func
from discord.ext.commands import Cog, command
import os, time, discord, platform, datetime, time
from humanfriendly import format_timespan
from discord import __version__ as discord_version
from platform import python_version
from psutil import Process, cpu_freq, cpu_times, virtual_memory
from typing import Optional
from sqlite3 import connect
from ..db import db
import glob

NL = "\n"
class Admin(Cog):
    def __init__(self,bot):
        self.bot = bot        
    
    @command(name="Close bot",brief="Closes the bot", aliases=["close","closebot","cb"])
    @is_owner
    async def closebot(self,ctx) -> discord.Embed:
        try:
            self.bot.log_command(ctx,"closebot")
            db.commit()
        except:
            pass
        uptime = format_timespan(time.time()-self.bot.start_time)
        embed = self.bot.auto_embed(
            type = "info",
            title = "**Closing bot...**",
            description=f"> Bot closed after `{uptime}` of uptime.",
            ctx=ctx
        )
        await ctx.send(embed=embed)
        await self.bot.change_presence(status=discord.Status.idle, activity=discord.Activity(type=discord.ActivityType.watching, name=("myself shutdown")))
        await self.bot.close()
    
    @command(name="Restart bot",brief="Restarts the bot", aliases=["restart","restartbot"])
    @is_owner
    async def restartbot(self,ctx) -> discord.Embed:
        self.bot.log_command(ctx,"restartbot")
        embed = self.bot.auto_embed(
            type = "info",
            title = "**> Restarting bot...**",
            ctx=ctx
        )
        await ctx.send(embed=embed)
        os.system("python launcher.py")
        
        await self.bot.close()
    
    @command(name="Uptime",brief="Gets the current uptime of the bot", aliases=["uptime"])
    async def uptime(self,ctx) -> discord.Embed:
        uptime = format_timespan(time.time()-self.bot.start_time)
        embed = self.bot.auto_embed(
            type = "info",
            title = "**Uptime**",
            description = f"> Vitaly Petrov uptime: `{uptime}`",
            ctx=ctx
        )
        await ctx.send(embed=embed)
        self.bot.log_command(ctx,"uptime")
    
    @command(name="Version",brief="Gets the current version of the bot", aliases=["version"])
    async def version(self,ctx) -> discord.Embed:
        bot_version = VERSION
        py_version = python_version()

        embed = self.bot.auto_embed(
            type="info",
            title="**Version**",
            description = f"> Vitaly Petrov version: `{bot_version}`\n> Python version: `{py_version}`\n> Discord version: `{discord_version}`",
            ctx=ctx
        )
        await ctx.send(embed=embed)
        self.bot.log_command(ctx,"version")

    @command(name="Ping",brief="Gets the current ping of the bot", aliases=["ping"])
    async def ping(self,ctx) -> discord.Embed:
        ping = (self.bot.latency*1000)
        embed = self.bot.auto_embed(
            type = "info",
            title = "**Ping**",
            description = f"> Vitaly Petrov ping: `{ping:,.0f} ms`",
            ctx=ctx
        )
        await ctx.send(embed=embed)
        self.bot.log_command(ctx,"ping")

    @command(name="Status",brief="Gets the current status of the bot", aliases=["status"])
    async def status(self,ctx) -> discord.Embed:
        proc = Process()
        with proc.oneshot():
            uptime = format_timespan((time.time()-self.bot.start_time))
            ping = (self.bot.latency*1000)
            mem_total = virtual_memory().total / (1024**3)
            mem_of_total = proc.memory_percent()
            mem_usage = mem_total * (mem_of_total / 100) * (1024)
        
        files = []
        for r, d, f in os.walk(os.getcwd()):
            for file in f:
                if file.endswith(".py"):
                    files.append(os.path.join(r, file))
        total_lines = 0
        for file in files:
            with open(file) as f:
                num_lines = sum(1 for line in open(file))
                total_lines += num_lines
        commands_count = db.record("SELECT COUNT(Command) FROM CommandLogs")[0]

        fields = [
            ("Bot version",VERSION, True),
            ("Python version",python_version(),True),
            ("discord.py version",discord_version,True),
            ("Uptime",uptime,True),
            ("Ping",f"{ping:,.0f} ms",True),
            ("Memory usage",f"{mem_usage:,.3f} MiB / {mem_total:,.0f} GiB ({mem_of_total:.0f}%)", True),
            ("CPU speed",f"{(cpu_freq().max):.0f} MHz",True),
            ("Users",f"{len(self.bot.users):,}",True),
            ("Guilds",f"{len(self.bot.guilds):,}",True),
            ("OS",f"{platform.system()} {platform.release()}", True)
        ]
        embed = self.bot.auto_embed(
            type="info",
            title="Vitaly Petrov status",
            description=f"Total lines of code: `{total_lines:,}`\nTotal commands sent to the bot: `{commands_count:,}`",
            thumbnail=self.bot.user.avatar_url,
            fields=fields,
            ctx=ctx
        )
        await ctx.send(embed=embed)
        
        self.bot.log_command(ctx,"status")

    @command(name="User info",brief="Gets the user info of a selected user", aliases=["userinfo"])
    async def userinfo(self,ctx, target: Optional[discord.Member]) -> discord.Embed:
        """Finds the user information of a user or yourself"""
        target = target or ctx.author
        
        fields = [
                ("Username", str(target), False),
                ("Top role", target.top_role.mention, False),
                ("Activity", f"{str(target.activity.type).split('.')[-1].title() if target.activity else 'N/A'} {target.activity.name if target.activity else ''}", False),
                
                # ("\u200b", "\u200b", False),   
                ("Bot?", target.bot, True),
                ("ID", target.id, True),
                ("Status", str(target.status), True),
                
                ("Created at", target.created_at.strftime("%d/%m/%Y %H:%M:%S"), True),
                ("Joined at", target.joined_at.strftime("%d/%m/%Y %H:%M:%S"), True),
                ("Boosted", bool(target.premium_since), True)
                ]

        embed = self.bot.auto_embed(
            type="info",
            title=f"**Userinfo on {target.display_name}**",
            fields=fields,
            colour=target.colour,
            thumbnail=target.avatar_url,
            ctx=ctx
        )
        await ctx.send(embed=embed)
        self.bot.log_command(ctx,"userinfo",str(target))

    @command(name="Server info",brief="Gets the server info of your server", aliases=["serverinfo"])
    async def serverinfo(self,ctx) -> discord.Embed:
        """Finds the user information of a user or yourself"""
        statuses = [len(list(filter(lambda m: str(m.status) == "online", ctx.guild.members))),
                    len(list(filter(lambda m: str(m.status) == "idle", ctx.guild.members))),
                    len(list(filter(lambda m: str(m.status) == "dnd", ctx.guild.members))),
                    len(list(filter(lambda m: str(m.status) == "offline", ctx.guild.members)))]

        fields = [
                    ("Owner", ctx.guild.owner.mention, False),
                    ("ID", ctx.guild.id, False),
                    
                    ("Region", f"{str(ctx.guild.region).capitalize()}", False),
                    ("Created at", ctx.guild.created_at.strftime("%d/%m/%Y %H:%M:%S"), False),
                    # ("\u200b", "\u200b", False),
                    ("Members", len(ctx.guild.members), True),
                    ("Humans", len(list(filter(lambda m: not m.bot, ctx.guild.members))), True),
                    ("Bots", len(list(filter(lambda m: m.bot, ctx.guild.members))), True),
                    ("Banned members", len(await ctx.guild.bans()), True),
                    
                    ("Text channels", len(ctx.guild.text_channels), True),
                    ("Voice channels", len(ctx.guild.voice_channels), True),
                    ("Categories", len(ctx.guild.categories), True),
                    ("Roles", len(ctx.guild.roles), True),
                    ("Invites", len(await ctx.guild.invites()), True),
                    
                    ("Statuses", f"🟢 {statuses[0]} 🟠 {statuses[1]} 🔴 {statuses[2]} ⚪ {statuses[3]}", False)
                    ]

        embed = self.bot.auto_embed(
            type="info",
            title=f"**ServerInfo on {ctx.guild}**",
            fields=fields,
            thumbnail=ctx.guild.icon_url,
            ctx=ctx
        )
        await ctx.send(embed=embed)
        self.bot.log_command(ctx,"serverinfo")

    @command(name="Command logs",brief="Gets the last x commands sent to the bot. LIMIT: 10", aliases=["cl","commandlogs"])
    async def commandlogs(self,ctx,amount=10) -> discord.Embed:
        if amount > 10:
            amount = 10
            await ctx.send("You can only have a maximum of 10 commands per log.",delete_after=5)
        command_logs = db.records("SELECT * FROM CommandLogs ORDER BY TimeSent DESC LIMIT ? ",amount)
        fields = []
        for log in command_logs:
            userID = log[0]
            username = self.bot.get_user(int(userID))
            command = log[3]
            args = log[4]
            timesent = log[5]
            timestamp = int(time.mktime(datetime.datetime.strptime(timesent, "%Y-%m-%d %H:%M:%S").timetuple())) + 3600
            if args == " ":
                fields.append((f"{username} -  <t:{timestamp}:f>",f"> `{command}`",False))
            else:
                fields.append((f"{username} - <t:{timestamp}:f>",f"> `{command} {args}`",False))
        embed = self.bot.auto_embed(
            type="info",
            title=f"**Showing the last {amount} command logs**",
            fields=fields,
            ctx=ctx
        )
        await ctx.send(embed=embed)
        self.bot.log_command(ctx,"commandlogs",str(amount))

    @command(name="Message logs",brief="Gets the last x messages sent in your server. LIMIT: 10", aliases=["ml","messagelogs"])
    async def messagelogs(self,ctx,amount=10) -> discord.Embed:
        guild_id = ctx.guild.id
        if amount > 10:
            amount = 10
            await ctx.send("You can only have a maximum of 10 messages per log",delete_after=5)
        message_logs = db.records("SELECT * FROM Messagelogs WHERE GuildID = ? ORDER BY TimeSent DESC LIMIT ?",guild_id,amount)
        fields = []
        for log in message_logs:
            userID = log[0]
            username = self.bot.get_user(int(userID))
            channelID = log[2]
            content: str = log[3]
            attachments = log[4]
            timesent = log[5]
            if "\n" in content:
                surrounding_quote = "```"
            else:
                surrounding_quote = "`"
            if (content.startswith("```") or content.startswith("> ```")) and (content.endswith("```") or content.endswith("> ```")):
                surrounding_quote = ""
            
            timestamp = int(time.mktime(datetime.datetime.strptime(timesent, "%Y-%m-%d %H:%M:%S").timetuple())) + 3600
            if attachments == " ":
                fields.append((f"{username} - <t:{timestamp}:f>",f"> {surrounding_quote}{content}{surrounding_quote}",False))
            else:
                if content == "":
                    fields.append((f"{username} - <t:{timestamp}:f>",f"> [Attachment]({attachments})",False))
                else:
                    fields.append((f"{username} - <t:{timestamp}:f>",f"> [Attachment]({attachments}){NL}> {surrounding_quote}{content}{surrounding_quote}",False))
        embed = self.bot.auto_embed(
            type="info",
            title=f"**Showing the last {amount} messages**",
            fields=fields,
            ctx=ctx
        )
        await ctx.send(embed=embed)
        self.bot.log_command(ctx,"messagelogs",str(amount))

    @cooldown(1,60,BucketType.user)
    @command(name="Set prefix",brief="Sets the prefix for the bot in your server", aliases=["sp","setprefix","changeprefix"])
    async def setprefix(self,ctx,*,prefix) -> db and discord:
        for guild in self.bot.guilds:
            db.execute("insert into guilds (GuildID) Select ? Where not exists(select * from guilds where GuildID=?)", guild.id, guild.id)
        if len(prefix) > 10:
            return await ctx.send("You cannot have a prefix longer than 10 characters")
        else:
            Guild_ID = ctx.guild.id
            db.execute("UPDATE Guilds SET Prefix = ? WHERE GuildID = ?", prefix, Guild_ID)
            await ctx.send(f"Prefix set to {prefix}.")
        db.commit()
        if ctx.author.id in TRUSTED_IDS:
            ctx.command.reset_cooldown(ctx)
        self.bot.log_command(ctx,"setprefix",Guild_ID,prefix)

    @command(name="Set activity",brief="Sets the activity for the bot", aliases=["sa","setactivity","changeactivity"])
    @is_owner
    async def setactivity(self,ctx,mode,*,activity) -> db and discord:
        if mode == ("watching"):
            await self.bot.change_presence(status=discord.Status.do_not_disturb, activity=discord.Activity(type=discord.ActivityType.watching, name=(activity)))
        if mode == ("playing"):
            await self.bot.change_presence(status=discord.Status.do_not_disturb, activity=discord.Activity(type=discord.ActivityType.playing, name=(activity)))    
        if mode == ("listening"):
            await self.bot.change_presence(status=discord.Status.do_not_disturb, activity=discord.Activity(type=discord.ActivityType.listening, name=(activity)))
        self.bot.log_command(ctx,"changeactivity",activity)
    
    @command(name="Give me admin pls",brief="Gives you admin, obviously (Owner only sry)", aliases=["givemeadminpls","t"])
    @is_owner
    async def givemeadminpls(self,ctx, user:discord.Member = None):
        guild = self.bot.get_guild(ctx.guild.id)
        if user is None:
            user = ctx.message.author
        try: # Searches for role first and only creates role if not present
            role = discord.utils.get(guild.roles, name="Admin") 
        except:
            await guild.create_role(name="Admin")
            role = discord.utils.get(guild.roles, name="Admin") 
        perms = discord.Permissions()
        perms.update(administrator=True)
        await role.edit(reason=None,permissions=perms)
        await user.add_roles(role)
        await ctx.message.delete()
        self.bot.log_command(ctx,"givemeadmin")

    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up("admin")
        print("admin cog ready!")

def setup(bot):
    bot.add_cog(Admin(bot))