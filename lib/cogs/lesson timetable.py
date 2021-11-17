"""
------------------------------------------------------------
RETIRED - DO NOT USE
TRANSFERED TO timetable.py
RETIRED - DO NOT USE
------------------------------------------------------------

Lesson scheduler cog for Vitaly Petrov

This cog reads and writes to the database, getting
lesson information and displaying it to any user.

Uses APScheduler to run lesson_sender and lesson_embed
at the time when the lesson is. Not suitable for large
scale deployment

Working commands:

Reload Timetable
Set alert
Schedule
Next Lesson
Current Lesson
Weekly Schedule

Non working commands:

Add lesson
Add Teacher
Add School

To be added:

ID system to add groups, teachers and lessons:

showgroups
showteachers <group>
showlessons [group] [teacher]

"""
__title__ = "Lesson Scheduler"
__author__ = "Bspoones"
__version__ = "1.0.4"
__copyright__ = "Bspoones 2021"



import datetime, discord

from ..db import db
from lib.bot import OWNER_IDS, get_prefix_value

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from discord.errors import InvalidArgument
from discord.ext.commands.errors import BadArgument
from discord.ext.commands import Cog, command
from humanfriendly import format_timespan
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont,ImageColor


# timetable = 0: LessonID, 1: TeacherID, GroupID, DayOfWeek, StartHour, StartMin, Endhour, Endmin, Room

