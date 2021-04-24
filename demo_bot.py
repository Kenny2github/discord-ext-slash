import os
import logging
import asyncio
import discord
from discord.ext import slash

client = slash.SlashBot(
    # Pass help_command=None if the bot only uses slash commands
    command_prefix='/', description='', help_command=None,
    debug_guild=int(os.environ.get('DISCORD_DEBUG_GUILD', 0)) or None,
    resolve_not_fetch=False, fetch_if_not_get=True
)

@client.slash_cmd()
async def hello(ctx: slash.Context):
    """Hello World!"""
    await ctx.respond('Hello World!', ephemeral=True)

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
    # By default, this sends a message and shows
    # the command invocation in a reply-like UI
    await ctx.respond(choice, allowed_mentions=discord.AllowedMentions.none())

msg_opt = slash.Option(
    # By default, options are string options
    description='Message to send', required=True)
eph_opt = slash.Option(
    description='Whether to send it ephemerally',
    # but they can be a bunch of other things
    type=slash.ApplicationCommandOptionType.BOOLEAN)

@say.slash_cmd()
async def repeat(ctx: slash.Context, message: msg_opt, ephemeral: eph_opt = False):
    """Make the bot repeat your message."""
    await ctx.respond(message, allowed_mentions=discord.AllowedMentions.none(),
                      # Setting this will make the message only visible to the invoker
                      ephemeral=ephemeral)

delay_opt = slash.Option(
    description='How long to wait first',
    type=slash.ApplicationCommandOptionType.INTEGER)

@say.slash_cmd()
async def wait(ctx: slash.Context, message: msg_opt, delay: delay_opt = 5):
    """Make the bot wait a bit before repeating your message."""
    # sends a "Bot is thinking..." response - if there is long processing to do,
    # send this first and make the actual response later
    await ctx.respond(deferred=True)
    await asyncio.sleep(delay)
    # make the actual response with a second respond() call (not send or webhook.send!)
    # further respond() calls after *this* one will edit the message
    await ctx.respond(message, allowed_mentions=discord.AllowedMentions.none())
    await asyncio.sleep(delay)
    # further messages after the response must be sent through the webhook
    await ctx.webhook.send('An extra message')

@client.slash_cmd(name='names')
async def names(
    ctx: slash.Context,
    # You can have Discord models as options too
    # They will have a good amount of information
    # even if the bot user is not in the guild
    channel: slash.Option(description='A channel',
                          type=slash.ApplicationCommandOptionType.CHANNEL),
    user: slash.Option(description='A user',
                       type=slash.ApplicationCommandOptionType.USER),
    role: slash.Option(description='A role',
                       type=slash.ApplicationCommandOptionType.ROLE)
):
    """Return a combination of names, somehow."""
    await ctx.respond(f'```{channel.name!r} {user.name!r} {role.name!r}```',
                      ephemeral=True)

@client.slash_cmd()
async def stop(ctx: slash.Context):
    """Stop the bot."""
    await ctx.respond('Goodbye', ephemeral=True)
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
