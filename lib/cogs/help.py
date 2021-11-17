from discord.ext.commands import Cog, bot, cog, command
from discord.ext.commands.errors import BadArgument, CommandNotFound
from lib.bot import Bot, get_prefix, get_prefix_value

NL = "\n" # Newlines can't be used in f strings so a variable is used

class HelpCog(Cog):
    def __init__(self,bot):
        self.bot = bot
        self.bot.remove_command("help")

    def create_help_output(self, commands, ctx) -> list:
        # Takes input as a list of discord commands, returns list of fields to be used in an embed
        fields = []
        prefix = get_prefix_value(ctx)
        nl = "\n"
        for command in commands:
            command_syntax = self.syntax(command)
            name = command.name or str(command)
            value = f"> {command.brief or 'No description'}{nl}```md{nl}{prefix}{command_syntax}```"
            inline = False
            fields.append((name,value,inline))
        return fields
    
    def syntax(self,command):
        if command.aliases == []:
            aliases = str(command)
        else:
            aliases = "|".join(command.aliases)
        params = []
        for key,value in command.params.items():
            if key not in ("self", "ctx"):
                params.append(f"[{key}]" if "None" in str(value) else f"<{key}>")
        params_str = " ".join(params)
        if len(params_str) == 0:
            return (f"{aliases}")
        else:
            return (f"{aliases} {params_str}")
    
    @command(name="Help", brief="Show information on all commands and cogs",aliases=["help","h"])
    async def help(self, ctx, cmd = None):
        self.bot.log_command(ctx,"help",cmd)
        lowercase_cognames = [str(cog).lower() for cog in self.bot.cogs]
        cognames = [str(cog) for cog in self.bot.cogs]
        lowercase_commands = [str(command).lower() for command in self.bot.commands]
        all_aliases = []
        commands_with_aliases = {}

        for command in self.bot.commands:
            commands_with_aliases[str(command)] = command.aliases
        
        for item in (list(commands_with_aliases.values())):
            for x in item:
                all_aliases.append(x)
        if cmd is None:
            # Shows basic help command, listing all cogs
            nl = "\n" # Newlines can't be used in f strings so a variable is used
            title = "Help"
            description = f"Here is a list of all cogs in Vitaly Petrov.{nl}Use `{get_prefix_value(ctx)}help COG` for more information on a cog."\
                          f"{nl}Use `{get_prefix_value(ctx)}help COMMAND` for information on a command.{nl}{nl}Available cogs:```ml{nl} > {f'{nl} > '.join(cognames)}```"
                
            embed = self.bot.auto_embed(
                type = "info",
                title= title,
                description = description,
                ctx = ctx
            )
            await ctx.send(embed=embed)

        else:
            # Searches for a cog or command matching cmd
            if cmd.lower() in lowercase_cognames:
                
                # Searches list of actual cogs for user input
                index = (lowercase_cognames.index(cmd.lower()))
                cogname = (cognames[index])
                cog_meta = self.bot.get_cog(cogname)
                get_version = False
                try:
                    version = cog_meta.__version__
                    get_version = True
                except:
                    pass
                if get_version:
                    version_info = f"**Version: `{version}`**{NL}"
                else:
                    version_info = ""
                cog_commands = cog_meta.get_commands()
                help_commands = self.create_help_output(cog_commands, ctx)
                embed = self.bot.auto_embed(
                    type="info",
                    title = f"Help with {cogname}",
                    description = version_info + f"Showing all {len(cog_commands)} commands in {cogname} cog. Anything in blue is a required argument.",
                    fields=help_commands,
                    ctx=ctx
                )
                await ctx.send(embed=embed)
            elif cmd.lower() in lowercase_commands:
                index = (lowercase_commands.index(cmd.lower()))
                command = (list(self.bot.commands)[index])
                help_commands = self.create_help_output([command], ctx)
                embed = self.bot.auto_embed(
                    type="info",
                    title = f"Help with {command.name or str(command)}",
                    description = f"Anything in blue is a required argument",
                    fields=help_commands,
                    ctx=ctx
                )
                await ctx.send(embed=embed)
            elif cmd in all_aliases:
                for key,value in commands_with_aliases.items():
                    for alias in value:
                        if cmd == alias:
                            command = key

                index = (lowercase_commands.index(command.lower()))
                command = (list(self.bot.commands)[index])
                help_commands = self.create_help_output([command], ctx)
                embed = self.bot.auto_embed(
                    type="info",
                    title = f"Help on {command.name or str(command)}",
                    description = f"Anything in blue is a required argument",
                    fields=help_commands,
                    ctx=ctx
                )
                await ctx.send(embed=embed)
            else:
                raise CommandNotFound

def setup(bot):
    bot.add_cog(HelpCog(bot))
