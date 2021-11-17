from apscheduler.triggers.cron import CronTrigger
from discord.embeds import Embed
from discord.utils import get
from lib.bot import OWNER_IDS, TRUSTED_IDS, Bot, get_prefix_value
from discord.ext.commands import Cog, command
from discord.ext.commands.errors import BadArgument, CheckFailure
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord.ext.commands.cooldowns import BucketType
from discord.ext.commands.core import cooldown, has_permissions
from ..db import db
import discord, datetime
NL = "\n" # f strings don't like \n so a variable is used instead
example_reminders = """
> `remind (everyone / here / me / nobody / @user) (every / on / in) (YYYY-MM-DD date / weekday / "day") (24h time) (todo)`
> 
> E.g:
> 
> `remind me on 2021-09-10 12:00 cry`
> `remind @someone every friday 19:00 die`
> `remind nobody in 1 hour cry some more`
> `remind everyone in 10 days find a better example`
"""

class Reminder(Cog):
    def __init__(self,bot):
        self.bot = bot
        self.days_of_week = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
        self.reminder_scheduler = AsyncIOScheduler()
        self.load_reminders()
    async def send_missed_reminders(self):
        self.reminders = db.records("SELECT * FROM Reminders")
        for reminder in self.reminders:
            datetype = reminder[6]
            date = reminder[7]
            time = reminder[8]
            hour = time[0:2]
            minute = time[2:4]
            
            if datetype == "YYYYMMDD":
                year = date[0:4]
                month = date[4:6]
                day = date[6:8]
                datetime_date = datetime.datetime(
                    year= int(year),
                    month = int(month),
                    day = int(day),
                    hour = int(hour),
                    minute= int(minute)
                )
                if datetime_date < datetime.datetime.today():
                    id = reminder[0]
                    author_id = reminder[1]
                    target = reminder[2]
                    output_guild = int(reminder[3])
                    output_channel = int(reminder[4])
                    reminder_type = reminder[5]
                    reminder_content = reminder[9]
                    channel = self.bot.get_channel(output_channel)
                    description = f"This reminder failed to send, if this keeps happening, contact <@724351142158401577>.\nID: `{id}`\n**{reminder_content}**"
                    if len(target) == 18:
                        user = self.bot.get_guild(output_guild).get_member(int(target))
                        
                        try:
                            embed = self.bot.auto_embed(
                                type="reminder-user",
                                title=f"**Missed Reminder**",
                                description = description,
                                user= user
                            )
                        except:
                            embed = self.bot.auto_embed(
                                type="default",
                                title=f"**Missed reminder**",
                                description=description
                            )
                            return await channel.send(embed=embed)

                    else:
                        embed = self.bot.auto_embed(
                            type="default",
                            title="**Missed Reminder**",
                            description=description
                        )
                    await channel.send(embed=embed)
                    if len(target) == 18: # If a user ID is being used
                        await channel.send(f"<@{target}>")
                    elif target == "everyone":
                        await channel.send("@everyone")
                    elif target == "here":
                        await channel.send("@here")
                    if reminder_type == "on":
                        db.execute("DELETE FROM Reminders WHERE ReminderID = ?",id)
                        db.commit()
                        self.load_reminders()
    def load_reminders(self) -> AsyncIOScheduler:
        try: # Prevents multiple schedulers running at the same time
            if (self.reminder_scheduler.state) == 1:
                self.reminder_scheduler.shutdown(wait=False)
            self.reminder_scheduler = AsyncIOScheduler()
        except:
            self.reminder_scheduler = AsyncIOScheduler()
        
        self.reminders = db.records("SELECT * FROM Reminders")
        self.reminder_scheduler.add_job(
            self.send_missed_reminders,
            CronTrigger(
                minute=7
            )
        )
        for reminder in self.reminders:
            datetype = reminder[6]
            date = reminder[7]
            time = reminder[8]
            hour = time[0:2]
            minute = time[2:4]
            
            if datetype == "YYYYMMDD":
                year = date[0:4]
                month = date[4:6]
                day = date[6:8]
                datetime_date = datetime.datetime(
                    year= int(year),
                    month = int(month),
                    day = int(day),
                    hour = int(hour),
                    minute= int(minute)
                )
                if datetime_date < datetime.datetime.today():
                    """
                    Refuses to load reminders for dates in the past
                    """
                    continue
                self.reminder_scheduler.add_job(
                    self.send_reminder,
                    CronTrigger(
                        year = year,
                        month = month,
                        day = day,
                        hour = hour,
                        minute = minute,
                        second = 0
                    ),
                    args = [reminder]
                )
            elif datetype == "weekday":
                day_of_week = self.days_of_week.index(date)
                self.reminder_scheduler.add_job(
                    self.send_reminder,
                    CronTrigger(
                        day_of_week = day_of_week,
                        hour = hour,
                        minute = minute,
                        second = 0
                    ),
                    args = [reminder]
                )
            elif datetype == "day":
                self.reminder_scheduler.add_job(
                    self.send_reminder,
                    CronTrigger(
                        hour = hour,
                        minute = minute,
                        second = 0
                    ),
                    args = [reminder]
                )

        self.reminder_scheduler.start()

    async def send_reminder(self, *args) -> Embed:
        args = args[0]
        id = args[0]
        target = args[2]
        output_guild = int(args[3])
        output_channel = int(args[4])
        reminder_type = args[5]
        reminder_content = args[9]
        channel = self.bot.get_channel(output_channel)
        description = f"ID: `{id}`\n**{reminder_content}**"
        try:
            if len(target) == 18:
                user = self.bot.get_guild(output_guild).get_member(int(target))
                embed = self.bot.auto_embed(
                    type="reminder-user",
                    title=f"**Reminder**",
                    description = description,
                    user= user
                )
            else:
                embed = self.bot.auto_embed(
                    type="default",
                    title="**Reminder**",
                    description=description
                )
            await channel.send(embed=embed)
            if len(target) == 18: # If a user ID is being used
                await channel.send(f"<@{target}>")
            elif target == "everyone":
                await channel.send("@everyone")
            elif target == "here":
                await channel.send("@here")
        except:
            pass
        if reminder_type == "on":
            db.execute("DELETE FROM Reminders WHERE ReminderID = ?",id)
            db.commit()
            self.load_reminders()
    
    @command(name="Delete Reminder", brief="Deletes a selected reminder. NOTE: You must be the creator of a reminder to delete it!",aliases=["deletereminder","dr"])
    async def deletereminder(self,ctx, reminder_ID: str) -> db and Embed:
        author_id = ctx.author.id
        reminder = db.record("SELECT * FROM Reminders WHERE ReminderID = ?",reminder_ID)
        if reminder is None:
            await ctx.send("Reminder not found")
        elif int(reminder[1]) != author_id and ctx.author.id not in OWNER_IDS:
            raise CheckFailure
        else:
            target = reminder[2]
            reminder_type = reminder[5]
            date_type = reminder[6]
            reminder_date = reminder[7]
            reminder_time = reminder[8]
            reminder_content = reminder[9]

            if len(str(target)) == 18:
                target_mention = f"<@{target}>"
            else:
                target_mention = f"@{target}"
            if reminder_type == "every":
                str_type = "recurring"
                str_date = "Frequency"
            elif reminder_type == "on":
                str_type = "single"
                str_date = "Date"
            if date_type == "day":
                reminder_date = "Daily"
            elif date_type == "weekday":
                reminder_date = f"{reminder_type.capitalize()} {reminder_date.capitalize()}"

            if date_type == "YYYYMMDD":
                reminder_date = f"{reminder_date[0:4]}-{reminder_date[4:6]}-{reminder_date[6:8]}"

            description = f"**Deleted reminder:**\n\nTarget: {target_mention}\nType: `{str_type}`\n{str_date}: `{reminder_date}`\nTime: `{reminder_time[0:2]}:{reminder_time[2:]}`\nDetails: `{reminder_content}`"
            embed = self.bot.auto_embed(
                type="info",
                title="Reminder deleted",
                description=description,
                ctx=ctx
            )
            db.execute("DELETE FROM Reminders WHERE ReminderID = ?",reminder_ID)
            db.commit()
            self.load_reminders()
            await ctx.send(embed=embed)
            self.bot.log_command(ctx,"deletereminder",reminder)

    @cooldown(1,60,BucketType.user)
    @command(name="Show Reminders", brief="Shows your reminders on a server, use `showreminders all` to view all reminders",aliases=["showreminders","sr"])
    async def showreminders(self,ctx, all = None) -> Embed:
        user_ID = ctx.author.id
        guild_ID = ctx.guild.id
        if all is None:
            reminders = db.records("SELECT * FROM Reminders WHERE CreatorUserID = ? AND OutputGuildID = ?", user_ID, guild_ID)
            show_all = False
        elif all == "all":
            reminders = db.records("SELECT * FROM Reminders WHERE CreatorUserID = ?", user_ID)
            show_all = True
        else:
            raise BadArgument
        formatted_reminders = []

        for reminder in reminders:
            id = reminder[0]
            target = reminder[2]
            reminder_type = reminder[5]
            date_type = reminder[6]
            reminder_date = reminder[7]
            reminder_time = reminder[8]
            reminder_content = reminder[9]

            if len(str(target)) == 18:
                target_mention = f"<@{target}>"
            else:
                target_mention = f"@{target}"
            if reminder_type == "every":
                str_type = "recurring"
                str_date = "Frequency"
            elif reminder_type == "on":
                str_type = "single"
                str_date = "Date"
            if date_type == "day":
                reminder_date = "Daily"
            elif date_type == "weekday":
                reminder_date = f"{reminder_type.capitalize()} {reminder_date.capitalize()}"

            if date_type == "YYYYMMDD":
                reminder_date = f"{reminder_date[0:4]}-{reminder_date[4:6]}-{reminder_date[6:8]}"

            name = f"ID: `{id}`"
            
            value = f"Target: {target_mention}\nType: `{str_type}`\n{str_date}: `{reminder_date}`\nTime: `{reminder_time[0:2]}:{reminder_time[2:]}`\nDetails: `{reminder_content}`"
            if date_type == "YYYYMMDD":
                reminder_date_unformatted = (reminder[7])
                datetime_date = datetime.datetime(
                    year= int(reminder_date_unformatted[0:4]),
                    month = int(reminder_date_unformatted[4:6]),
                    day = int(reminder_date_unformatted[6:8]),
                    hour = int(reminder_time[0:2]),
                    minute= int(reminder_time[2:])
                )
                value = f"Target: {target_mention}\nType: `{str_type}`\n{str_date}: <t:{int(datetime_date.timestamp())}:F>\nDetails: `{reminder_content}`"
                # await ctx.send(f"<t:{int(datetime_date.timestamp())}:F>")
            formatted_reminders.append([name,value,True])
        
        if not show_all:
            description = f"Showing reminders for this server, use `{get_prefix_value(ctx)}showreminders all` to get reminders for every server."
        else:
            description = "Showing reminders for every server."

        if reminders == []:
            title = f"**No reminders found**"
            if not show_all:
                description = f"You don't have any reminders in this server.\nUse `{get_prefix_value(ctx)}showreminders all` to see reminders for every server."
            else:
                description = f"You don't have any reminders.\nUse `{get_prefix_value(ctx)}help remind` to setup a reminder."
            embed = self.bot.auto_embed(
                type="error",
                title=title,
                description=description,
                ctx=ctx
            )
        else:
            embed = self.bot.auto_embed(
                type="info",
                title=f"**Showing your reminders**",
                description=description,
                fields=formatted_reminders,
                thumbnail=ctx.author.avatar_url,
                ctx=ctx
            )
        if show_all:
            await ctx.author.send(embed=embed)
        else:
            await ctx.send(embed=embed)
        
        if ctx.author.id in TRUSTED_IDS:
            ctx.command.reset_cooldown(ctx)
        self.bot.log_command(ctx,"showreminders",all)

    @command(name="Remind", brief=f"Create a reminder. Examples: {example_reminders}{NL}NOTE: You may only have a maximum of 25 reminders",aliases=["remind","r"])
    async def remind(self, ctx, target, type, date:str, time:str, *, todo) -> db :
        error_msg = []
        datetype = "none"
        for char in ("<",">","@","!"): # Removes mention info from input
            target = target.replace(char,"")

        if len(target) != 18 and target not in ("nobody","me","everyone","here"):
            error_msg.append("Please select a valid target")
        if target == "me":
            target = ctx.author.id
        creator_id = ctx.author.id
        output_guild = ctx.guild.id
        output_channel = ctx.channel.id
        if type not in ("every","on","in"):
            error_msg.append(f"Make sure that you choose either `every`, `on` or `in` instead of `{type}`")

        if type == "in":
            # asumes that date argument is the amount of time and the time argument is the type of time eg seconds, mins, hours
            if not date.isnumeric():
                error_msg.append(f"Make sure you enter a number of time instead of {date}")
            acceptable_times = ["m","min","mins","minute","minutes","h","hour","hours","d","day","days"]
            if time not in acceptable_times:
                error_msg.append(f"Please select a proper delay, you picked {time}\nAvalaible choices: `{acceptable_times}`")
            date = int(date)
            # Setting time delays to datetime formats
            current_datetime = datetime.datetime.today()
            
            if time in ("m","min","mins","minute","minutes"):
                target_datetime = current_datetime + datetime.timedelta(minutes=date)
            if time in ("h","hour","hours"):
                target_datetime = current_datetime + datetime.timedelta(hours=date)
            if time in ("d","day","days"):
                target_datetime = current_datetime + datetime.timedelta(days=date)
            date = target_datetime.date().strftime("%Y%m%d")
            time = target_datetime.time().strftime("%H%M")

            type="on"

        # date types = (weekday, day, date)
        date = date.replace("-","") # Formats YYYY-MM-DD to YYYYMMDD
        date = date.lower() # Formats date to lowercase if it is a weekday
        if len(date) == 8 and date.isdecimal(): # If it is a date (YYYYMMDD) and contains only numbers. This prevents "saturday" and "tomorrow" being acceptable dates
            try: # Validates to be in proper format
                datetime.datetime.strptime(date,"%Y%m%d")
                datetype = "YYYYMMDD"
                if int(date[0:4]) > 3000:
                    error_msg.append("You cannot enter a year above 3000.")
            except:
                error_msg.append(f"Please make sure your date is in `YYYY-MM-DD` format, you entered `{date}`")
        elif date in self.days_of_week:
            datetype = "weekday"
        elif date == "day":
            datetype = "day"
        elif date == "today":
            datetype = "YYYYMMDD"
            date = datetime.date.today().strftime("%Y%m%d")
        elif date == "tomorrow":
            print("Test")
            datetype = "YYYYMMDD"
            date = (datetime.datetime.today())
            tomorrow_date = (date + datetime.timedelta(days=1))
            date = datetime.datetime.strftime(tomorrow_date,"%Y%m%d")
        else:
            
            error_msg.append(f"You have entered the date wrong ({date}), please try again")
        
        if datetype == "YYYYMMDD" and type == "every":
            error_msg.append("You cannot have a reminder for every YYYY-MM-DD date")
        if datetype == "day" and type == "on":
            error_msg.append("You have to specify a day instead of just putting `day`")
        try:
            time_formatted = time.replace(":","")
            datetime.datetime.strptime(time_formatted,"%H%M")
            time = time_formatted
        except:
            error_msg.append(f"Please enter the time correctly, you entered `{time}`")

        reminders_count = db.record("SELECT COUNT(CreatorUserID) FROM Reminders WHERE CreatorUserID = ?", ctx.author.id)[0]
        if reminders_count > 25:
            error_msg.append("You cannot set more than 25 reminders.")
        
        if datetype == "YYYYMMDD":
            current = datetime.datetime.today()
            target_datetime = datetime.datetime(
                        int(date[0:4]),
                        int(date[4:6]),
                        int(date[6:8]), 
                        int(time[0:2]),
                        int(time[2:4])
                        )
            if target_datetime < current:
                error_msg.append("You can not set a reminder in the past.")

        
        if error_msg == []:
            db.execute(
                "INSERT INTO Reminders(CreatorUserID,TargetID,OutputGuildID,OutputChannelID,ReminderType,DateType,ReminderDate,ReminderTime,ReminderContent) VALUES (?,?,?,?,?,?,?,?,?)",
                creator_id,target,output_guild,output_channel,type,datetype,date,time,todo
            )
            db.commit()
            self.load_reminders()
            id = (db.lastrowid())
            if len(str(target)) == 18:
                target_mention = f"<@{target}>"
            else:
                target_mention = f"@{target}"
            if type == "every":
                str_type = "recurring"
                str_date = "Frequency"
            elif type == "on":
                str_type = "single"
                str_date = "Date"
            if datetype == "day":
                date = "Daily"
            elif datetype == "weekday":
                date = f"{type.capitalize()} {date.capitalize()}"

            if datetype == "YYYYMMDD":
                date = f"{date[0:4]}-{date[4:6]}-{date[6:8]}"

            description = f"ID: `{id}`\nTarget: {target_mention}\nType: `{str_type}`\n{str_date}: `{date}`\nTime: `{time[0:2]}:{time[2:]}`\nDetails: `{todo}`"
            embed = self.bot.auto_embed(
                type="info",
                title=f"**Reminder successfully created**",
                description=description,
                thumbnail=ctx.author.avatar_url,
                ctx=ctx
            )
            await ctx.send(embed=embed)
        
        else:
            embed = self.bot.auto_embed(
                type="error",
                title="You have entered one or more arguments wrong",
                description= "\n".join(error_msg)+f"\n\nUse {get_prefix_value(ctx)}help to learn more",
                ctx=ctx
            )
            await ctx.send(embed=embed)
        self.bot.log_command(ctx,"remind",str((creator_id,target,output_guild,output_channel,type,datetype,date,time,todo)))

    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up("reminder")
        print("reminder cog ready!")

def setup(bot):
    bot.add_cog(Reminder(bot))