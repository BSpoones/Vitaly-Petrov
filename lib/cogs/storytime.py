from discord.ext.commands import Cog, command
from discord.ext.commands.core import cooldown, has_permissions
from discord.ext.commands.errors import BadArgument
from random import choice
import json, random
class LoadData:
    def __init__(self):
        with open("data/data.json") as f:
            self.JSON_data = json.load(f)
    def name(self) -> str:
        gender_choice = choice(["boys","girls"])
        forenames = self.JSON_data[gender_choice]
        surnames = self.JSON_data["surnames"]
        name = f"{choice(forenames)} {choice(surnames)}"
        return name
    def colour(self) -> str:
        colours = self.JSON_data["colours"]
        return choice(colours)
    def town(self) -> str:
        towns = self.JSON_data["towns"]
        return choice(towns)
    def occupation(self) -> str:
        occupations = self.JSON_data["occupations"]
        return choice(occupations)
    def time_of_day(self) -> str:
        times = self.JSON_data["time_of_day"]
        return choice(times)
    def weather(self) -> str:
        weathers = self.JSON_data["weather"]
        return choice(weathers)
    def time_in_past(self) -> str:
        past_times = self.JSON_data["time_in_past"]
        return choice(past_times)
    def location(self) -> str:
        locations = self.JSON_data["locations"]
        return choice(locations)
    def saw_something(self) -> str:
        somethings = self.JSON_data["somethings"]
        return choice(somethings)
    def emotion(self) -> str:
        emotions = self.JSON_data["emotions"]
        return choice(emotions)
    def somethings_action(self) -> str:
        actions = self.JSON_data["something_did_something"]
        return choice(actions)
    def reaction_to_action(self) -> str:
        reactions = self.JSON_data["reaction"]
        return choice(reactions)

class Story:
    def __init__(self):
        self.story = self.load_stories()
    def load_stories(self) -> list:
        with open("data/stories.json") as f:
            JSON_data = json.load(f)
        # return(choice(stories).split("\n\n")) # Seperation for two paragraphs
        intros = JSON_data["introductions"]
        second_paragraphs = JSON_data["second paragraphs"]

        intro = choice(intros)
        second_paragraph = choice(second_paragraphs)
        return(intro,second_paragraph)
    def intro(self):
        load_data = LoadData()
        intro_paragraph = self.story[0]
        intro_paragraph = intro_paragraph.format(
            name = load_data.name(),
            age = random.randint(12,70),
            hair_colour = load_data.colour(),
            eye_colour = load_data.colour(),
            hometown = load_data.town(),
            occupation = load_data.occupation(),
            time_of_day = load_data.time_of_day(),
            weather = load_data.weather()
            )
        return intro_paragraph
    def second_paragraph(self):
        load_data = LoadData()

        second_paragraph = self.story[1]

        second_paragraph = second_paragraph.format(
            time_in_past = load_data.time_in_past(),
            location = load_data.location(),
            saw_something = load_data.saw_something(),
            emotion = load_data.emotion(),
            somethings_action = load_data.somethings_action(),
            reaction = load_data.reaction_to_action()
        )
        return second_paragraph





class StoryTimeCog(Cog):
    def __init__(self, bot):
        self.bot = bot
    @command(name="Story Time", brief="Displays an randomly generated story",aliases=["storytime"])
    async def storytime(self,ctx):
        story = Story()
        intro = story.intro()
        second = story.second_paragraph()

        embed = self.bot.auto_embed(
            type="info",
            title=f"**Showing a randomly generated story**",
            description = f"{intro}\n\n{second}",
            ctx=ctx
        )
        await ctx.send(embed=embed)
        self.bot.log_command(ctx,"storytime")

    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up("story time")
        print("story time cog ready!")

def setup(bot):
    bot.add_cog(StoryTimeCog(bot))