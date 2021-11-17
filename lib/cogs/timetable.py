"""
Timetable cog for Vitaly Petrov

Used to send both lesson reminders and assignment reminders
Uses Apscheduler and SQLite to read from a database and send information
at the correct time.

Intended as a replacement to the old lesson timetable cog, suitable for medium
scale deployment.

Commands:

- Setalert
- Schedule
- Next lesson
- Current lesson
- Weekly schedule
- Add group
- Add teacher
- Add lesson
- Add student
- Remove group
- Remove teacher
- Remove lesson
- Remove student
- Show groups
- Show teachers
- Show lessons
- Show students
- Add assignment
- Remove assignment
- Show assignments
- Beep


"""
from io import BytesIO
from typing import Optional
import asyncio, time
from PIL import Image, ImageDraw, ImageFont,ImageColor
from discord.errors import InvalidArgument
from discord.ext.commands.errors import BadArgument, CheckFailure
from lib.bot import OWNER_IDS, get_prefix_value
from discord.ext.commands import Cog, command
from discord.ext.commands.core import Group, group, has_permissions
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from humanfriendly import format_timespan
import validators, re, random, discord, datetime
from ..db import db
COG_VERSION = "1.1.0"
FMT = '%H:%M'
NL = "\n"
DEFAULT_ASSIGNMENT_WARNING_TIMES = "40320 30240 20160 4320 1440 360 60 10 0"
class Timetable(Cog):
    def __init__(self,bot):
        self.bot = bot
        self.__version__ = COG_VERSION
        self.LONG_DAYS_OF_WEEK = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
        self.SHORT_DAYS_OF_WEEK = ["mon","tue","wed","thu","fri","sat","sun"]

        """
        Using 2 instances of AsyncIOScheduler because it's my code and you can't
        tell me what to do.
        """
        self.lesson_scheduler = AsyncIOScheduler()
        self.assignment_scheduler = AsyncIOScheduler()

        self.load_timetable()
        self.load_assignments()
    
    def get_groupID_from_command(self,ctx,groupID,groupCode) -> list or str:
        error_msg = []
        if all([x is None for x in [groupID,groupCode]]):
            group_info = self.get_group_info_from_userID(ctx.author.id)
            if group_info is None:
                error_msg.append(f"Your ID is not in the database, talk to the group owner if you think this is an issue but for now use {get_prefix_value(ctx)}weeklyschedule GroupID to view the schedule.")
            else:
                groupID = group_info[0]
        elif all([x is None for x in [groupCode]]): # If GroupID is given
            group_info = db.record("SELECT * FROM Groups WHERE GroupID = ?",groupID)
            if group_info is None:
                error_msg.append("That group ID is invalid")
        elif all([x is None for x in [groupID]]): # If GroupCode is given
            group_info = self.get_group_info_from_code(groupCode)
            if group_info is None:
                error_msg.append(f"That Group code is not in the databse, talk to the group owner if you think this is an issue but please check your spelling\nNOTE: Group codes are CaSe SeNsItIvE")
            else:
                groupID = group_info[0]
        if error_msg != []:
            return error_msg
        else:
            return groupID
    def get_group_info_from_userID(self, UserID) -> None or str:
        """
        Searches database for discord user id, returns groupID if found,
        returns None if not found
        """
        GroupID = db.record("SELECT GroupID FROM Students WHERE UserID = ?",UserID) # Will only retrieve first GroupID it find
        if GroupID is not None:
            group_info = db.record("SELECT * FROM Groups WHERE GroupID = ?",GroupID[0])
            if group_info is not None:
                return group_info
        else:
            return None
    def get_group_info_from_code(self, groupcode) -> None or str:
        """
        Searches database for discord user id, returns groupID if found,
        returns None if not found
        """
        GroupInfo = db.record("SELECT * FROM Groups WHERE GroupCode = ?",groupcode)
        if GroupInfo is None:
            return None
        else:
            return GroupInfo
    def get_group_info_from_input(self,group_input: str):
        if group_input.isdigit(): # If a groupID is given
            group_info = db.record("SELECT * FROM Groups WHERE GroupID = ?",group_input)
            return group_info # Will either return groupinfo or None
        else: # If str given it searches group names and group codes
            group_info = db.record("SELECT * FROM Groups WHERE GroupName = ? OR GroupCode = ?",group_input,group_input)
            return group_info
    def get_group_info_from_ID(self,ID):
        return db.record("SELECT * FROM Groups WHERE GroupID = ?",ID)
    def get_teacher_info_from_input(self,teacher_input: str):
        if teacher_input.isdigit(): # If a groupID is given
            teacher_info = db.record("SELECT * FROM Teachers WHERE TeacherID = ?",teacher_input)
            return teacher_info # Will either return groupinfo or None
        else: # If str given it searches group names and group codes
            teacher_info = db.record("SELECT * FROM Teachers WHERE TeacherName = ?",teacher_input)
            return teacher_info
    def get_teacher_info_from_ID(self,ID):
        return db.record("SELECT * FROM Teachers WHERE TeacherID = ?",ID)
    def get_timetable(self,UserID) -> None or str:
        """
        Used to get a timetable for any student given their Discord ID.
        Cam integrate multiple groupIDs
        Returns an array of lessons and a list containing all groupIDs
        Returns a list of GroupIDs if multiple are present
        """
        GroupID = db.records("SELECT GroupID FROM Students WHERE UserID = ?",UserID) # Retrieves all GroupIDs
        NewGroupIDS = []
        
        if GroupID is not None:
            for item in GroupID:
                NewGroupIDS.append(item[0])
            NewGroupIDS = list(map(lambda x: str(x),NewGroupIDS))
            lesson_info = db.records(f"SELECT * FROM Lessons WHERE GroupID IN ({','.join(NewGroupIDS)}) ORDER BY DayOfWeek ASC, StartHour ASC, StartMin ASC")
            if lesson_info is not None:
                return lesson_info, NewGroupIDS
        else:
            return None
    def get_timetable_for_day(self,UserID: int,day_of_week) -> None or str:
        """
        Does the same as self.get_timetable, but is for a specific day
        """
        GroupID = db.records("SELECT GroupID FROM Students WHERE UserID = ?",UserID) # Retrieves all GroupIDs
        NewGroupIDS = []
        
        if GroupID is not None:
            for item in GroupID:
                NewGroupIDS.append(item[0])
            NewGroupIDS = list(map(lambda x: str(x),NewGroupIDS))
            lesson_info = db.records(f"SELECT * FROM Lessons WHERE GroupID IN ({','.join(NewGroupIDS)}) AND DayOfWeek = ? ORDER BY DayOfWeek ASC, StartHour ASC, StartMin ASC",day_of_week)
            if lesson_info is not None:
                return lesson_info, NewGroupIDS
        else:
            return None

    def load_timetable(self):
        """
        Loads in all items in the Lessons table of the database, adding them
        as jobs to the APscheduler
        """
        try: # Prevents multiple schedulers running at the same time
            if (self.lesson_scheduler.state) == 1:
                self.lesson_scheduler.shutdown(wait=False)
            self.lesson_scheduler = AsyncIOScheduler()
        except:
            self.lesson_scheduler = AsyncIOScheduler()
        self.lessons = db.records("SELECT * FROM Lessons ORDER BY LessonID")

        for lesson in self.lessons:
            GroupID = lesson[1]
            TeacherID = lesson[2]
            day_of_week = lesson[3]
            start_hr = lesson[4]
            start_min = lesson[5]
            end_hr = lesson[6]
            end_min = lesson[7]

            Teacher_Info = db.record("SELECT * FROM Teachers WHERE TeacherID = ?",TeacherID)
            Group_Info = db.record("SELECT * FROM Groups WHERE GroupID = ?",GroupID)
            warning_times = Group_Info[12].split()
            warning_times_list = list(map(int,warning_times))
            """
            Below changes the warning times so they only get sent between lessons.
            E.G If a second lesson comes 15 mins after the first, there's no point
            giving a 30 min warning for the 2nd lesson as it will be during the first
            lesson
            """
            actual_warning_times = []
            for time in warning_times_list:
                start_time = datetime.time(start_hr,start_min)
                tdelta = datetime.timedelta(minutes=time)
                element_time = (datetime.datetime.combine(datetime.date(2, 1, 1), start_time)- tdelta).time()
                if not self.is_time_in_lesson(element_time, day_of_week, GroupID):
                    actual_warning_times.append(time)

            if 0 not in actual_warning_times:
                actual_warning_times.append(0)
            
            for element in actual_warning_times:
                start_time = datetime.time(start_hr,start_min)
                updated_time = (datetime.datetime.combine(datetime.date(2, 1, 1), start_time) - datetime.timedelta(minutes=element)).time()
                hour = updated_time.hour
                minute = updated_time.minute
                if element == actual_warning_times[0]: # First thing that gets sent in a lesson announcement
                    self.lesson_scheduler.add_job(
                        self.send_lesson_embed,
                        CronTrigger(
                            day_of_week=day_of_week,
                            hour=hour,
                            minute=minute,
                            second=0
                        ),
                        args=[lesson, Teacher_Info, Group_Info, element, actual_warning_times]
                    )
                    self.lesson_scheduler.add_job(
                        self.send_lesson_countdown,
                        CronTrigger(
                            day_of_week=day_of_week,
                            hour=hour,
                            minute=minute,
                            second=0
                        ),
                        args=[lesson, Teacher_Info, Group_Info, element, actual_warning_times]
                    )
                else: # All other countdown warnings afterwards
                    self.lesson_scheduler.add_job(
                        self.send_lesson_countdown,
                        CronTrigger(
                            day_of_week=day_of_week,
                            hour=hour,
                            minute=minute,
                            second=0
                        ),
                        args=[lesson, Teacher_Info, Group_Info, element, actual_warning_times]
                    )            
        self.lesson_scheduler.start()
    
    def load_assignments(self): # UNFINISHED
        try: # Prevents multiple schedulers running at the same time
            if (self.assignment_scheduler.state) == 1:
                self.assignment_scheduler.shutdown(wait=False)
            self.assignment_scheduler = AsyncIOScheduler()
        except:
            self.assignment_scheduler = AsyncIOScheduler()
        self.assignments = db.records("SELECT * FROM Assignments ORDER BY AssignmentID")
        warning_times = DEFAULT_ASSIGNMENT_WARNING_TIMES.split()
        warning_times_list = list(map(int,warning_times))
        today = datetime.datetime.today()
        for assignment in self.assignments:
            date = assignment[4]
            time = assignment[5]
            date_time = date+time
            date_object = datetime.datetime.strptime(date_time,"%Y%m%d%H%M")
            actual_warning_datetimes = []
            """
            Next section finds out which warning times are applicable
            Finds out if any times from DEFAULT_ASSIGNMENT_WARNING_TIMES
            are before today's date. If so then it does not load them, saving
            memory
            """
            for time in warning_times_list:
                tdelta = datetime.timedelta(minutes=time)
                element_datetime = date_object - tdelta
                if element_datetime > today:
                    actual_warning_datetimes.append(element_datetime)
            
            for element in actual_warning_datetimes: # Sends countdown embeds but not the final embed
                self.assignment_scheduler.add_job(
                    self.send_assignment_countdown,
                    CronTrigger(
                        year = element.year,
                        month = element.month,
                        day = element.day,
                        hour = element.hour,
                        minute = element.minute,
                        second = element.second
                    ),
                    args=[assignment,element,actual_warning_datetimes]
                )
        self.assignment_scheduler.start()

    async def send_lesson_countdown(self,*args):
        lesson_info = args[0]
        teacher_info = args[1]
        Group_Info = args[2]
        element = args[3]
        actual_warning_times = args[4]

        output_channel = int(Group_Info[8])
        output_role = Group_Info[5]
        
        if element == actual_warning_times[0]:
            await asyncio.sleep(2) # Makes sure that the announcement comes after the embed
        if element == 0:
            await self.bot.get_channel(output_channel).send(f"<@&{output_role}> your lesson is now!")
            await self.update_time_channels(lesson_info,Group_Info)
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
    async def send_lesson_embed(self,*args):
        lesson_info = args[0]
        teacher_info = args[1]
        Group_Info = args[2]
        element = args[3]
        actual_warning_times = args[4]
        
        start_time = datetime.time(lesson_info[4],lesson_info[5]).strftime(FMT)
        end_time = datetime.time(lesson_info[6],lesson_info[7]).strftime(FMT)
        duration = (datetime.datetime.strptime(end_time,FMT)-datetime.datetime.strptime(start_time,FMT)).total_seconds()
        duration = format_timespan(duration)
        room = lesson_info[8]

        lesson_teacher = teacher_info[2]
        lesson_subject = teacher_info[3]
        title = f"***{lesson_subject} lesson with {lesson_teacher}***"
        description=f"***In {room}***\n> Start time: `{start_time}`\n> End time: `{end_time}`\n> Duration: `{duration}`"
        group_hex_colour = Group_Info[6]
        teacher_hex_colour = teacher_info[4]
        colour=discord.Colour(int(f"0x{teacher_hex_colour}", 16))
        teacher_link = teacher_info[5]
        if teacher_link is None:
            thumbnail = Group_Info[11]
        else:
            thumbnail = "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9b/Google_Meet_icon_%282020%29.svg/934px-Google_Meet_icon_%282020%29.svg.png"
        embed = self.bot.auto_embed(
            type="lesson",
            title=title, 
            description=description, 
            colour=colour, 
            thumbnail=thumbnail,
            iconurl= thumbnail,
            schoolname = Group_Info[4]
            )
        output_channel = int(Group_Info[8])
        await self.bot.get_channel(output_channel).send(embed=embed)

    async def send_assignment_countdown(self,*args):
        assignment = args[0]
        element = args[1]
        warning_datetimes= args[2]

        assignment_id = assignment[0]
        creator_id = assignment[1]
        group_id = assignment[2]
        teacher_id = assignment[3]
        assignment_todo = assignment[6]
        due_datetime: datetime.datetime  = warning_datetimes[-1] # Last item in list is always the due date
        group_info = self.get_group_info_from_ID(group_id)
        thumbnail = group_info[11]
        output_channel = int(group_info[8])

        if teacher_id != "none":
            teacher_info = self.get_teacher_info_from_ID(teacher_id)
            teacher_hex_colour = teacher_info[4]
            lesson_teacher = teacher_info[2]
            lesson_subject = teacher_info[3]
            colour=discord.Colour(int(f"0x{teacher_hex_colour}", 16))
            title = f"***{assignment_todo} for {lesson_teacher}***"
        else:
            group_hex_colour = group_info[6]
            colour=discord.Colour(int(f"0x{group_hex_colour}", 16))
            title = f"***{assignment_todo}***"
        
        if element != warning_datetimes[-1]: # For all items except final one
            description=f"**Due: <t:{int(due_datetime.timestamp())}:F>**\nWhich is <t:{int(due_datetime.timestamp())}:R>"
            
            
            embed = self.bot.auto_embed(
                type="lesson",
                title=title, 
                description=description, 
                colour=colour, 
                thumbnail=thumbnail,
                iconurl= thumbnail,
                schoolname = group_info[4]
                )
            await self.bot.get_channel(output_channel).send(embed=embed)
        else:
            await self.bot.get_channel(output_channel).send(f"{assignment_todo} due now! Make sure you hand it in")
            db.execute("DELETE FROM Assignments WHERE AssignmentID = ?",assignment_id)
            db.commit()


    def send_assignment_embed():
        pass
    
    def is_time_in_lesson_currentlesson(self, time, day, lessons):
        for item in lessons:
            start_time = datetime.time(item[4], item[5])
            end_time = datetime.time(item[6], item[7])
            if start_time <= end_time:
                if start_time <= time < end_time: # result = True if time is within lesson
                    try:
                        return True,item # Returns both True and the item to specify
                                         # which lesson is in the timetable
                    except:
                        return False
        return False
    def is_time_in_lesson(self, time, day, Group_ID) -> bool:
        timetable_on_day = db.records("SELECT * FROM Lessons WHERE DayOfWeek = ? AND GroupID = ?",day,Group_ID)
        for item in timetable_on_day:
            start_time = datetime.time(item[4], item[5])
            end_time = datetime.time(item[6], item[7])
            if start_time <= end_time:
                if start_time <= time < end_time: # result = True if time is within lesson
                    return True
        return False
    
    def get_next_lesson():
        pass
    
    async def update_time_channels(self, Timetable_Info, Group_Info) -> discord:
        """
        Takes an arg of the current lesson, then takes all lessons for the day
        and finds the next lesson in the list, working out the titles for the
        next lesson headers
        """
        if isinstance(Group_Info,list): # Nextlesson will give a list if multiple gropIDs are used
            lessons = db.records(f"SELECT * FROM Lessons WHERE GroupID IN ({','.join(Group_Info)}) ORDER BY DayOfWeek ASC, StartHour ASC, StartMin ASC")

        else: # If func is run through send_lesson
            GroupID = Timetable_Info[1]
            lessons = db.records("SELECT * FROM Lessons WHERE GroupID = ? ORDER BY DayOfWeek ASC, StartHour ASC, StartMin ASC", GroupID)
        index = lessons.index(Timetable_Info)
        try:
            next_lesson = (lessons[index+1])
        except: # If it is the user's last lesson at the end of the week, it will wrap around to the start of the week
            next_lesson = (lessons[0])
        next_lesson_GroupID = next_lesson[1]
        Group_Info = db.record("SELECT * FROM Groups WHERE GroupID = ?",next_lesson_GroupID)
        day_channel = int(Group_Info[9])
        time_channel = int(Group_Info[10])
        start_time = datetime.time(next_lesson[4],next_lesson[5]).strftime("%H:%M")
        end_time = datetime.time(next_lesson[6],next_lesson[7]).strftime("%H:%M")
        
        day = self.LONG_DAYS_OF_WEEK[next_lesson[3]]

        await self.bot.get_channel(day_channel).edit(name=f"Next lesson: {day.capitalize()}")
        await self.bot.get_channel(time_channel).edit(name=f"Time: {start_time} - {end_time}")
    

    def is_image_link_valid(self, link) -> bool:
        if link is not None:
            return validators.url(link)
    
    def validate_hex_code(self,hex) -> bool:
        if hex is not None:
            match = re.search(r'^(?:[0-9a-fA-F]{3}){1,2}$', hex)
            return match
    
    def random_hex_colour(self) -> str:
        hex = "{:06x}".format(random.randint(0, 0xFFFFFF))
        return hex

    def generate_image_from_group_ID(self,groupID) -> Image:
        
        img = Image.new('RGB', size=(7000, 6000), color=(255,255,255))
        font = ImageFont.truetype("./data/fonts/comicsans.ttf", 90)
        draw = ImageDraw.Draw(img)

        draw.line((0, 500, 7000, 500), fill=(0, 0, 0), width=10) # Draws line at top to seperate day titles and content
        for i in range(20): # Going from 08:00 to 18:00 with lines, totalling 20 half hour increments
            if i % 2 == 0:
                draw.line((0,(1000+(250*i)),7000,(1000+(250*i))),fill=(0,0,0),width=1)
            else:
                draw.line((0,(1000+(250*i)),7000,(1000+(250*i))),fill=(128,128,128),width=1)
        for i,val  in enumerate(self.SHORT_DAYS_OF_WEEK):
            # Draw day of week at top
            draw.text((i*1000+400, 200), val.upper(), fill=(0,0,0), font=font)
            # Select all lessons for day
            daily_timetable = db.records("SELECT * FROM Lessons WHERE GroupID = ? AND DayOfWeek = ? ORDER BY DayOfWeek ASC, StartHour ASC, StartMin ASC", groupID, i)
            
            if i != 6:
                # Prevents extra black line on the right
                draw.line((i*1000+1000, 0, i*1000+1000, 7000), fill=(0, 0, 0), width=10)

            for lesson in daily_timetable:
                start_time = datetime.time(lesson[4],lesson[5]).strftime("%H:%M")
                end_time = datetime.time(lesson[6],lesson[7]).strftime("%H:%M")
                lesson_room = lesson[8]
                teacherID = (lesson[2])
                teacher_info = db.record("SELECT * FROM teachers WHERE TeacherID = ?", teacherID)
                teacher = teacher_info[2]
                hexcolour = str(teacher_info[4])
                colour = ImageColor.getrgb("#"+hexcolour)
                # Starting pad of 1000px, then each hour block counts as 500px. Starting at 08:00
                # E.g - 09:00 is 1500px down, 09:30 is 1750px down
                # Each half an hour increment is 250px, with an initial start point of 1000px down
                start_time_px = 1000+(500*(lesson[4]-8) + 500*(lesson[5]/60))
                end_time_px = 1000+(500*(lesson[6]-8) + 500*(lesson[7]/60))
                block_height = end_time_px-start_time_px
                message =  f"{start_time} - {end_time}\n{lesson_room}\n{teacher}"
                vertical_pad = 30
                if block_height <= 250:
                    # If the lesson is too short for the text to fit into a block
                    message = f"{start_time} - {end_time}\n{lesson_room} {teacher}"
                    vertical_pad = 1

                draw.rectangle((i*1000+100, start_time_px, i*1000+1000-100, end_time_px), fill=(colour), outline=(0, 0, 0)) # Draws rectangle with a 100px padding from the daily line seperators
                if (sum(colour)) <= 290:
                    # If the background colour is too dark then the text changes to white
                    draw.text((i*1000+130, start_time_px+vertical_pad), message, fill=(255,255,255), font=font, stroke_width = 2)
                else:
                    draw.text((i*1000+130, start_time_px+vertical_pad), message, fill=(0,0,0), font=font, stroke_width = 2)
        
        with BytesIO() as image_binary: # Used to turn Pillow image to binary for discord to upload
            img.save(image_binary, 'PNG')
            image_binary.seek(0)
            file=discord.File(fp=image_binary, filename='image.png')
        return file
    @command(name="Set Alert",brief="Sets the alert times before your group's lessons. NOTE: Use a period (.) as a seperator for alert times. e.g 20.10.5.1", aliases=["changealert","setalert"])
    async def setalert(self,ctx,times, groupID: Optional[int] = None, groupCode: Optional[str] = None):
        """
        Sets the alert times for a given group. Groups are auto decided as only
        the group creator can change the alert times.
        Input is a list of minutes seperated by 
        spaces.

        e.g: setalert 30 15 10 5 (0)

        Input list is split into a proper list and ordered. Any duplicates are
        removed. If a 0 is not present at the end of an input, it is added in
        order to send the correct result.
        """
        groupID = self.get_groupID_from_command(ctx,groupID,groupCode)
        if isinstance(groupID, list):
            error_msg = groupID
            error_embed = self.bot.auto_embed(
                type="error",
                title="You have entered one or more arguments wrong",
                description= "\n".join(error_msg)+f"\n\nUse `{get_prefix_value(ctx)}help removegroup` to learn more",
                ctx=ctx
            )
            return await ctx.send(embed=error_embed)
        group_info = db.record("SELECT * FROM Groups WHERE GroupID = ?",groupID)
        group_owner_id = group_info[1]
        if ctx.author.id == group_owner_id:
            times_list = times.split(".")
            if all(x.isnumeric() for x in times_list):
                if times_list[-1] != "0": # Final item must be 0
                    times_list.append("0")
                warning_times = " ".join(times_list)
                
                db.execute("UPDATE groups SET AlertTimes = ? WHERE GroupID = ?", warning_times,groupID)
                db.commit()
                
                title = "**Alert times updated!**"
                warning_times_formatted = [f'> `{warning_time}` minutes before.' for warning_time in times_list]
                description = f"Alert times updated for {group_info[3]} to be: \n{NL.join(warning_times_formatted)}"
                
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
        self.load_timetable()
        self.bot.log_command(ctx,"changealert",groupID, warning_times)

    @command(name="Schedule",brief="Shows the schedule for a day and a school.",aliases=["timetable","schedule","sched"])
    async def schedule(self,ctx, day_input = None, user: Optional[discord.Member] = None, groupID: Optional[int] = None, groupCode: Optional[str] = None):
        """
        Shows a schedule for a given day.
        Day is chosen by either an input or is the current day of week.
        Group is either auto decided from UserID or chosen as an argument.
        
        e.g: schedule tomorrow bcot

        Command retrieves timetable from Group arg and returns in Embed form.
        Assignments are also added as an Embed description.
        Length of breaks and lessons are also shown.
        """

        if day_input is not None:
            try:
                day_input = day_input.lower() # Used to find index of self.DAYS_OF_WEEK
            except:
                raise InvalidArgument
            if day_input == "today":
                day = (datetime.datetime.today().weekday())
            elif day_input == "tomorrow":
                day = datetime.datetime.today().weekday() + 1
                if day == 7:
                    day = 0
            elif day_input == "yesterday":
                day = datetime.datetime.today().weekday() - 1
                if day == -1:
                    day = 6
            else:
                for i,val in enumerate(self.LONG_DAYS_OF_WEEK):
                    if val.startswith(day_input) and len(day_input) > 2: 
                        # Used to allow any segment of a day (thurs, thu etc)
                        # Has to be 2 chars as T could mean tues and thurs.
                        day = i
                        break
                # if day_input in self.LONG_DAYS_OF_WEEK:
                #     day = self.LONG_DAYS_OF_WEEK.index(day_input)
                # elif day_input in self.SHORT_DAYS_OF_WEEK:
                #     day = self.SHORT_DAYS_OF_WEEK.index(day_input)
                else:
                    raise BadArgument
            current_day_of_week = self.LONG_DAYS_OF_WEEK[(datetime.datetime.today().weekday())]
            date_day_of_week = self.LONG_DAYS_OF_WEEK[day]
            difference = self.LONG_DAYS_OF_WEEK.index(date_day_of_week)-self.LONG_DAYS_OF_WEEK.index(current_day_of_week)
            if difference < 0:
                difference += 7
            full_date = (datetime.datetime.today()) + datetime.timedelta(days=difference)
            dateformat = full_date.strftime('%d %B')    
        else:
            full_date = (datetime.datetime.today())
            day = (datetime.datetime.today().weekday())
            dateformat = datetime.datetime.today().strftime('%d %B')
        
        if all([x is None for x in [groupID,groupCode]]):
            daily_lessons, GroupIDs = self.get_timetable_for_day(ctx.author.id if user is None else user.id, day)
            GroupID = GroupIDs
        else:
            NewgroupID = self.get_groupID_from_command(ctx,groupID,groupCode)     
            if isinstance(NewgroupID, list):
                error_msg = NewgroupID
                error_embed = self.bot.auto_embed(
                    type="error",
                    title="You have entered one or more arguments wrong",
                    description= "\n".join(error_msg)+f"\n\nUse `{get_prefix_value(ctx)}help removegroup` to learn more",
                    ctx=ctx
                )
                return await ctx.send(embed=error_embed)
            daily_lessons = db.records("SELECT * FROM Lessons WHERE GroupID = ? AND DayOfWeek = ? ORDER BY StartHour ASC, StartMin ASC", NewgroupID, day)
            GroupID = NewgroupID
            
        fields = []
        total_lesson_time = 0
        for i, lesson in enumerate(daily_lessons,start=1):
            Teacher_info = db.record("SELECT * FROM teachers where TeacherID = ?", lesson[2])

            start_time = datetime.time(lesson[4],lesson[5]).strftime("%H:%M")
            end_time = datetime.time(lesson[6],lesson[7]).strftime("%H:%M")

            duration = (datetime.datetime.strptime(end_time,FMT)-datetime.datetime.strptime(start_time,FMT)).total_seconds()
            total_lesson_time += duration
            duration = format_timespan(duration)
            room = lesson[8]
            teacher = Teacher_info[2]
            subject = Teacher_info[3]
            name = f"**Lesson {i}**"
            value = f"> Subject: `{subject}`\n> Teacher: `{teacher}`\n> Time: `{start_time} - {end_time} ({duration})`\n> Room: `{room}`"
            inline = False
            fields.append((name,value,inline))
        if len(daily_lessons) == 0:
            title = f"**No lessons found**"
            description = f"You don't have any lessons {'today' if day_input is None else 'that day'}\nUse `{get_prefix_value(ctx)}nextlesson` to show your next lesson"
            embed = self.bot.auto_embed(
                type="error",
                title=title,
                description=description,
                ctx=ctx
            )
        else:
            # Finds total length of day from start of first lesson to end of last lesson
            day_start_time = datetime.time(daily_lessons[0][4],daily_lessons[0][5]).strftime("%H:%M")
            day_end_time = datetime.time(daily_lessons[-1][6],daily_lessons[-1][7]).strftime("%H:%M")
            day_duration = (datetime.datetime.strptime(day_end_time,FMT)-datetime.datetime.strptime(day_start_time,FMT)).total_seconds()
            total_break_time = day_duration - total_lesson_time
            # Handles assignments for the day
            day_str = full_date.strftime("%Y%m%d")
            if isinstance(GroupID,list):
                assignments = db.records(f"SELECT * FROM Assignments WHERE GroupID IN ({','.join(GroupID)}) AND DueDate = ?",day_str)
            else:
                assignments = db.records(f"SELECT * FROM Assignments WHERE GroupID = ? AND DueDate = ?",GroupID,day_str)
            assignment_output = ""
            if assignments != []:
                date_fmt = '%Y%m%d%H%M'
                assignment_output = f"**Assignments for today**\n{NL.join([f'{assignment[6]} <t:{int(datetime.datetime.strptime(assignment[4]+assignment[5],date_fmt).timestamp())}:R>' for assignment in assignments])}"
            title=f"Schedule for {self.LONG_DAYS_OF_WEEK[day].capitalize()}, {dateformat}"
            description = f"{assignment_output}\n\nTotal lesson time: `{format_timespan(total_lesson_time)}`\nTotal break time: `{format_timespan(total_break_time)}`"
            embed = self.bot.auto_embed(
                type="schedule",
                title=title,
                description=description, 
                fields=fields,
                ctx=ctx
            )
        await ctx.send(embed=embed)

        if groupID is None and groupCode is None:
            groupID = GroupIDs
        self.bot.log_command(ctx,"schedule", day, groupID)
    @command(name="Next lesson",brief="Shows the next lesson for a school.", aliases=["nl","nextlesson"])
    async def nextlesson(self,ctx,user: Optional[discord.Member] = None, groupID: Optional[int] = None, groupCode: Optional[str] = None ):
        """
        Shows information for your next lesson.
        Takes a group as an arg or auto decides it from userID.
        Retrieves timetable and retrieves the next lesson.
        Outputs the next lesson in Embed form.
        """
        if all([x is None for x in [groupID,groupCode]]):
            lessons, GroupIDs = self.get_timetable(ctx.author.id if user is None else user.id)
            GroupID = GroupIDs
        else:
            NewgroupID = self.get_groupID_from_command(ctx,groupID,groupCode)    
            if isinstance(NewgroupID, list):
                error_msg = NewgroupID
                error_embed = self.bot.auto_embed(
                    type="error",
                    title="You have entered one or more arguments wrong",
                    description= "\n".join(error_msg)+f"\n\nUse `{get_prefix_value(ctx)}help showgroups` to learn more",
                    ctx=ctx
                )
                return await ctx.send(embed=error_embed)
            GroupID = NewgroupID
            lessons = db.records("SELECT * FROM Lessons WHERE GroupID = ? ORDER BY DayOfWeek ASC, StartHour ASC, StartMin ASC", NewgroupID)
        
        if lessons == []:
            title = f"**No lessons**"
            description = f"You don't have any lessons in the database."
            embed = self.bot.auto_embed(
                type="error",
                title=title,
                description= description,
                ctx=ctx
            )
            return await ctx.send(embed=embed)
        group_timetable_weekdays = [x[3] for x in lessons] # Gets a list of the days of the week in the lesson database
        group_timetable_start_times = [(datetime.time(x[4],x[5])) for x in lessons] # gets a list of start times

        def next_day(current_time, current_date, weekday, start_time):
            day_shift = (weekday - current_date.weekday()) % 7
            if datetime.datetime.today().weekday() == weekday and current_time > start_time: # If lesson is today and has already happened
                day_shift += 7
            return current_date + datetime.timedelta(days=day_shift)

        current_date = datetime.datetime.today().date()
        current_time = datetime.datetime.now().time()
        next_lessons = [next_day(current_time, current_date,weekday,start_time) for weekday,start_time in zip(group_timetable_weekdays,group_timetable_start_times)]
        next_lesson_date = next_lessons.index(min(next_lessons, key=lambda d: abs(d - current_date))) # Finds the index of the next lesson
        lesson = (lessons[next_lesson_date])

        Group_Info = db.record("SELECT * FROM groups where GroupID = ?", lesson[1])
        Teacher_info = db.record("SELECT * FROM teachers where TeacherID = ?", lesson[2])
        
        start_time = datetime.time(lesson[4],lesson[5]).strftime("%H:%M")
        end_time = datetime.time(lesson[6],lesson[7]).strftime("%H:%M")
        duration = (datetime.datetime.strptime(end_time,FMT)-datetime.datetime.strptime(start_time,FMT)).total_seconds()
        duration = format_timespan(duration)
        lesson_day_of_week_str = self.LONG_DAYS_OF_WEEK[lesson[3]].capitalize()
        room = lesson[8]
        teacher = Teacher_info[2]
        subject = Teacher_info[3]


        current_time = datetime.datetime.now().strftime(FMT)
        next_lesson_date_object = next_lessons[next_lesson_date]
        next_lesson_datetime_object = datetime.datetime(
            next_lesson_date_object.year,
            next_lesson_date_object.month,
            next_lesson_date_object.day,
            lesson[4], 
            lesson[5]
            )
        next_lesson_unix_time = int(time.mktime(next_lesson_datetime_object.timetuple()))

        if datetime.datetime.today().weekday() == lesson[3]: # If the current weekday is the same as the lesson weekday
            title = f"**Next lesson:**\n<t:{next_lesson_unix_time}:t> (<t:{next_lesson_unix_time}:R>)"
        else:
            title = f"**Next lesson:**\n<t:{next_lesson_unix_time}:F>\n(<t:{next_lesson_unix_time}:R>)"
        description = f"> Day: `{lesson_day_of_week_str}`\n> Subject: `{subject}`\n> Teacher: `{teacher}`\n> Time: `{start_time} - {end_time} ({duration})`\n> Room: `{room}`"
        embed = self.bot.auto_embed(
            type="schedule",
            title=title,
            description= description,
            ctx=ctx
        )
        if groupID is None and groupCode is None:
            groupID = GroupIDs
        await self.update_time_channels((lessons[next_lesson_date-1]),GroupID) # Gives current lesson
        await ctx.send(embed=embed)
        
        self.bot.log_command(ctx,"nextlesson",groupID)
    @command(name="Current lesson",brief="Shows information about the current lesson.", aliases=["currentlesson","cul"])
    async def currentlesson(self,ctx, user: Optional[discord.Member] = None, groupID: Optional[int] = None, groupCode: Optional[str] = None):
        """
        Shows information on the current lesson
        Takes a group as an arg or auto decides it from UserID.
        Retrieves timetable and checks if any of the lessons are the same day
        and within the same time as the current time.
        Outputs the current lesson in Embed form
        
        Shows time left until the end of lesson
        """
        current_time = datetime.datetime.now().time()
        current_weekday = datetime.datetime.today().weekday()
        if all([x is None for x in [groupID,groupCode]]):
            lessons, GroupIDs = self.get_timetable_for_day(ctx.author.id if user is None else user.id, current_weekday)
            GroupID = GroupIDs
        else:
            NewgroupID = self.get_groupID_from_command(ctx,groupID,groupCode)     
            if isinstance(NewgroupID, list):
                error_msg = NewgroupID
                error_embed = self.bot.auto_embed(
                    type="error",
                    title="You have entered one or more arguments wrong",
                    description= "\n".join(error_msg)+f"\n\nUse `{get_prefix_value(ctx)}help removegroup` to learn more",
                    ctx=ctx
                )
                return await ctx.send(embed=error_embed)
            lessons = db.records("SELECT * FROM Lessons WHERE GroupID = ? AND DayOfWeek = ? ORDER BY DayOfWeek ASC, StartHour ASC, StartMin ASC", NewgroupID, current_weekday)
        
        for each_lesson in lessons:
            weekday = each_lesson[3]
            try:
                is_time,lesson = self.is_time_in_lesson_currentlesson(current_time, weekday, lessons)
                if is_time:
                    break
            except:
                pass
        else:
            title = f"**Not in a lesson**"
            description = f"You are not currently in a lesson.\nTry `{get_prefix_value(ctx)}schedule` to show the list of lessons for today"
            embed = self.bot.auto_embed(
                type="error",
                title=title,
                description= description,
                ctx=ctx
            )
            return await ctx.send(embed=embed)
        start_time = datetime.time(lesson[4],lesson[5]).strftime("%H:%M")
        end_time = datetime.time(lesson[6],lesson[7]).strftime("%H:%M")
        duration = (datetime.datetime.strptime(end_time,FMT)-datetime.datetime.strptime(start_time,FMT)).total_seconds()
        duration = format_timespan(duration)
        lesson_day_of_week = self.LONG_DAYS_OF_WEEK[lesson[3]].capitalize()
        room = lesson[8]
        Teacher_info = db.record("SELECT * FROM teachers where TeacherID = ?", lesson[2])
        teacher = Teacher_info[2]
        subject = Teacher_info[3]
        
        current_time = datetime.datetime.now().strftime(FMT)
        time_until_end = format_timespan((datetime.datetime.strptime(end_time,FMT)-datetime.datetime.strptime(current_time,FMT)).total_seconds())

        title = f"**This lesson finishes at {end_time}.\n({time_until_end} from now)**"
        description = f"> Day: `{lesson_day_of_week}`\n> Subject: `{subject}`\n> Teacher: `{teacher}`\n> Time: `{start_time} - {end_time} ({duration})`\n> Room: `{room}`"
        embed = self.bot.auto_embed(
            type="schedule",
            title=title,
            description= description,
            ctx=ctx
        )

        await ctx.send(embed=embed)
        if groupID is None and groupCode is None:
            groupID = GroupIDs
        self.bot.log_command(ctx,"currentlesson",groupID)
    @command(name="Weekly Schedule",brief="Shows an auto generated image of your weekly timetable",aliases=["weeklytimetable","wt","ws","weeklyschedule"])
    async def weeklyschedule(self,ctx,groupID: Optional[int] = None, groupCode: Optional[str] = None):
        """
        Uses Pillow to create an image from a timetable.
        Takes a group as an arg or decides it from UseriD.
        Retrieves timetable from Group and turns it into an image.
        """
        error_msg = []
        if groupID is None and groupCode is None:
            group_info = self.get_group_info_from_userID(ctx.author.id)
            if group_info is None:
                error_msg.append(f"Your ID is not in the database, talk to the group owner if you think this is an issue but for now use {get_prefix_value(ctx)}weeklyschedule GroupID to view the schedule.")
        else:
            group_info = db.record("SELECT * FROM Groups WHERE GroupID = ?",groupID)
            if group_info is None:
                error_msg.append("That group ID is invalid")
        if error_msg != []:
            error_embed = self.bot.auto_embed(
                type="error",
                title="You have entered one or more arguments wrong",
                description= "\n".join(error_msg)+f"\n\nUse `{get_prefix_value(ctx)}help removegroup` to learn more",
                ctx=ctx
            )
            return await ctx.send(embed=error_embed)
        groupID = group_info[0]
        wait_message = await ctx.send("Creating image, please wait.....")

        file = self.generate_image_from_group_ID(groupID)
        
        title=f"__**Weekly schedule**__"
        description= f"Use `{get_prefix_value(ctx)}schedule DAY` to find out more information for each day"
        school = group_info[4]
        iconurl = group_info[11]
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
        self.bot.log_command(ctx,"weeklyschedule",groupID)

    @command(name="Add Group",brief="Adds group to the timetable database. NOTE: Use a period (.) for a seperator for multi word names. e.g: A.Multi.Word.School",aliases=["addgroup"])
    @has_permissions(administrator=True)
    async def addgroup(self,ctx,group_code, group_name, group_image_link = None, group_hex_colour = None):
        """
        Requires admin permission in discord

        Adds a group / school to the database.
        Takes a group code (10 char limit)
        Takes a group name (multi word)
        Takes a group image link (Optional)
        Takes a group hex colour (Optional, randomly generated if not present)

        Creates a category containing
         - lesson announcement text channel
         - Next lesson day voice channel
         - Next lesson time voice channel
        Creates a role of the group code
        Category only visible by role
        Sets a default alert times
        
        Outputs confirmation of creation showing:
         - Group ID
         - Group Owner
         - Group Code
         - Group Name
         - Category name
         - Output channels (linking them)
         - Output role ping
         - Alert times
         - Image link (if given else none)

        e.g: addgroup bcot Basingstone.College.Of.Technology www.google.com FFFFFF
        """
        error_msg = []
        group_code_length_max = 25
        default_alert_times = " ".join(["20","10","0"])

        # Validation of args
        if len(group_code) >= group_code_length_max:
            error_msg.append(f"Your group code is too long! (limit {group_code_length_max} chars)")
        if group_code.isdecimal():
            error_msg.append(f"Your group code cannot be entirely numbers, it needs at least one letter.")
        guild_roles = ([guild.name for guild in ctx.guild.roles])
        if group_code in guild_roles:
            error_msg.append(f"Group code already exists in the server, try another.")
        
        group_name_list = group_name.split(".")
        group_name = " ".join(group_name_list)
        if len(group_name) > 100: # Discord category length limit
            error_msg.append("Your group name is too long (limit 100 chars)")
            
        if not self.is_image_link_valid(group_image_link) and group_image_link is not None:
            error_msg.append(f"Your image link is invalid, please make sure it is a proper url")
        if group_image_link is None:
            group_image_link = "https://cdn.discordapp.com/avatars/834054201784008755/58b04fc4a00cdd6da40d0072c9d349f6.webp?size=1024"

        if not self.validate_hex_code(group_hex_colour) and group_hex_colour is not None:
            error_msg.append(f"Your hex code is invalid, please make sure it is a valid hex code")
        # Creates a random colour if arg is None
        if group_hex_colour is None:
            group_hex_colour = self.random_hex_colour()
        # Presence check in database

        groups_count = db.record("SELECT COUNT(GroupOwnerID) FROM Groups WHERE GroupOwnerID = ?", ctx.author.id)[0]
        if groups_count > 25:
            error_msg.append("You cannot create more than 25 groups")
        group_code_count = db.record("SELECT COUNT(GroupCode) FROM Groups WHERE GroupCode = ? OR GroupName = ?", group_code,group_code)[0]
        if group_code_count > 0:
            error_msg.append("Group code already exists in the database, try another.")
        group_name_count = db.record("SELECT COUNT(GroupName) FROM Groups WHERE GroupName = ? OR GroupCode = ?", group_name, group_name)[0]
        if group_name_count > 0:
            error_msg.append("Group name already exists in the database, try another.")

        if error_msg != []:
            error_embed = self.bot.auto_embed(
                type="error",
                title="You have entered one or more arguments wrong",
                description= "\n".join(error_msg)+f"\n\nUse `{get_prefix_value(ctx)}help addgroup` to learn more",
                ctx=ctx
            )
            return await ctx.send(embed=error_embed)
        
        # Creates role for group        
        role = await ctx.guild.create_role(name=group_code)
        role_id = role.id
        group_hex_colour = group_hex_colour.replace("#","") # discord.Colour doesn't take #. I'm too tired for this smh
        await role.edit(colour = discord.Colour(int(f"0x{group_hex_colour}", 16)))
        await ctx.message.author.add_roles(role)
        
        # Creates category for group
        category = await ctx.guild.create_category(name=group_name,position=0)
        category_id = category.id
        await category.set_permissions(ctx.guild.default_role, read_messages=False, connect=False)
        await category.set_permissions(role, read_messages=True, send_messages=False)
        # Creates channels in category
        announcement_channel = await ctx.guild.create_text_channel(
            "Lesson-announcements",
            category=category,
            sync_premissions=True,
            )
        nl_day_channel = await ctx.guild.create_voice_channel(
            "Next Lesson:",
            category=category,
            sync_premissions=True
            )
        nl_time_channel = await ctx.guild.create_voice_channel(
            "Next Lesson time:",
            category=category,
            sync_premissions=True
            )
        
        lesson_announcement_id = announcement_channel.id
        NLDayID = nl_day_channel.id
        NLTimeID = nl_time_channel.id
        # Adds information to database
        
        db.execute(
            "INSERT INTO Groups(GroupOwnerID,GuildID,GroupCode,GroupName,RoleID,Colour,CategoryID,LessonAnnouncementID,NLDayID,NLTimeID,ImageLink,AlertTimes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ctx.author.id,
            ctx.guild.id,
            group_code,
            group_name,
            role_id,
            group_hex_colour,
            category_id,
            lesson_announcement_id,
            NLDayID,
            NLTimeID,
            group_image_link,
            default_alert_times
        )
        db.commit()
        id = (db.lastrowid())
        db.execute(
            "INSERT INTO Students(GroupID,UserID,FullName) VALUES (?,?,?)",
            id,
            ctx.author.id,
            "Owner"
        )
        db.commit()
        title = "**Group successfully created**"
        description = f"ID: `{id}`\nGroup code: `{group_code}`\nGroup Name: `{group_name}`\nRole: <@&{role_id}>\nLesson announcements: <#{lesson_announcement_id}>\nNext lesson info: <#{NLDayID}> <#{NLTimeID}>\nAlert times: `{default_alert_times}`"
        embed = self.bot.auto_embed(
            type="info",
            title=title,
            description=description,
            ctx=ctx,
            colour=discord.Colour(int(f"0x{group_hex_colour}", 16))
        )
        await ctx.send(embed=embed)
        self.bot.log_command(ctx,"addgroup",group_code, group_name, group_image_link, group_hex_colour)
    @command(name="Add Teacher",brief="Adds a teacher to the lesson database. NOTE: Use a period (.) for a seperator for multi word names. e.g: A.Multi.Word.Teacher",aliases=["addteacher"])
    async def addteacher(self,ctx, groupID, teacher_name, teacher_subject, teacher_colour = None, teacher_link = None):
        """
        Adds teacher to group
        Takes groupID or name
        Takes a lesson teacher
        Takes a lesson subject
        Takes a lesson colour
        Takes a lesson link
        Takes a bool (online / offline)

        Outputs confirmation of creation showing:
         - Group ID
         - Group Name
         - Teacher ID
         - Teacher Name
         - Teacher subject
         - Teacher Colour
         - Teacher link
         - Teacher online bool

        e.g: addteacher Vitaly.Petrov Hacking FFFFFF www.google.com online

        Assumes lesson is offline if link not present
        Randomly generates colour if not present
        """
        error_msg = []
        #Validation
        group_info = db.record("SELECT * FROM Groups WHERE GroupID = ?",groupID)
        if group_info is None:
            error_msg.append(f"Group ID not found, use {get_prefix_value(ctx)}showgroups to view groups.")
        try:
            group_owner_ID = group_info[1]
            group_name = group_info[4]
            if ctx.author.id != group_owner_ID and ctx.author.id not in OWNER_IDS:
                raise CheckFailure
        except:
            pass

        if not self.is_image_link_valid(teacher_link) and teacher_link is not None:
            error_msg.append(f"Your image link is invalid, please make sure it is a proper url")

        if not self.validate_hex_code(teacher_colour) and teacher_colour is not None:
            error_msg.append(f"Your hex code is invalid, please make sure it is a valid hex code")
        if teacher_colour is None:
            teacher_colour = self.random_hex_colour()
        # Presence check in database
        teachers_count = db.record("SELECT COUNT(GroupID) FROM Teachers WHERE GroupID = ?", groupID)[0]
        if teachers_count > 25:
            error_msg.append("You cannot create more than 25 teachers in your group")
        teacher_name_list = teacher_name.split(".")
        teacher_name = " ".join(teacher_name_list)
        teacher_subject_list = teacher_subject.split(".")
        teacher_subject = " ".join(teacher_subject_list)
        teacher_info = db.records("SELECT * FROM Teachers WHERE TeacherName = ? and TeacherSubject = ?",teacher_name,teacher_subject)
        if teacher_info != []:
            error_msg.append("There is already a teacher and a subject with the same name in the database.")
        if error_msg != []:
            error_embed = self.bot.auto_embed(
                type="error",
                title="You have entered one or more arguments wrong",
                description= "\n".join(error_msg)+f"\n\nUse `{get_prefix_value(ctx)}help addteacher` to learn more",
                ctx=ctx
            )
            return await ctx.send(embed=error_embed)
        
        
        db.execute(
            "INSERT INTO Teachers(GroupID,TeacherName,TeacherSubject,TeacherColour,TeacherLink) VALUES (?,?,?,?,?)",
            groupID,
            teacher_name,
            teacher_subject,
            teacher_colour,
            teacher_link
        )
        db.commit()
        id = (db.lastrowid())
        title = "**Teacher successfully added**"
        description = f"ID: `{id}`\nGroup: `{group_name}`\nName: `{teacher_name}`\nSubject: `{teacher_subject}`"
        if teacher_link is not None:
            description += f"\nLink: [Click here]({teacher_link})"
        embed = self.bot.auto_embed(
            type="info",
            title=title,
            description=description,
            ctx=ctx,
            colour=discord.Colour(int(f"0x{teacher_colour}", 16))
        )
        await ctx.send(embed=embed)
        self.bot.log_command(ctx,"addteacher", groupID, teacher_name, teacher_subject, teacher_colour, teacher_link)
    @command(name="Add lesson",brief="Adds a lesson to the lesson database",aliases=["addlesson"])
    async def addlesson(self, ctx, groupID, teacher_ID, day_of_week, start_time, end_time, *, room):
        """
        Adds lesson to group timetable
        Takes groupID or name
        Takes teacher ID or name
        Takes day of week
        Takes start time
        Takes end time
        Takes room

        Outputs confirmation of creation showing:
         - Group ID
         - Group Name
         - Lesson ID
         - Teacher ID
         - Teacher Name
         - Start time
         - End time
         - Room
        """
        error_msg = []
        # Validation
        group_info = db.record("SELECT * FROM Groups WHERE GroupID = ? ",groupID)
        teacher_info = db.record("SELECT * FROM Teachers WHERE TeacherID = ?",teacher_ID)
        if group_info is None:
            error_msg.append(f"Group ID not found, use {get_prefix_value(ctx)}showgroups to view groups.")
        if teacher_info is None:
            error_msg.append(f"Teacher ID not found, use {get_prefix_value(ctx)}showteachers to view teachers.")
        try:
            group_owner_ID = group_info[1]
            group_name = group_info[4]
            if ctx.author.id != group_owner_ID and ctx.author.id not in OWNER_IDS:
                raise CheckFailure
        except:
            pass
        day_of_week = day_of_week.lower()
        if day_of_week in self.LONG_DAYS_OF_WEEK:
            day_of_week = self.LONG_DAYS_OF_WEEK.index(day_of_week)
        elif day_of_week in self.SHORT_DAYS_OF_WEEK:
            day_of_week = self.SHORT_DAYS_OF_WEEK.index(day_of_week)
        elif len(day_of_week) == 1 and int(day_of_week) in [x for x in range(6)]:
            day_of_week = int(day_of_week)
        else:
            error_msg.append("Invalid day of week.")

        try:
            start_time_formatted = start_time.replace(":","")
            datetime.datetime.strptime(start_time_formatted,"%H%M")
            start_time = start_time_formatted
        except:
            error_msg.append(f"Please enter the start time correctly, you entered `{start_time}`")
        try:
            end_time_formatted = end_time.replace(":","")
            datetime.datetime.strptime(end_time_formatted,"%H%M")
            end_time = end_time_formatted
        except:
            error_msg.append(f"Please enter the start time correctly, you entered `{start_time}`")
        if start_time > end_time:
            error_msg.append("Please ensure the lesson start time is before the lesson end time.")
        # Checks for repeats in database
        lesson_info = db.records(
            "SELECT * FROM Lessons WHERE TeacherID = ? AND DayOfWeek = ? AND StartHour = ? AND StartMin = ? AND EndHour = ? AND EndMin = ?",
            teacher_ID,
            day_of_week,
            start_time[:2],
            start_time[2:],
            end_time[:2],
            end_time[2:],
        )
        if lesson_info != []:
            error_msg.append("That lesson already exists in the database")
        
        if error_msg != []:
            error_embed = self.bot.auto_embed(
                type="error",
                title="You have entered one or more arguments wrong",
                description= "\n".join(error_msg)+f"\n\nUse `{get_prefix_value(ctx)}help addteacher` to learn more",
                ctx=ctx
            )
            return await ctx.send(embed=error_embed)
        db.execute(
            "INSERT INTO Lessons(GroupID,TeacherID,DayOfWeek,StartHour,StartMin,EndHour,EndMin,Room) VALUES (?,?,?,?,?,?,?,?)",
            groupID,
            teacher_ID,
            day_of_week,
            start_time[:2],
            start_time[2:],
            end_time[:2],
            end_time[2:],
            room
        )
        db.commit()
        id = (db.lastrowid())
        teacher_info = db.record("SELECT * FROM Teachers WHERE TeacherID = ?", teacher_ID)

        title = "**Lesson successfully added**"
        description = f"ID: `{id}`\nGroup: `{group_name}`\nTeacher: `{teacher_info[2]}`\nSubject: `{teacher_info[3]}`"\
            f"\nDay: `{(self.LONG_DAYS_OF_WEEK[day_of_week]).capitalize()}`\nStart time: `{start_time[:2]}:{start_time[2:]}`"\
            f"\nEnd time: `{end_time[:2]}:{end_time[2:]}`\nRoom: `{room}`"
        embed = self.bot.auto_embed(
            type="info",
            title=title,
            description=description,
            ctx=ctx,
        )
        await ctx.send(embed=embed)
        self.load_timetable()
        self.bot.log_command(ctx,"addlesson",groupID, teacher_ID, day_of_week, start_time, end_time, room)
    @command(name="Add student",brief="Adds student to lesson database",aliases=["addstudent"])
    async def addstudent(self, ctx, groupID, student: discord.Member,*, name = None):
        """
        Adds student to group
        Takes Group ID or name
        Takes Student name

        Adds role to useriD and adds to database
        
        Outputs confirmation of creation showing:
         - Group ID
         - Group Name
         - Student Name
        """
        error_msg = []
        #Validation
        group_info = db.record("SELECT * FROM Groups WHERE GroupID = ?",groupID)
        if group_info is None:
            error_msg.append(f"Group ID not found, use {get_prefix_value(ctx)}showgroups to view groups.")
        try:
            group_owner_ID = group_info[1]
            group_name = group_info[4]
            if ctx.author.id != group_owner_ID and ctx.author.id not in OWNER_IDS:
                raise CheckFailure
        except:
            pass
        student = student or None
        if student is None:
            error_msg.append("Please select a valid user")
        try:
            
            role = ctx.guild.get_role(group_info[5])
            await student.add_roles(role)

        except:
            error_msg.append("You are in the wrong server, go to the server with the lessons to add a user.")
        
        student_info = db.records(
            "SELECT * FROM Students WHERE GroupID = ? AND UserID = ?",
            groupID,
            student.id
        )
        if student_info != []:
            error_msg.append("Student is already in the database.")

        if error_msg != []:
            error_embed = self.bot.auto_embed(
                type="error",
                title="You have entered one or more arguments wrong",
                description= "\n".join(error_msg)+f"\n\nUse `{get_prefix_value(ctx)}help addstudent` to learn more",
                ctx=ctx
            )
            return await ctx.send(embed=error_embed)

        db.execute(
            "INSERT INTO Students(GroupID,UserID,FullName) VALUES (?,?,?)",
            groupID,
            student.id,
            name
        )
        db.commit()
        id = (db.lastrowid())
        title = "**Student successfully added**"
        description = f"ID: `{id}`\nGroup: `{group_name}`\nStudent: <@{student.id}>"
        if name is not None:
            description += f"\nName: `{name}`"
        embed = self.bot.auto_embed(
            type="info",
            title=title,
            description=description,
            ctx=ctx,
        )
        await ctx.send(embed=embed)
        self.bot.log_command(ctx,groupID, student, name)

    @command(name="Remove Group",brief="Removes group from the lesson database",aliases=["removegroup"])
    async def removegroup(self, ctx, groupID):
        """
        Takes GroupID or GroupCode

        Removes a group from database
        Only owner may remove the group

        Ensures to delete everything in groups, timetable and teachers
        that contain GroupID

        Deletes role, turns category hidden
        """
        error_msg = []
        #Validation
        group_info = db.record("SELECT * FROM Groups WHERE GroupID = ?",groupID)
        if group_info is None:
            error_msg.append(f"Group ID not found, use {get_prefix_value(ctx)}showgroups to view groups.")
        try:
            group_owner_ID = group_info[1]
            group_guild_id = group_info[2]
            if ctx.guild.id != group_guild_id:
                error_msg.append("You are in the wrong guild, please use this command in the guild containing the lesson info")
            if ctx.author.id != group_owner_ID and ctx.author.id not in OWNER_IDS:
                raise CheckFailure
        except:
            pass

        if error_msg != []:
            error_embed = self.bot.auto_embed(
                type="error",
                title="You have entered one or more arguments wrong",
                description= "\n".join(error_msg)+f"\n\nUse `{get_prefix_value(ctx)}help removegroup` to learn more",
                ctx=ctx
            )
            return await ctx.send(embed=error_embed)

        teacher_info = db.records("SELECT * FROM Teachers WHERE GroupID = ?",groupID)
        lesson_info = db.records("SELECT * FROM Lessons WHERE GroupID = ?",groupID)
        student_info = db.records("SELECT * FROM Students WHERE GroupID = ?",groupID)


        # Deletes all database records
        db.execute("DELETE FROM Groups WHERE GroupID = ?",groupID)
        db.execute("DELETE FROM Teachers WHERE GroupID = ?",groupID)
        db.execute("DELETE FROM Lessons WHERE GroupID = ?",groupID)
        db.execute("DELETE FROM Students WHERE GroupID = ?",groupID)
        db.commit()

        role = discord.utils.get(ctx.guild.roles, id=group_info[5])
        category = discord.utils.get(ctx.guild.categories, id= group_info[7])
        announcement_channel = discord.utils.get(ctx.guild.channels, id=group_info[8])
        NLDayChannel = discord.utils.get(ctx.guild.channels, id=group_info[9])
        NLTimeChannel = discord.utils.get(ctx.guild.channels, id=group_info[10])
        
        await role.delete()
        await announcement_channel.delete()
        await NLDayChannel.delete()
        await NLTimeChannel.delete()
        await category.delete()

        title = "**Group successfully removed**"
        description = f"Deleted info has been messaged to you."
        embed = self.bot.auto_embed(
            type="info",
            title=title,
            description=description,
            ctx=ctx,
        )
        await ctx.send(embed=embed)

        title = "**Deleted group information**"
        fields = [
            ("Group",group_info,False),
            ("Teachers",teacher_info,False),
            ("Lessons",lesson_info,False),
            ("Students",student_info,False),
        ]
        embed = self.bot.auto_embed(
            type="info",
            title=title,
            fields=fields,
            ctx=ctx
        )
        await ctx.author.send(embed=embed)
        self.load_timetable() # Reloads timetable since lessons may have been removed
        self.bot.log_command(ctx,"removegroup",group_info,teacher_info,lesson_info,student_info)
    @command(name="Remove Teacher",brief="Removes a teacher from the lesson database",aliases=["removeteacher"])
    async def removeteacher(self,ctx,teacherID):
        """
        Takes TeacherID or Teacher Name

        Removes a teacher from database
        Only group owner may remove a teacher

        Ensures to delete everything in timetable and teachers that
        contain TeacherID
        """
        error_msg = []
        #Validation
        teacher_info = db.record("SELECT * FROM Teachers WHERE TeacherID = ?",teacherID)
        if teacher_info is None:
            error_msg.append(f"Group ID not found, use {get_prefix_value(ctx)}showteachers to view groups.")
        
        
        try:
            groupID = teacher_info[1]
            group_info = db.record("SELECT * FROM Groups WHERE GroupID = ?",groupID)
            group_owner_ID = group_info[1]
            group_guild_id = group_info[2]
            if ctx.guild.id != group_guild_id:
                error_msg.append("You are in the wrong guild, please use this command in the guild containing the lesson info")
            if ctx.author.id != group_owner_ID and ctx.author.id not in OWNER_IDS:
                raise CheckFailure
        except:
            pass

        if error_msg != []:
            error_embed = self.bot.auto_embed(
                type="error",
                title="You have entered one or more arguments wrong",
                description= "\n".join(error_msg)+f"\n\nUse `{get_prefix_value(ctx)}help removelesson` to learn more",
                ctx=ctx
            )
            return await ctx.send(embed=error_embed)


        lesson_info = db.records("SELECT * FROM Lessons WHERE TeacherID = ?",teacherID)
        # Deletes all database records
        db.execute("DELETE FROM Teachers WHERE TeacherID = ?",teacherID)
        db.execute("DELETE FROM Lessons WHERE TeacherID = ?",teacherID)
        db.commit()

        title = "**Teacher successfully removed**"
        description = f"Deleted info has been messaged to you."
        embed = self.bot.auto_embed(
            type="info",
            title=title,
            description=description,
            ctx=ctx,
        )
        await ctx.send(embed=embed)

        title = "**Deleted group information**"
        fields = [
            ("Teachers",teacher_info,False),
            ("Lessons",lesson_info,False),
        ]
        embed = self.bot.auto_embed(
            type="info",
            title=title,
            fields=fields,
            ctx=ctx
        )
        await ctx.author.send(embed=embed)
        self.load_timetable() # Reloads timetable since lessons may have been removed    
        self.bot.log_command(ctx,"removeteacher",teacher_info,lesson_info)    
    @command(name="Remove Lesson",brief="Removes a lesson from the lesson database",aliases=["removelesson"])
    async def removelesson(self,ctx,lessonID):
        """
        Takes lessonID 
        
        Removes lesson from database
        Only group owner may remove a lesson

        Ensures to delete everything in timetable that contains lessonID
        """
        error_msg = []
        #Validation
        lesson_info = db.record("SELECT * FROM Lessons WHERE LessonID = ?",lessonID)
        if lesson_info is None:
            error_msg.append(f"Group ID not found, use {get_prefix_value(ctx)}showteachers to view groups.")

        try:
            groupID = lesson_info[1]
            group_info = db.record("SELECT * FROM Groups WHERE GroupID = ?",groupID)

            group_owner_ID = group_info[1]
            group_guild_id = group_info[2]
            if ctx.guild.id != group_guild_id:
                error_msg.append("You are in the wrong guild, please use this command in the guild containing the lesson info")
            if ctx.author.id != group_owner_ID and ctx.author.id not in OWNER_IDS:
                raise CheckFailure
        except:
            pass

        if error_msg != []:
            error_embed = self.bot.auto_embed(
                type="error",
                title="You have entered one or more arguments wrong",
                description= "\n".join(error_msg)+f"\n\nUse `{get_prefix_value(ctx)}help removelesson` to learn more",
                ctx=ctx
            )
            return await ctx.send(embed=error_embed)

        # Deletes all database records
        db.execute("DELETE FROM Lessons WHERE LessonID = ?",lessonID)
        db.commit()

        title = "**Lesson successfully removed**"
        description = f"Deleted info has been messaged to you."
        embed = self.bot.auto_embed(
            type="info",
            title=title,
            description=description,
            ctx=ctx,
        )
        await ctx.send(embed=embed)

        title = "**Deleted group information**"
        fields = [
            ("Lessons",lesson_info,False)
        ]
        embed = self.bot.auto_embed(
            type="info",
            title=title,
            fields=fields,
            ctx=ctx
        )
        await ctx.author.send(embed=embed)
        self.load_timetable() # Reloads timetable since lessons may have been removed
        self.bot.log_command(ctx,"removelesson",lesson_info)    

    @command(name="Remove Student",brief="Removes a student from the lesson database",aliases=["removestudent"])
    async def removestudent(self,ctx,studentID):
        """
        Takes StudentID or userID or Name

        Removes a student from the databsae
        Only group owner may remove a student

        Ensures to delete student from database, as well as removing role
        """
        error_msg = []
        #Validation
        student_info = db.record("SELECT * FROM Students WHERE StudentID = ?",studentID)
        if student_info is None:
            error_msg.append(f"Student ID not found, use {get_prefix_value(ctx)}showstudents to view students.")

        try:
            groupID = student_info[1]
            group_info = db.record("SELECT * FROM Groups WHERE GroupID = ?",groupID)

            group_owner_ID = group_info[1]
            group_guild_id = group_info[2]
            if ctx.guild.id != group_guild_id:
                error_msg.append("You are in the wrong guild, please use this command in the guild containing the lesson announcements")
            if ctx.author.id != group_owner_ID and ctx.author.id not in OWNER_IDS:
                raise CheckFailure
        except:
            pass

        if error_msg != []:
            error_embed = self.bot.auto_embed(
                type="error",
                title="You have entered one or more arguments wrong",
                description= "\n".join(error_msg)+f"\n\nUse `{get_prefix_value(ctx)}help removelesson` to learn more",
                ctx=ctx
            )
            return await ctx.send(embed=error_embed)

        # Deletes all database records
        db.execute("DELETE FROM Students WHERE StudentID = ?",studentID)
        db.commit()
        role_id = group_info[5]
        role = discord.utils.get(ctx.guild.roles, id=role_id)
        user_id = student_info[2]
        user = discord.utils.get(ctx.guild.members, id=user_id)
        try: # Errors if user is no longer in guild
            await user.remove_roles(role)
        except:
            pass
        title = "**Student successfully removed**"
        description = f"Deleted info has been messaged to you."
        embed = self.bot.auto_embed(
            type="info",
            title=title,
            description=description,
            ctx=ctx,
        )
        await ctx.send(embed=embed)

        title = "**Deleted group information**"
        fields = [
            ("Student",student_info,False)
        ]
        embed = self.bot.auto_embed(
            type="info",
            title=title,
            fields=fields,
            ctx=ctx
        )
        await ctx.author.send(embed=embed)
        self.load_timetable() # Reloads timetable since lessons may have been removed
        self.bot.log_command(ctx,"removestudent",student_info)    


    @command(name="Show Groups",brief="Shows all groups that you own",aliases=["showgroups"])
    async def showgroups(self, ctx):
        """
        Outputs an Embed showing all groups from user
        """
        
        groups_info = db.records("SELECT * FROM Groups WHERE GroupOwnerID = ?", ctx.author.id)
        if groups_info == []:
            title = "**No groups found**"
            description = f"Use {get_prefix_value(ctx)}addgroup to create a group."
            embed = self.bot.auto_embed(
                type="error",
                title=title,
                description=description,
                ctx=ctx,
            )
            await ctx.send(embed=embed)
        else:
            fields = []
            for group in groups_info:
                id = group[0]
                owner_id = group[1]
                guild = group[2]
                group_code = group[3]
                group_name = group[4]
                role_id = group[5]
                colour = group[6]
                category_id = group[7]
                announcement_id = group[8]
                NLDayID = group[9]
                NLTimeID = group[10]
                image_link = group[11]
                AlertTimes = group[12]
                
                name = f"**{group_name}**"
                value = f"ID: `{id}`\nGroup code: `{group_code}`\nOwner: <@{owner_id}>\nRole: <@&{role_id}>\nLesson announcements: <#{announcement_id}>\nNext lesson info: <#{NLDayID}> <#{NLTimeID}>\nAlert times: `{AlertTimes}`\nImage: [Click here]({image_link})"
                inline = False
                fields.append((name,value,inline))
            title = "**Showing your groups**"
            embed = self.bot.auto_embed(
                type="info",
                title=title,
                fields=fields,
                ctx=ctx
            )
            await ctx.send(embed=embed)
        self.bot.log_command(ctx,"showgroups")    

    @command(name="Show Teachers",brief="Shows all teachers for a given group",aliases=["showteachers"])
    async def showteachers(self, ctx, groupID):
        """
        Takes GroupID or code or name
        Shows all teachers in embed form
        """
        error_msg = []
        #Validation
        group_info = db.record("SELECT * FROM Groups WHERE GroupID = ?",groupID)
        if group_info is None:
            error_msg.append(f"Group ID not found, use {get_prefix_value(ctx)}showgroups to view groups.")
        try:
            group_owner_ID = group_info[1]
            group_name = group_info[4]
            if ctx.author.id != group_owner_ID and ctx.author.id not in OWNER_IDS:
                raise CheckFailure
        except:
            pass
        if error_msg != []:
            error_embed = self.bot.auto_embed(
                type="error",
                title="You have entered one or more arguments wrong",
                description= "\n".join(error_msg)+f"\n\nUse `{get_prefix_value(ctx)}help removegroup` to learn more",
                ctx=ctx
            )
            return await ctx.send(embed=error_embed)

        teacher_info = db.records("SELECT * FROM Teachers WHERE GroupID = ?",groupID)#
        if teacher_info == []:
            title = "**No teachers found**"
            description = f"Use {get_prefix_value(ctx)}addteacher to create a group."
            embed = self.bot.auto_embed(
                type="error",
                title=title,
                description=description,
                ctx=ctx,
            )
            await ctx.send(embed=embed)
        else:
            fields = []
            for teacher in teacher_info:
                id = teacher[0]
                group_ID = teacher[1]
                teacher_name = teacher[2]
                teacher_subject = teacher[3]
                teacher_link = teacher[5]

                name = f"**{teacher_name}**"
                value = f"ID: `{id}`\nGroup: `{group_name}`\nSubject: `{teacher_subject}`"
                if teacher_link is not None:
                    value += f"\nLink: `{teacher_link}`"
                inline = False
                fields.append((name,value,inline))
            title = "**Showing your teachers**"
            embed = self.bot.auto_embed(
                type="info",
                title=title,
                fields=fields,
                ctx=ctx
            )
            await ctx.send(embed=embed)
        self.bot.log_command(ctx,"showteachers",group_ID)    

    @command(name="Show Lessons",brief="Shows all lessons for a given group",aliases=["showlessons"])
    async def showlessons(self,ctx,groupID):
        """
        Takes GroupID or code or name
        Shows all lessons in embed form
        """
        error_msg = []
        #Validation
        group_info = db.record("SELECT * FROM Groups WHERE GroupID = ?",groupID)
        if group_info is None:
            error_msg.append(f"Group ID not found, use {get_prefix_value(ctx)}showgroups to view groups.")
        try:
            group_owner_ID = group_info[1]
            group_name = group_info[4]
            if ctx.author.id != group_owner_ID and ctx.author.id not in OWNER_IDS:
                raise CheckFailure
        except:
            pass
        if error_msg != []:
            error_embed = self.bot.auto_embed(
                type="error",
                title="You have entered one or more arguments wrong",
                description= "\n".join(error_msg)+f"\n\nUse `{get_prefix_value(ctx)}help removegroup` to learn more",
                ctx=ctx
            )
            return await ctx.send(embed=error_embed)
        lesson_info = db.records("SELECT * FROM Lessons WHERE GroupID = ?",groupID)
        if lesson_info == []:
            title = "**No lessons found**"
            description = f"Use {get_prefix_value(ctx)}addlesson to create a group."
            embed = self.bot.auto_embed(
                type="error",
                title=title,
                description=description,
                ctx=ctx,
            )
            await ctx.send(embed=embed)
        else:
            fields = []
            for i, lesson in enumerate(lesson_info):
                id = lesson[0]
                group_ID = lesson[1]
                teacher_ID = lesson[2]
                teacher_info = db.record("SELECT * FROM Teachers WHERE TeacherID = ?",teacher_ID)
                teacher_name = teacher_info[2]
                teacher_subject = teacher_info[3]
                day_of_week = (self.LONG_DAYS_OF_WEEK[lesson[3]]).capitalize()
                start_time = f"{lesson[4]}:{lesson[5]}"
                end_time = f"{lesson[6]}:{lesson[7]}"
                room = lesson[8]


                name = f"**Lesson {i+1}**"
                value = f"ID: `{id}`\nGroup: `{group_name}`\nTeacher: `{teacher_name}`\nSubject: `{teacher_subject}`\nDay: `{day_of_week}`\nStart time: `{start_time}`\nEnd time: `{end_time}`\nRoom: `{room}`"
                inline = True
                fields.append((name,value,inline))
            title = "**Showing your lessons**"
            embed = self.bot.auto_embed(
                type="info",
                title=title,
                fields=fields,
                ctx=ctx
            )
            await ctx.send(embed=embed)   
            self.bot.log_command(ctx,"showlessons",group_ID)    
            
    @command(name="Show Students",brief="Shows all students for a given group",aliases=["showstudents"])
    async def showstudents(self,ctx,groupID):
        """
        Takes GroupID or code or name
        Shows all students in embed form
        """
        error_msg = []
        #Validation
        group_info = db.record("SELECT * FROM Groups WHERE GroupID = ?",groupID)
        if group_info is None:
            error_msg.append(f"Group ID not found, use {get_prefix_value(ctx)}showgroups to view groups.")
        try:
            group_owner_ID = group_info[1]
            group_name = group_info[4]
            if ctx.author.id != group_owner_ID and ctx.author.id not in OWNER_IDS:
                raise CheckFailure
        except:
            pass
        if error_msg != []:
            error_embed = self.bot.auto_embed(
                type="error",
                title="You have entered one or more arguments wrong",
                description= "\n".join(error_msg)+f"\n\nUse `{get_prefix_value(ctx)}help removegroup` to learn more",
                ctx=ctx
            )
            return await ctx.send(embed=error_embed)
        student_info = db.records("SELECT * FROM Students WHERE GroupID = ?",groupID)
        if student_info == []:
            title = "**No students found**"
            description = f"Use {get_prefix_value(ctx)}addstudent to create a group."
            embed = self.bot.auto_embed(
                type="error",
                title=title,
                description=description,
                ctx=ctx,
            )
            await ctx.send(embed=embed)
        else:
            title = "**Showing all students**"
            description = f"**{group_name}: `{len(student_info):,}` students**"
            for student in student_info:
                id = student[0]
                group_id = student[1]
                user_id = student[2]
                name = student[3]
                description += f"\n> ID: `{id}`\t     User: <@{user_id}>"
                if name is not None:
                    description += f"\tName: `{name}`"
            embed = self.bot.auto_embed(
                type="info",
                title=title,
                description=description,
                ctx=ctx
            )
            await ctx.send(embed=embed)
            self.bot.log_command(ctx,"showstudents",groupID)    

    @command()
    async def editgroup():
        pass
    @command()
    async def editteacher():
        pass
    @command()
    async def editlesson():
        pass
    @command()
    async def editstudent():
        pass

    @command(name="Add assignment",brief="Adds an assignment to the database.",aliases=["addassignment"])
    async def addassignment(self,ctx,group,teacher: str,date: str,time: str,*,todo):
        """
        Adds an assignment to a group
        Similar to Remind
        Takes groupID or code or Name
        Takes TeacherID or Name
        Takes Date
        Takes time
        Takes assignment todo

        e,g: addassignment bcot Jo.Slater 2021-12-10 10:00 Assignment 4

        Adds to assignment database
        Adds to assignment scheduler

        """
        error_msg = []
        teacher = teacher.replace("."," ")
        date_formatted = date.replace("-","")
        time_formatted = time.replace(":","")
        # Handling group input
        Group_Info = self.get_group_info_from_input(group)
        if teacher.lower() != "none":
            Teacher_Info = self.get_teacher_info_from_input(teacher)
            if Group_Info is None:
                error_msg.append("Group could not be found")
            # Handling teacher input
            if Teacher_Info is None:
                error_msg.append("Teacher could not be found")
            else:
                TeacherID = Teacher_Info[0]
        else:
            TeacherID = "none"
        # Handling date input
        if len(date_formatted) == 8 and date_formatted.isdecimal(): # If it is a date (YYYYMMDD) and contains only numbers. This prevents "saturday" and "tomorrow" being acceptable dates
            try: # Validates to be in proper format
                datetime_object = datetime.datetime.strptime(date_formatted+time_formatted,"%Y%m%d%H%M")
                if int(date_formatted[0:4]) > 3000:
                    error_msg.append("You cannot enter a year above 3000.")
                if datetime.datetime.today() > datetime_object:
                    error_msg.append("You cannot have an assignment set in the past.")
            except:
                error_msg.append(f"Please make sure your date is in `YYYY-MM-DD` format, you entered `{date}`")
        else:
            error_msg.append("You have entered an invalid date. Please make sure it is in the format `YYYY-MM-DD`")
        # Handling time input
        try:
            datetime.datetime.strptime(time_formatted,"%H%M")
            time = time_formatted
        except:
            error_msg.append(f"Please enter the time correctly, you entered `{time}`")

        creator_id = ctx.author.id
        if error_msg == []:
            db.execute(
                "INSERT INTO Assignments(CreatorUserID,GroupID,TeacherID,DueDate,DueTime,AssignmentContent) VALUES (?,?,?,?,?,?)",
                creator_id,
                Group_Info[0],
                TeacherID,
                date_formatted,
                time_formatted,
                todo
            )
            db.commit()
            self.load_assignments()
            id = (db.lastrowid())

            if TeacherID != "none":
                description = f"ID: `{id}`\nGroup: `{Group_Info[4]}`\nTeacher: `{Teacher_Info[2]}`\nDate: `{date}`\nTime: `{time[0:2]}:{time[2:]}`\nDetails: `{todo}`"
            else:
                description = f"ID: `{id}`\nGroup: `{Group_Info[4]}`\nDate: `{date}`\nTime: `{time[0:2]}:{time[2:]}`\nDetails: `{todo}`"

            embed = self.bot.auto_embed(
                type="info",
                title=f"**Assignment successfully added**",
                description=description,
                thumbnail=ctx.author.avatar_url,
                ctx=ctx
            )
            await ctx.send(embed=embed)
            self.bot.log_command(ctx,"addassignment",group,teacher,date,time,todo)
        
        else:
            embed = self.bot.auto_embed(
                type="error",
                title="You have entered one or more arguments wrong",
                description= "\n".join(error_msg)+f"\n\nUse {get_prefix_value(ctx)}help to learn more",
                ctx=ctx
            )
            await ctx.send(embed=embed)
    @command(name="Remove Assignment",brief="Removes an assignment given an ID",aliases=["removeassignment"])
    async def removeassignment(self,ctx,assignmentID):
        """
        Takes AssignmentID
        Removes assignment from database
        """
        error_msg = []
        #Validation
        assignment_info = db.record("SELECT * FROM Assignments WHERE AssignmentID = ?",assignmentID)
        if assignment_info is None:
            error_msg.append(f"Assignment ID not found, use {get_prefix_value(ctx)}showassignments to view assignments.")

        try:
            groupID = assignment_info[2]
            group_info = db.record("SELECT * FROM Groups WHERE GroupID = ?",groupID)

            group_owner_ID = group_info[1]
            group_guild_id = group_info[2]
            if ctx.author.id != group_owner_ID and ctx.author.id not in OWNER_IDS:
                raise CheckFailure
        except:
            pass

        if error_msg != []:
            error_embed = self.bot.auto_embed(
                type="error",
                title="You have entered one or more arguments wrong",
                description= "\n".join(error_msg)+f"\n\nUse `{get_prefix_value(ctx)}help removeassignment` to learn more",
                ctx=ctx
            )
            return await ctx.send(embed=error_embed)

        # Deletes all database records
        db.execute("DELETE FROM Assignments WHERE AssignmentID = ?",assignmentID)
        db.commit()

        title = "**Assignment successfully removed**"
        description = f"Deleted info has been messaged to you."
        embed = self.bot.auto_embed(
            type="info",
            title=title,
            description=description,
            ctx=ctx,
        )
        await ctx.send(embed=embed)

        title = "**Deleted assignment information**"
        fields = [
            ("Assignment",assignment_info,False)
        ]
        embed = self.bot.auto_embed(
            type="info",
            title=title,
            fields=fields,
            ctx=ctx
        )
        await ctx.author.send(embed=embed)
        self.load_assignments() # Reloads timetable since lessons may have been removed
        self.bot.log_command(ctx,"removeassignment",assignmentID)
    @command(name="Show Assignments",brief="Shows assignments for a user, groupID or group code.",aliases=["showassignments"])
    async def showassignments(self,ctx, user: Optional[discord.Member] = None, groupID: Optional[int] = None, groupCode: Optional[str] = None ):
        """
        Takes GroupID, Code or Name
        Shows all assignments in embed form
        """
        error_msg = []
        #Validation
        if all([x is None for x in [groupID,groupCode]]):
            lessons, GroupIDs = self.get_timetable(ctx.author.id if user is None else user.id)
            GroupID = GroupIDs
            assignments = db.records(f"SELECT * FROM Assignments WHERE GroupID IN ({','.join(GroupIDs)}) ORDER BY DueDate ASC, DueTime ASC")
        else:
            NewgroupID = self.get_groupID_from_command(ctx,groupID,groupCode)    
            if isinstance(NewgroupID, list):
                error_msg = NewgroupID
                error_embed = self.bot.auto_embed(
                    type="error",
                    title="You have entered one or more arguments wrong",
                    description= "\n".join(error_msg)+f"\n\nUse `{get_prefix_value(ctx)}help showassignments` to learn more",
                    ctx=ctx
                )
                return await ctx.send(embed=error_embed)
            else:
                assignments = db.records(f"SELECT * FROM Assignments WHERE GroupID = ?",NewgroupID)
        if assignments is None:
            error_msg.append(f"You do not have any assignments, use {get_prefix_value(ctx)}addassignment to add one!")
        if error_msg != []:
            error_embed = self.bot.auto_embed(
                type="error",
                title="You have entered one or more arguments wrong",
                description= "\n".join(error_msg)+f"\n\nUse `{get_prefix_value(ctx)}help removegroup` to learn more",
                ctx=ctx
            )
            return await ctx.send(embed=error_embed)
        if assignments == []:
            title = "**No assignments found**"
            description = f"Use {get_prefix_value(ctx)}addassignment to create an assignment."
            embed = self.bot.auto_embed(
                type="error",
                title=title,
                description=description,
                ctx=ctx,
            )
            await ctx.send(embed=embed)
        else:
            fields = []
            for assignment in assignments:
                id = assignment[0]
                group_info = self.get_group_info_from_ID(assignment[2])
                teacher_ID = assignment[3]
                todo = assignment[6]
                due_datetime = datetime.datetime.strptime(assignment[4]+assignment[5],"%Y%m%d%H%M")

                name=todo
                if teacher_ID != "none":
                    teacher_info = self.get_teacher_info_from_ID(teacher_ID)
                    value = f"> ID: `{id}`\n> Teacher: `{teacher_info[2]}`\n> Date: <t:{int(due_datetime.timestamp())}:F>\n> Due <t:{int(due_datetime.timestamp())}:R>\n> Details: `{todo}`"
                else:
                    value = f"> ID: `{id}`\n> Date: <t:{int(due_datetime.timestamp())}:F>\n> Due <t:{int(due_datetime.timestamp())}:R>\n> Details: `{todo}`"
                inline = False
                fields.append((name,value,inline))
            title = f"**Showing assignments for `{group_info[4]}`:**"
            embed = self.bot.auto_embed(
                type="info",
                title=title,
                fields=fields,
                ctx=ctx
            )
            await ctx.send(embed=embed)
            self.bot.log_command(ctx,"showassignments",group_info[4])
    
    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up("timetable")
        print("Timetable cog ready!")

def setup(bot):
    bot.add_cog(Timetable(bot))