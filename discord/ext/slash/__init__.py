'''
Support slash commands.

Example Usage
~~~~~~~~~~~~~

.. code-block:: python

    from discord.ext import slash
    client = slash.SlashBot(
        # normal arguments to commands.Bot()
        command_prefix='.', description="whatever",
        # special option: modify all global commands to be
        # actually guild commands for this guild instead,
        # for the purposes of testing. Remove this argument
        # or set it to None to make global commands be
        # properly global - note that they take 1 hour to
        # propagate. Useful because commands have to be
        # re-registered if their API definitions are changed.
        debug_guild=staging_guild_id
    )

    msg_opt = slash.Option(
        # description of option, shown when filling in
        description='Message to send',
        # this means that the slash command will not be invoked
        # if this argument is not specified
        required=True)

    @client.slash_cmd() # global slash command
    async def repeat( # command name
        ctx: slash.Context, # there MUST be one argument annotated with Context
        message: msg_opt
    ):
        """Make the bot repeat what you say""" # description of command
        # respond to the interaction, must be done within 3 seconds
        await ctx.respond(message) # string (or str()able) message

    client.run(token)

Notes
~~~~~

* :class:`~discord.ext.slash.Context` emulates
  :class:`discord.ext.commands.Context`, but only to a certain extent.
  Notably, ``ctx.message`` does not exist, because slash commands can be run
  completely without the involvement of messages. However, channel and author
  information is still available.
* On the other hand, :class:`~discord.ext.slash.ComponentContext` does have a
  :attr:`~discord.ext.slash.ComponentContext.message` attribute
  available to message component callbacks.
* All descriptions are **required**.
* You must grant the bot ``applications.commands`` permissions in the OAuth2
  section of the developer dashboard.

See the `docs <https://discord-ext-slash.rtfd.io>`_ as well as the
`demo bot <https://github.com/Kenny2github/discord-ext-slash/blob/main/demo_bot.py>`_.
'''
from __future__ import annotations
from .simples import (
    SlashWarning, ApplicationCommandOptionType,
    ApplicationCommandPermissionType, InteractionType, InteractionResponseType,
    InteractionCallbackType, CallbackFlags, ChoiceEnum, ButtonStyle,
    PartialRole, PartialCategoryChannel, PartialMember, PartialObject,
    PartialTextChannel, PartialVoiceChannel
)
from .option import Option, Choice
from .components import (
    MessageComponent, ActionRow, Button,
    SelectMenu, SelectOption
)
from .message import ComponentedMessage
from .command import (
    BaseCallback, Command, Group, cmd, group, permit,
    callback, CommandPermissionsDict, ComponentCallback
)
from .context import BaseContext, Context, Interaction, ComponentContext
from .bot import SlashBot

__all__ = [
    'SlashWarning',
    'ApplicationCommandOptionType',
    'ApplicationCommandPermissionType',
    'InteractionType',
    'InteractionCallbackType',
    'CallbackFlags',
    'ChoiceEnum',
    'ButtonStyle',
    'BaseContext',
    'Context',
    'Interaction',
    'ComponentContext',
    'Option',
    'Choice',
    'MessageComponent',
    'ActionRow',
    'Button',
    'SelectMenu',
    'SelectOption',
    'CommandPermissionsDict',
    'BaseCallback',
    'Command',
    'Group',
    'ComponentCallback',
    'cmd',
    'group',
    'permit',
    'callback',
    'SlashBot'
]

__version__ = '1.0.0b2'