class LessonTimetable(Cog):
    def __init__(self, bot):
        self.bot = bot
        self.WEEK = ('MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN')
        self.DAYS_OF_WEEK = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
        self.FMT = "%H:%M"
        self.__version__ = __version__
        
        self.lesson_scheduler = AsyncIOScheduler()
        self.load_schedule()
    
    def load_schedule(self) -> AsyncIOScheduler:
        
        try: # Prevents multiple schedulers running at the same time
            if (self.lesson_scheduler.state) == 1:
                self.lesson_scheduler.shutdown(wait=False)
            self.lesson_scheduler = AsyncIOScheduler()
        except:
            self.lesson_scheduler = AsyncIOScheduler()
        self.timetable = db.records("SELECT * FROM timetable ORDER BY LessonID")
        for item in self.timetable:
            Type_ID = item[1]
            Type_Info = db.record("SELECT * FROM teachers WHERE TeacherID = ?", Type_ID)
            Group_ID = Type_Info[1]
            Group_Info = db.record("SELECT * FROM groups WHERE GroupID = ?", Group_ID)
            start_hr = item[4]
            start_min = item[5]
            warming_times = Group_Info[5].split()
            warming_times = list(map(int, warming_times))
            actual_warning_times = []
            for element in warming_times:
                start_time = datetime.time(start_hr,start_min)
                tdelta = datetime.timedelta(minutes=element)
                element_time = (datetime.datetime.combine(datetime.date(2, 1, 1), start_time)- tdelta).time()
                if not self.is_time_in_lesson(element_time, item[3], Group_ID):
                    actual_warning_times.append(element)
            if 0 not in actual_warning_times:
                actual_warning_times.append(0)
            
            for element in actual_warning_times:
                start_time = datetime.time(start_hr,start_min)
                updated_time = (datetime.datetime.combine(datetime.date(2, 1, 1), start_time) - datetime.timedelta(minutes=element)).time()
                hour = updated_time.hour
                minute = updated_time.minute
                if element == actual_warning_times[0]:
                    self.lesson_scheduler.add_job(
                        self.lesson_embed,
                        CronTrigger(
                            day_of_week=item[3],
                            hour=hour,
                            minute=minute,
                            second=0
                        ),
                        args=[item, Type_Info, Group_Info, element, actual_warning_times]
                    )
                else:
                    self.lesson_scheduler.add_job(
                        self.lesson_sender,
                        CronTrigger(
                            day_of_week=item[3],
                            hour=hour,
                            minute=minute,
                            second=0
                        ),
                        args=[item, Type_Info, Group_Info, element, actual_warning_times]
                    )
                # print(item)
                # print(hour,minute)
                # print(Group_Info)
                # print(Type_Info)
                # print(actual_warning_times)
                # print("")
            
        self.lesson_scheduler.start()
    
    async def lesson_sender(self,*args) -> discord:
        Timetable_Info = args[0]
        Type_Info = args[1]
        Group_Info = args[2]
        element = args[3]
        actual_warning_times = args[4]

        output_channel = int(Group_Info[3])
        output_role = Group_Info[4]

        if element == 0:
            await self.bot.get_channel(output_channel).send(f"<@&{output_role}> your lesson is now!")
            await self.update_time_channels(Timetable_Info,Group_Info)
        else:
            """
            Deletes message just before the next message is shown. 
            Time is calculated from the time between that message and the next one. 
            E.g if the warning was 10 min and the next was 5 min, 10-5 = 5 so it would stay for 5 min
            """
            element_index = actual_warning_times.index(element)
             # Shouldn't create an error when finding +1 th in a list as the last element is always 0 and is handled by the above statement.
            delete_after = (actual_warning_times[element_index] - actual_warning_times[element_index+1]) * 60 # deleteafter works in seconds
            await self.bot.get_channel(output_channel).send(f"<@&{output_role}> your lesson is in {element} minutes!", delete_after=delete_after)
    
    async def lesson_embed(self,*args) -> discord.Embed:
        Timetable_Info = args[0]
        Type_Info = args[1]
        Group_Info = args[2]
        element = args[3]
        actual_warning_times = args[4]
        FMT = '%H:%M'
        start_time = datetime.time(Timetable_Info[4],Timetable_Info[5]).strftime(FMT)
        end_time = datetime.time(Timetable_Info[6],Timetable_Info[7]).strftime(FMT)
        duration = (datetime.datetime.strptime(end_time,FMT)-datetime.datetime.strptime(start_time,FMT)).total_seconds()
        duration = format_timespan(duration)
        title = f"***{Type_Info[3]} lesson with {Type_Info[2]}***"
        description=f"***In {Timetable_Info[8]}***\n\nStart time: `{start_time}`\nEnd time: `{end_time}`\nLesson duration: `{duration}`"
        colour = int(Type_Info[6],16)
        colour = int(hex(colour),0)
        if Type_Info[5] == "F":
            thumbnail = Group_Info[6]
        else:
            thumbnail = "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9b/Google_Meet_icon_%282020%29.svg/934px-Google_Meet_icon_%282020%29.svg.png"
        embed = self.bot.auto_embed(
            type="lesson",
            title=title, 
            description=description, 
            colour=colour, 
            thumbnail=thumbnail,
            iconurl= thumbnail,
            schoolname = Group_Info[2]
            )
        output_channel = int(Group_Info[3])
        output_role = Group_Info[4]
        await self.bot.get_channel(output_channel).send(embed=embed)
        if element == 0:
            await self.bot.get_channel(output_channel).send(f"<@&{output_role}> your lesson is now!")
            await self.update_time_channels(Timetable_Info,Group_Info)
        else:
            """
            Deletes message just before the next message is shown. 
            Time is calculated from the time between that message and the next one. 
            E.g if the warning was 10 min and the next was 5 min, 10-5 = 5 so it would stay for 5 min
            """
            element_index = actual_warning_times.index(element)
             # Shouldn't create an error when finding +1 th in a list as the last element is always 0 and is handled by the above statement.
            delete_after = (actual_warning_times[element_index] - actual_warning_times[element_index+1]) * 60 # deleteafter works in seconds
            await self.bot.get_channel(output_channel).send(f"<@&{output_role}> your lesson is in {element} minutes!", delete_after=delete_after)
    
    def is_time_in_lesson(self, time, day, Group_ID) -> bool:
        timetable_on_day = db.records("SELECT * FROM timetable WHERE DayOfWeek = ? AND GroupID = ?",day,Group_ID)
        for item in timetable_on_day:
            start_time = datetime.time(item[4], item[5])
            end_time = datetime.time(item[6], item[7])
            if start_time <= end_time:
                if start_time <= time < end_time: # result = True if time is within lesson
                    return True
            # else:
            #     return start_time <= time or time < end_time
        return False
    
    def return_time_in_lesson(self,time,day,Group_ID) -> str:
        timetable_on_day = db.records("SELECT * FROM timetable WHERE DayOfWeek = ? AND GroupID = ?",day,Group_ID)
        for item in timetable_on_day:
            start_time = datetime.time(item[4], item[5])
            end_time = datetime.time(item[6], item[7])
            if start_time <= end_time:
                if start_time <= time < end_time: # result = True if time is within lesson
                    return item
        else:
            return False
    
    async def update_time_channels(self, Timetable_Info, Group_Info) -> discord:
        GroupID = Group_Info[0]
        group_timetable = db.records("SELECT * FROM timetable WHERE GroupID = ? ORDER BY DayOfWeek ASC, StartHour ASC, StartMin ASC", GroupID)

        index = group_timetable.index(Timetable_Info)
        try:
            next_lesson = (group_timetable[index+1])
        except:
            next_lesson = (group_timetable[0])
        day_channel = int(Group_Info[7])
        time_channel = int(Group_Info[8])
        time = datetime.time(next_lesson[4],next_lesson[5]).strftime("%H:%M")
        day = self.DAYS_OF_WEEK[next_lesson[3]]

        await self.bot.get_channel(day_channel).edit(name=f"Next lesson: {day.capitalize()}")
        await self.bot.get_channel(time_channel).edit(name=f"Next lesson time: {time}")

    @command(name="Reload timetable",brief="Reloads the timetable database.", aliases=["reload"])
    async def reloadtimetable(self,ctx) -> str:
        self.load_schedule()
        await ctx.send("Lesson schedule reloaded!")
        self.bot.log_command(ctx,"reloadtimetable")
    
    @command(name="Change Alert",brief="Changes the alert times before your group's lessons.", aliases=["changealert","setalert"])
    async def changealert(self,ctx,*,times) -> str:
        if ctx.author.id in OWNER_IDS:
            times_list = times.split()
            if all(x.isnumeric() for x in times_list):
                if times_list[-1] != "0": # Final item must be 0
                    print(times_list[-1])
                    times_list.append("0")
                warning_times = " ".join(times_list)
                user_id = ctx.author.id
                
                User_Info = db.record("SELECT * FROM students WHERE DiscordID = ?", user_id)
                Group_ID = User_Info[1]
                
                db.execute("UPDATE groups SET AlertTimes = ? WHERE GroupID = ?", warning_times,Group_ID)
                db.commit()

                Group_Info = db.record("SELECT * FROM groups where GroupID = ?", Group_ID)
                
                title = "**Alert times updated!**"
                description = f"Alert times updated for {Group_Info[2]} to be: \n`{warning_times}`."
                
                embed = self.bot.auto_embed(
                    type="info",
                    title=title,
                    description=description,
                    ctx=ctx
                )
                
                await ctx.send(embed=embed)
            else:
                raise BadArgument
        else:
            raise PermissionError
        self.load_schedule()
        self.bot.log_command(ctx,"changealert",Group_ID, warning_times)
            
    @command(name="Schedule",brief="Shows the schedule for a day and a school.",aliases=["schedule","sched"])
    async def schedule(self,ctx,day=None,school=None) -> discord.Embed:
        if day is not None:
            try:
                day.lower() # Used to find index of self.DAYS_OF_WEEK
            except:
                raise InvalidArgument
            if day == "today":
                day = (datetime.datetime.today().weekday())
            elif day == "tomorrow":
                day = datetime.datetime.today().weekday() + 1
                if day == 7:
                    day = 0
            elif day == "yesterday":
                day = datetime.datetime.today().weekday() - 1
                if day == -1:
                    day - 6
            else:
                try:
                    day = self.DAYS_OF_WEEK.index(day)
                except:
                    raise BadArgument
            current_day_of_week = self.DAYS_OF_WEEK[(datetime.datetime.today().weekday())]
            date_day_of_week = self.DAYS_OF_WEEK[day]
            difference = self.DAYS_OF_WEEK.index(date_day_of_week)-self.DAYS_OF_WEEK.index(current_day_of_week)
            if difference < 0:
                difference += 7
            full_date = (datetime.datetime.today()) + datetime.timedelta(days=difference)
            dateformat = full_date.strftime('%d %B')    
        else:
            day = (datetime.datetime.today().weekday())
            dateformat = datetime.datetime.today().strftime('%d %B')

        if school is not None:
            try:
                school = school.lower()
            except:
                raise BadArgument
            Group_Info = db.record("SELECT * FROM groups WHERE GroupCode = ?", school)
            if Group_Info == ():
                raise InvalidArgument
            Group_ID = Group_Info[0]
        else:
            user_id = ctx.author.id
            User_Info = db.record("SELECT * FROM students WHERE DiscordID = ?", user_id)
            Group_ID = User_Info[1]
        lessons = db.records("SELECT * FROM timetable WHERE GroupID = ? AND DayOfWeek = ?", Group_ID, day)
        title=f"Schedule for {self.DAYS_OF_WEEK[day].capitalize()}, {dateformat}"
        fields = []
        for i, lesson in enumerate(lessons,start=1):
            Teacher_info = db.record("SELECT * FROM teachers where TeacherID = ?", lesson[1])
            Group_Info = db.record("SELECT * FROM groups where GroupID = ?", lesson[2])

            start_time = datetime.time(lesson[4],lesson[5]).strftime("%H:%M")
            end_time = datetime.time(lesson[6],lesson[7]).strftime("%H:%M")

            duration = (datetime.datetime.strptime(end_time,self.FMT)-datetime.datetime.strptime(start_time,self.FMT)).total_seconds()
            duration = format_timespan(duration)
            room = lesson[8]
            teacher = Teacher_info[2]
            subject = Teacher_info[3]
            name = f"**Lesson {i}**"
            value = f"Subject: `{subject}`\nTeacher: `{teacher}`\nStart time: `{start_time}`\nEnd time: `{end_time}`\nDuration: `{duration}`\nRoom: `{room}`"
            inline = False
            fields.append((name,value,inline))
        if len(lessons) == 0:
            title = f"**No lessons found**"
            description = f"You don't have any lessons for today\nUse `{get_prefix_value(ctx)}nextlesson` to show your next lesson"
            embed = self.bot.auto_embed(
                type="error",
                title=title,
                description=description,
                ctx=ctx
            )
        else:
            embed = self.bot.auto_embed(
                type="schedule",
                title=title,
                fields=fields,
                ctx=ctx
            )
        await ctx.send(embed=embed)
        self.bot.log_command(ctx,"schedule", day, Group_ID)
    
    @command(name="Next lesson",brief="Shows the next lesson for a school.", aliases=["nl","nextlesson"])
    async def nextlesson(self,ctx, school=None) -> discord.Embed:
        if school is None:
            User_ID = ctx.author.id
            Group_ID = db.record("SELECT GroupID FROM students where DiscordID = ?", User_ID)[0]
            group_timetable = db.records("SELECT * FROM timetable WHERE GroupID = ?", Group_ID)
        else:
            school = school.lower()
            try:
                Group_Info = db.record("SELECT * FROM groups WHERE GroupCode = ?", school)
            except:
                raise InvalidArgument
            Group_ID = Group_Info[0]
            group_timetable = db.records("SELECT * FROM timetable WHERE GroupID = ?", Group_ID)
        if group_timetable == []:
            title = f"**No lessons**"
            description = f"You don't have any lessons in the databse."
            embed = self.bot.auto_embed(
                type="error",
                title=title,
                description= description,
                ctx=ctx
            )
            await ctx.send(embed=embed)
            return
        group_timetable_weekdays = [x[3] for x in group_timetable]
        group_timetable_start_times = [(datetime.time(x[4],x[5])) for x in group_timetable]

        def next_day(current_time, current_date, weekday, start_time):
            day_shift = (weekday - current_date.weekday()) % 7
            if datetime.datetime.today().weekday() == weekday and current_time > start_time: # If lesson is today and has already happened
                day_shift += 7
            return current_date + datetime.timedelta(days=day_shift)

        current_date = datetime.datetime.today().date()
        current_time = datetime.datetime.now().time()
        next_lessons = [next_day(current_time, current_date,weekday,start_time) for weekday,start_time in zip(group_timetable_weekdays,group_timetable_start_times)]
        next_lesson_date = next_lessons.index(min(next_lessons, key=lambda d: abs(d - current_date)))
        lesson = (group_timetable[next_lesson_date])

        Teacher_info = db.record("SELECT * FROM teachers where TeacherID = ?", lesson[1])
        Group_Info = db.record("SELECT * FROM groups where GroupID = ?", lesson[2])
        
        start_time = datetime.time(lesson[4],lesson[5]).strftime("%H:%M")
        end_time = datetime.time(lesson[6],lesson[7]).strftime("%H:%M")
        duration = (datetime.datetime.strptime(end_time,self.FMT)-datetime.datetime.strptime(start_time,self.FMT)).total_seconds()
        duration = format_timespan(duration)
        lesson_day_of_week_str = self.DAYS_OF_WEEK[lesson[3]].capitalize()
        room = lesson[8]
        teacher = Teacher_info[2]
        subject = Teacher_info[3]


        current_time = datetime.datetime.now().strftime(self.FMT)
        next_lesson_date_object = next_lessons[next_lesson_date]
        next_lesson_datetime_object = datetime.datetime(
            next_lesson_date_object.year,
            next_lesson_date_object.month,
            next_lesson_date_object.day,
            lesson[4], 
            lesson[5]
            )
        time_until_end = format_timespan((next_lesson_datetime_object-datetime.datetime.today()).total_seconds())
        
        if datetime.datetime.today().weekday() == lesson[3]: # If the current weekday is the same as the lesson weekday
            title = f"**Next lesson is at {start_time}\n({time_until_end} from now)**"
        else:
            title = f"**Next lesson is at {start_time} on {lesson_day_of_week_str}\n({time_until_end} from now)**"
        description = f"Day of week: `{lesson_day_of_week_str}`\nSubject: `{subject}`\nTeacher: `{teacher}`\nStart time: `{start_time}`\nEnd time: `{end_time}`\nDuration: `{duration}`\nRoom: `{room}`"
        embed = self.bot.auto_embed(
            type="schedule",
            title=title,
            description= description,
            ctx=ctx
        )
        await self.update_time_channels((group_timetable[next_lesson_date-1]),Group_Info)
        await ctx.send(embed=embed)
        self.bot.log_command(ctx,"nextlesson",Group_ID)
    
    @command(name="Current lesson",brief="Shows information about the current lesson.", aliases=["currentlesson"])
    async def currentlesson(self,ctx, school=None) -> discord.Embed:
        if school is None:
            User_ID = ctx.author.id
            Group_ID = db.record("SELECT GroupID FROM students where DiscordID = ?", User_ID)[0]
        else:
            school = school.lower()
            Group_Info = db.record("SELECT * FROM groups WHERE GroupCode = ?", school)
            if Group_Info == ():
                raise InvalidArgument
            Group_ID = Group_Info[0]
        current_time = datetime.datetime.now().time()
        current_weekday = datetime.datetime.today().weekday()
        day_timetable = db.records("SELECT * FROM timetable WHERE GroupID = ? AND DayOfWeek = ?", Group_ID, current_weekday)
        for each_lesson in day_timetable:
            weekday = each_lesson[3]
            lesson = self.return_time_in_lesson(current_time, weekday, Group_ID)
            if lesson != False:
                break
        else:
            title = f"**Not in a lesson**"
            description = f"You are not currently in a lesson.\nTry `{get_prefix_value(ctx)}schedule` to show the list of lessons for today"
            embed = self.bot.auto_embed(
                type="error",
                title=title,
                description= description,
                ctx=ctx
            )
            await ctx.send(embed=embed)
            return
        start_time = datetime.time(lesson[4],lesson[5]).strftime("%H:%M")
        end_time = datetime.time(lesson[6],lesson[7]).strftime("%H:%M")
        duration = (datetime.datetime.strptime(end_time,self.FMT)-datetime.datetime.strptime(start_time,self.FMT)).total_seconds()
        duration = format_timespan(duration)
        lesson_day_of_week = self.DAYS_OF_WEEK[lesson[3]].capitalize()
        room = lesson[8]
        Teacher_info = db.record("SELECT * FROM teachers where TeacherID = ?", lesson[1])
        teacher = Teacher_info[2]
        subject = Teacher_info[3]
        
        current_time = datetime.datetime.now().strftime(self.FMT)
        time_until_end = format_timespan((datetime.datetime.strptime(end_time,self.FMT)-datetime.datetime.strptime(current_time,self.FMT)).total_seconds())

        title = f"**This lesson finishes at {end_time}.\n({time_until_end} from now)**"
        description = f"Day of week: `{lesson_day_of_week}`\nSubject: `{subject}`\nTeacher: `{teacher}`\nStart time: `{start_time}`\nEnd time: `{end_time}`\nDuration: `{duration}`\nRoom: `{room}`"
        embed = self.bot.auto_embed(
            type="schedule",
            title=title,
            description= description,
            ctx=ctx
        )

        await ctx.send(embed=embed)
        self.bot.log_command(ctx,"currentlesson",Group_ID)
    
    @command(name="Weekly schedule",brief="Shows an auto generated image of the timetable for the week.", aliases=["ws","weeklyschedule"])
    async def weeklyschedule(self,ctx,school=None) -> discord.Embed and Image:
        if school is None:
            User_ID = ctx.author.id
            Group_ID = db.record("SELECT GroupID FROM students where DiscordID = ?", User_ID)[0]
        else:
            school = school.lower()
            try:
                Group_Info = db.record("SELECT * FROM groups WHERE GroupCode = ?", school)
            except:
                raise InvalidArgument
            Group_ID = Group_Info[0]

        Group_Info = db.record("SELECT * FROM groups WHERE GroupID = ?", Group_ID)

        wait_message = await ctx.send("Creating image, please wait.....")
        img = Image.new('RGB', size=(7000, 6000), color=(255,255,255))
        font = ImageFont.truetype("./data/fonts/arial.ttf", 90)
        draw = ImageDraw.Draw(img)

        draw.line((0, 500, 7000, 500), fill=(0, 0, 0), width=10) # Draws line at top to seperate day titles and content
        for i in range(20): # Going from 08:00 to 18:00 with lines, totalling 20 half hour increments
            if i % 2 == 0:
                draw.line((0,(1000+(250*i)),7000,(1000+(250*i))),fill=(0,0,0),width=1)
            else:
                draw.line((0,(1000+(250*i)),7000,(1000+(250*i))),fill=(128,128,128),width=1)
        for i,val  in enumerate(self.WEEK):
            # Draw day of week at top
            draw.text((i*1000+400, 200), val, fill=(0,0,0), font=font)
            # Select all lessons for day
            daily_timetable = db.records("SELECT * FROM timetable WHERE GroupID = ? AND DayOfWeek = ?", Group_ID, i)
            
            if i != 6:
                # Prevents extra black line on the right
                draw.line((i*1000+1000, 0, i*1000+1000, 7000), fill=(0, 0, 0), width=10)

            for lesson in daily_timetable:
                start_time = datetime.time(lesson[4],lesson[5]).strftime("%H:%M")
                end_time = datetime.time(lesson[6],lesson[7]).strftime("%H:%M")
                lesson_room = lesson[8]
                teacherID = (lesson[1])
                teacher_info = db.record("SELECT * FROM teachers WHERE TeacherID = ?", teacherID)
                teacher = teacher_info[2]
                hexcolour = str(teacher_info[6])
                colour = ImageColor.getrgb("#"+hexcolour)
                # Starting pad of 1000px, then each hour block counts as 500px. Starting at 08:00
                # E.g - 09:00 is 1500px down, 09:30 is 1750px down
                # Each half an hour increment is 250px, with an initial start point of 1000px down
                start_time_px = 1000+(500*(lesson[4]-8) + 500*(lesson[5]/60))
                end_time_px = 1000+(500*(lesson[6]-8) + 500*(lesson[7]/60))
                block_height = end_time_px-start_time_px
                print(teacher,block_height)
                message =  f"{start_time} - {end_time}\n{lesson_room}\n{teacher}"
                vertical_pad = 30
                if block_height <= 250:
                    # If the lesson is too short for the text to fit into a block
                    message = f"{start_time} - {end_time}\n{lesson_room} {teacher}"
                    vertical_pad = 1

                draw.rectangle((i*1000+100, start_time_px, i*1000+1000-100, end_time_px), fill=(colour), outline=(0, 0, 0)) # Draws rectangle with a 100px padding from the daily line seperators
                if (sum(colour)) <= 254:
                    # If the background colour is too dark then the text changes to white
                    draw.text((i*1000+130, start_time_px+vertical_pad), message, fill=(255,255,255), font=font, stroke_width = 2)
                else:
                    draw.text((i*1000+130, start_time_px+vertical_pad), message, fill=(0,0,0), font=font, stroke_width = 2)
        
        with BytesIO() as image_binary: # Used to turn Pillow image to binary for discord to upload
            img.save(image_binary, 'PNG')
            image_binary.seek(0)
            file=discord.File(fp=image_binary, filename='image.png')
        
        title=f"__**Weekly schedule**__"
        description= f"Use `{get_prefix_value(ctx)}schedule DAY` to find out more information for each day"
        school = Group_Info[2]
        iconurl = Group_Info[6]
        embed = self.bot.auto_embed(
            type="lesson",
            title=title,
            description= description,
            schoolname=school,
            iconurl=iconurl,
            colour = ctx.author.colour,
            ctx=ctx
        )
        embed.set_image(url=f"attachment://image.png")

        await ctx.send(file=file,embed=embed)
        await wait_message.delete()
        self.bot.log_command(ctx,"weeklyschedule",Group_ID)
    
    # @command()
    # async def addschool(self,ctx, group_code, output_channel, output_role, image_link, NLDayChannel, NLTimeChannel,*,School_Name):
    #     pass
    
    # @command()
    # async def addteacher(self,ctx, school, teacher_foremane, teacher_surname, lesson_subject, lesson_link = None):
    #     pass
    
    # @command()
    # async def addlesson(self, ctx, schoolcode, teacher_forename, teacher_surname, day_of_week, start_time, end_time, room):
    #     pass
    
    
    
    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up("lesson timetable")
        print("lesson timetable cog ready!")

def setup(bot):
    # bot.add_cog(LessonTimetable(bot))
    pass
if __name__ == "__main__":
    print("I am an external cog, please run launcher.py to load me")
    exit()