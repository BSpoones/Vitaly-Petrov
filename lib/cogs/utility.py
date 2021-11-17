from discord.ext.commands.cooldowns import BucketType
from typing import Union
from lib.bot import TRUSTED_IDS
from discord.ext.commands import Cog, command
from discord.ext.commands.core import cooldown, has_permissions
from discord.ext.commands.errors import BadArgument
from PyDictionary import PyDictionary
import json, re, discord
from urllib.request import urlopen
from urllib.parse import quote as urlquote

UD_DEFINE_URL = 'https://api.urbandictionary.com/v0/define?term='


class Utility(Cog):
    def __init__(self,bot):
        self.bot = bot
        
    def get_urban_json(self,url):
        with urlopen(url) as f:
            data = json.loads(f.read().decode('utf-8'))
        return data

    def parse_urban_json(self,json, check_result=True):
        definitions = []
        if json is None or any(e in json for e in ('error', 'errors')):
            raise BadArgument
        if check_result and ('list' not in json or len(json['list']) == 0):
            return []
        word = json["list"][0]["word"]
        for entry in json['list'][:3]:

            definition = entry['definition']
            example = entry["example"]

            upvotes = (entry["thumbs_up"])
            downvotes = (entry["thumbs_down"])
            definition = re.sub("[\[\]]", "", definition)
            example = re.sub("[\[\]]", "", example)
            if definition.endswith("\n"):
                definition = definition[:-2]
            if example.endswith("\n"):
                example = example[:-2]
            if len(definition) + len(example) > 950:
                if len(definition) > 967:
                    definition = definition[:840] + "..."
                    example = ""
                else:
                    length_left = 800 - len(definition)
                    example = example[:length_left] + "..."
            definition = definition.replace("\n","\n> ")
            example = example.replace("\n","\n> ")
            definitions.append((definition,example, upvotes, downvotes))
        return((word,definitions))


    def urbandefine(self, term):
        """
        Searches through Urban Dictionary and returns 
        both the word and the list of definitions with examples.
        term -- term or phrase to search for (str)
        """
        json = self.get_urban_json(UD_DEFINE_URL + urlquote(term))
        return self.parse_urban_json(json)

    @has_permissions(manage_messages=True)
    @cooldown(1,60,BucketType.user)
    @command(name="Purge", brief="Deletes the last x messages in a chat (Limit = 25)", aliases = ["purge","p"])
    async def purge(self,ctx,limit: int = 1):
        if limit > 25:
            await ctx.send(f"You have entered too many messages to purge ({limit}). The max is 25")
        else:
            await ctx.channel.purge(limit = limit + 1) # This shouldn't be += one as they are 2 different limits
            self.bot.log_command(ctx,"purge",str(limit))
        if ctx.author.id in TRUSTED_IDS:
            ctx.command.reset_cooldown(ctx)
        self.bot.log_command(ctx,"purge",limit)

    @command(name="Type",brief="Types out a message as the bot",aliases=["type"])
    async def type_msg(self,ctx,*,message):
        await ctx.message.delete()
        await ctx.channel.send(message)
        self.bot.log_command(ctx,"type",message)
    
    @command(name="Define",brief="Looks up the definition of a word",aliases=["define"])
    async def define(self,ctx,*,word):
        dictionary = PyDictionary()
        definition = dictionary.meaning(word)
        wait_msg = await ctx.send(f"Searching for the word `{word}`, please wait.....")
        if definition is not None:
            newkeys = definition.keys()
            newmsg = definition.values()
            
            for item in zip(newkeys,newmsg):
                message = ""
                word_type=(item[0])
                for chr in item[1][:2]:
                    message +="- "+(chr.capitalize())
                    message += "\n"
            fields = [(word_type,message,False)]
            embed = self.bot.auto_embed(
                type="info",
                title=f"Definition of {word}",
                fields=fields,
                ctx=ctx
            )
        if definition is None:
            embed = self.bot.auto_embed(
                type="error",
                title="**Word not found**",
                description="Cannot find that word, it may not exist in the dictionary but please check the spelling.",
                ctx=ctx
            )
        await ctx.send(embed=embed)
        await wait_msg.delete()
        self.bot.log_command(ctx,"define",word)

    @command(name="Urban Dictionary",brief="Finds the top 3 results from urban dictionary of a chosen word",aliases=["urban","urbandictionary"])
    async def urbandictionary(self,ctx,*,word):
        wait_msg = await ctx.send(f"Looking up the Urban Dictionary meaning of {word}")
        word_and_definition = self.urbandefine(word)
        if word_and_definition != []:
            word, definition = word_and_definition[0], word_and_definition[1]
            fields = []
            for i,item in enumerate(definition):
                field_value = f"**Definition**:\n> {item[0]}\n\n**Example:**\n> {item[1]}\n** **"
                up_and_down_votes = f"\n<:upvote:846117123871998036>{item[2]}<:downvote:846117121854537818>{item[3]}"
                if i == 0:
                    fields.append(("Top definition " + up_and_down_votes,field_value,False))
                else:
                    fields.append((f"Definition {i+1} " + up_and_down_votes,field_value,False))
            linkword = word.replace(" ","%20")
            link = f"https://www.urbandictionary.com/define.php?term={linkword}"
            embed = self.bot.auto_embed(
                type="info",
                title=f"Urban Dictionary definition of `{word}`:",
                description=f"To view all definitions, [Click Here]({link})", 
                fields = fields,
                ctx=ctx
            )
        else:
            embed = self.bot.auto_embed(
                type="error",
                title="**Word not found**",
                description=f"Couldn't find {word}. It may not exist in urbandictionary but please check the spelling",
                ctx=ctx
            )
        await ctx.send(embed=embed)
        await wait_msg.delete()
        self.bot.log_command(ctx,"urbandictionary",word)

    @command(name="Big",brief="Enlarges a custom emoji.\n> **NOTE: Does not work with default discord emoji**",aliases=["big","b"])
    async def big(self,ctx, emoji: Union[discord.Emoji, discord.PartialEmoji]):
        try:
            await ctx.message.delete()
            embed = self.bot.auto_embed(
                type="emoji",
                title =f"Showing an enlarged `{emoji.name}`",
                emoji_url= str(emoji.url),
                ctx=ctx
                )
            await ctx.send(embed=embed)
            self.bot.log_command(ctx,str(emoji))
        except:
            raise BadArgument
    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up("utility")
        print("utility cog ready!")

def setup(bot):
    bot.add_cog(Utility(bot))






