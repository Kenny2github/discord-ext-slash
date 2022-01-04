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
    # any real number, like 2 or 4.3
    type=slash.ApplicationCommandOptionType.NUMBER)
count_opt = slash.Option(
    description='How many times to repeat the message',
    # integers only, like 1 or 3
    type=slash.ApplicationCommandOptionType.INTEGER)

@say.slash_cmd()
async def wait(
    ctx: slash.Context, message: msg_opt,
    delay: delay_opt = 5, count: count_opt = 1
):
    """Make the bot wait a bit before repeating your message."""
    # sends a "Bot is thinking..." response - if there is long processing to do,
    # send this first and make the actual response later
    await ctx.respond(deferred=True)
    # long processing
    await asyncio.sleep(delay)
    # make the actual response with a second respond() call (not send or webhook.send!)
    # further respond() calls after *this* one will edit the message
    await ctx.respond(message, allowed_mentions=discord.AllowedMentions.none())
    for _ in range(count):
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
                       type=slash.ApplicationCommandOptionType.ROLE),
    # This option type will try to resolve to either a user or a role.
    # It can be thought of as a union of USER and ROLE.
    ping: slash.Option(description='Someone/something to ping',
                       type=slash.ApplicationCommandOptionType.MENTIONABLE),
    # If you want to limit the channel type (e.g. text channels only),
    # forgo the `type` parameter and use `channel_type(s)` instead
    text_channel: slash.Option(description='A text channel',
                               channel_type=discord.ChannelType.text),
):
    """Return a combination of names, somehow."""
    emb = discord.Embed()
    emb.add_field(name='Channel Name', value=channel.name)
    emb.add_field(name='User Name', value=user.name)
    emb.add_field(name='Role Name', value=role.name)
    emb.add_field(name='Ping', value=ping.mention)
    emb.add_field(name='Text Channel Name', value=text_channel.name)
    await ctx.respond(embed=emb, ephemeral=True)

class ArithmeticOperator(slash.ChoiceEnum):
    # The docstring is used as the description of the
    # option - it is required
    """The operation to perform on the numbers."""
    # Only string options are supported by ChoiceEnum
    ADDITION = '+'
    SUBTRACTION = '-'
    MULTIPLICATION = '\N{MULTIPLICATION SIGN}'
    DIVISION = '\N{DIVISION SIGN}'

@client.slash_cmd()
async def numbers(
    ctx: slash.Context,
    num1: slash.Option(description='The first number',
                       min_value=0),
    operator: ArithmeticOperator, # see above
    num2: slash.Option(description='The second number',
                       min_value=-4.20, max_value=6.9),
):
    """Do some math! (With limitations)"""
    if operator == ArithmeticOperator.ADDITION:
        value = num1 + num2
    elif operator == ArithmeticOperator.SUBTRACTION:
        value = num1 - num2
    elif operator == ArithmeticOperator.MULTIPLICATION:
        value = num1 * num2
    elif operator == ArithmeticOperator.DIVISION:
        value = num1 / num2
    await ctx.respond(value, ephemeral=True)

@client.slash_cmd(default_permission=False)
async def stop(ctx: slash.Context):
    """Stop the bot."""
    await ctx.respond('Goodbye', ephemeral=True)
    await client.close()

@client.event
async def on_slash_permissions():
    stop.add_perm(client.app_info.owner, True, None)
    await client.register_permissions()

@client.event
async def on_before_slash_command_invoke(ctx: slash.Context):
    logger.info('User %s running /%s', ctx.author, ctx.command)

# show extension logs
logger = logging.getLogger('discord.ext.slash')
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())
logger.handlers[0].setFormatter(logging.Formatter(
    '{levelname}\t{name}\t{asctime} {message}', style='{'))

token = os.environ['DISCORD_TOKEN'].strip()

try:
    client.run(token)
finally:
    print('Goodbye.')
