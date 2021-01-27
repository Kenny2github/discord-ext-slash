import os
import logging
import discord
from discord.ext import slash

client = slash.SlashBot(
    # Pass help_command=None if the bot only uses slash commands
    command_prefix='/', description='', help_command=None,
    debug_guild=int(os.environ.get('DISCORD_DEBUG_GUILD', 0)) or None
)

@client.slash_cmd()
async def hello(ctx: slash.Context):
    """Hello World!"""
    await ctx.respond('Hello World!', flags=slash.MessageFlags.EPHEMERAL,
                      rtype=slash.InteractionResponseType.ChannelMessage)

@client.slash_group()
async def say(ctx: slash.Context):
    """Send a message in the bot's name."""
    print('Options:', ctx.options)

@say.check
async def check_no_hashtags(ctx: slash.Context):
    if 'message' in ctx.options and '#' in ctx.options['message']:
        await ctx.respond(embeds=[
            discord.Embed(title='No hashtags!',color=0xff0000)])
        # Returning False (not None!) prevents subcommands from running
        return False

emote_opt = slash.Option(
    description='Message to send', required=True,
    choices=['Hello World!', 'This is a premade message.',
             slash.Choice('This will not say what this says.', 'See?')]
)

@say.slash_cmd()
async def emote(ctx: slash.Context, choice: emote_opt):
    """Send a premade message."""
    await ctx.respond(choice, allowed_mentions=discord.AllowedMentions.none(),
                      # sends a message without showing the command invocation
                      rtype=slash.InteractionResponseType.ChannelMessageWithSource)

msg_opt = slash.Option(
    description='Message to send', required=True)

@say.slash_cmd()
async def repeat(ctx: slash.Context, message: msg_opt):
    """Make the bot repeat your message."""
    await ctx.respond(message, allowed_mentions=discord.AllowedMentions.none(),
                      # sends a message, showing command invocation
                      rtype=slash.InteractionResponseType.ChannelMessageWithSource)

@client.slash_cmd()
async def stop(ctx: slash.Context):
    """Stop the bot."""
    await ctx.respond(rtype=slash.InteractionResponseType.Acknowledge)
    await client.close()

@stop.check
async def check_owner(ctx: slash.Context):
    if client.app_info.owner.id != ctx.author.id:
        await ctx.respond(embeds=[
            discord.Embed(title='You are not the owner!', color=0xff0000)])
        return False

# show extension logs
logger = logging.getLogger('discord.ext.slash')
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())

token = os.environ['DISCORD_TOKEN'].strip()

try:
    client.run(token)
finally:
    print('Goodbye.')
