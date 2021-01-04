'''
Support slash commands.

Example Usage
=============

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
        # propagate. Useful because commands are
        # re-registered every time the bot starts.
        debug_guild=7293012031203012
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
        """Send a message in the bot's name""" # description of command
        await ctx.respond(message, # respond to the interaction
            # sends a message without showing the command invocation
            rtype=slash.InteractionResponseType.ChannelMessage)

    client.run(token)

Notes
=====
* ``slash.Context`` emulates ``commands.Context``, but only to a certain extent.
  Notably, ``ctx.message`` does not exist, because slash commands can be run
  completely without the involvement of messages. However, channel and author
  information is still available.
* All descriptions are **required**.

Not Yet Supported
=================
* Subcommands
'''
from __future__ import annotations
from enum import IntEnum
from typing import Coroutine, Union
import datetime
import asyncio
import discord
from discord.ext import commands

__version__ = '0.0.0'

class ApplicationCommandOptionType(IntEnum):
    """Possible option types. Default is ``STRING``."""
    SUB_COMMAND = 1
    SUB_COMMAND_GROUP = 2
    STRING = 3
    INTEGER = 4
    BOOLEAN = 5
    USER = 6
    CHANNEL = 7
    ROLE = 8

class InteractionResponseType(IntEnum):
    """Possible ways to respond to an interaction.

    .. attribute:: Pong

        Only used to ACK a Ping, never valid here.
        Included only for completeness
    .. attribute:: Acknowledge

        ACK a command without sending a message and without showing user input.
        Probably best used for debugging commands.
    .. attribute:: ChannelMessage

        Respond with a message, but don't show user input.
        Probably best suited for admin commands
    .. attribute:: ChannelMessageWithSource

        Show user input and send a message. Default.
    .. attribute:: AcknowledgeWithSource

        Show user input and do nothing else.
        Probably best suited for regular commands that require no response.
    """
    # ACK a Ping
    Pong = 1
    # ACK a command without sending a message, eating the user's input
    Acknowledge = 2
    # respond with a message, eating the user's input
    ChannelMessage = 3
    # respond with a message, showing the user's input
    ChannelMessageWithSource = 4
    # ACK a command without sending a message, showing the user's input
    AcknowledgeWithSource = 5

class _Route(discord.http.Route):
    BASE = 'https://discord.com/api/v8'

class Context(discord.Object):
    """Object representing an interaction.

    Attributes
    -----------
    id: :class:`int`
        The interaction ID.
    guild: Union[:class:`discord.Guild`, :class:`discord.Object`]
        The guild where the interaction took place.
        Can be an Object with just the ID if the client is not in the guild.
    channel: Union[:class:`discord.TextChannel`, :class:`discord.Object`]
        The channel where the command was run.
        Can be an Object with just the ID if the client is not in the guild.
    author: :class:`discord.Member`
        The user who ran the command.
        If ``guild`` is an Object, a lot of methods that require the guild
        will break and should not be relied on.
    command: :class:`Command`
        The command that was run.
    me: Optional[:class:`discord.Member`]
        The bot, as a ``Member`` in that context.
        Can be None if the client is not in the guild.
    client: :class:`SlashBot`
        The bot.
    webhook: Optional[:class:`discord.Webhook`]
        Webhook used for sending followup messages.
        None until interaction response has been sent
    """
    def __init__(self, client: SlashBot):
        self.client = client

    async def _ainit(self, event: dict):
        self.id = event['id']
        try:
            self.guild = await self.client.fetch_guild(event['guild_id'])
        except discord.HTTPException:
            self.guild = discord.Object(event['guild_id'])
        try:
            self.channel = await self.client.fetch_channel(event['channel_id'])
        except discord.HTTPException:
            self.channel = discord.Object(event['channel_id'])
        try:
            self.author = await self.guild.fetch_member(event['member']['user']['id'])
        except discord.HTTPException:
            self.author = discord.Member(
                data=event['member'], guild=self.guild, state=self.client._connection)
        self.token = event['token']
        self.command = event['data']['name']
        try:
            self.me = await self.guild.fetch_member(self.client.user.id)
        except (discord.HTTPException, AttributeError):
            self.me = None
        self.webhook = None

    async def respond(self, content='', *, embeds=None, allowed_mentions=None,
                      rtype=InteractionResponseType.ChannelMessageWithSource):
        """Respond to the interaction. If called again, edits the response.

        Parameters
        -----------
        content: :class:`str`
            The content of the message.
        embeds: Iterable[:class:`discord.Embed`]
            Up to 10 embeds (any more will be silently discarded)
        allowed_mentions: :class:`discord.AllowedMentions`
            Mirrors normal ``allowed_mentions`` in Messageable.send
        rtype: :class:`InteractionResponseType`
            The type of response to send. See that class's documentation.
        """
        if embeds:
            embeds = [emb.to_dict() for emb, _ in zip(embeds, range(10))]
        mentions = self.client.allowed_mentions
        if mentions is not None and allowed_mentions is not None:
            mentions = mentions.merge(allowed_mentions)
        if self.webhook is not None:
            data = {}
            if content:
                data['content'] = content
            if embeds:
                data['embeds'] = embeds
            if mentions is not None:
                data['allowed_mentions'] = mentions.to_dict()
            path = f"/webhooks/{self.client.app_info.id}/{self.token}" \
                "/messages/@original"
            route = _Route('PATCH', path, channel_id=self.channel.id,
                           guild_id=self.guild.id)
        else:
            data = {
                'type': rtype
            }
            if content or embeds:
                data['data'] = {'content': content}
            elif rtype in {InteractionResponseType.ChannelMessage,
                        InteractionResponseType.ChannelMessageWithSource}:
                raise ValueError('sending channel message with no content')
            if embeds:
                data['data']['embeds'] = embeds
            if mentions is not None:
                data['allowed_mentions'] = mentions.to_dict()
            path = f"/interactions/{self.id}/{self.token}/callback"
            route = _Route('POST', path, channel_id=self.channel.id,
                           guild_id=self.guild.id)
            self.webhook = discord.Webhook.partial(
                id=self.client.app_info.id, token=self.token, adapter=
                discord.AsyncWebhookAdapter(self.client.http._HTTPClient__session))
        await self.client.http.request(route, json=data)

    async def delete(self):
        """Delete the original interaction response message."""
        path = f"/webhooks/{self.client.app_info.id}/{self.token}" \
            "/messages/@original"
        route = _Route('DELETE', path, channel_id=self.channel.id,
                       guild_id=self.guild.id)
        await self.client.http.request(route)

    async def send(self, *args, **kwargs):
        """Send a message in the channel where the the command was run.

        Only method that works after the interaction token has expired.
        Only works if client is present there as a bot user too.
        """
        await self.channel.send(*args, **kwargs)

Interaction = Context

class Option:
    """An argument to a :class:`Command`.
    This must be passed as an annotation to the corresponding argument.

    Parameters
    -----------
    description: :class:`str`
        The description of the option, displayed to users.
    type: :class:`ApplicationCommandOptionType`
        The argument type. This defaults to
        :attr:`ApplicationCommandOptionType.STRING`
    name: Optional[:class:`str`]
        The name of the option, if different from its argument name.
    default: Optional[:class:`bool`]
        If ``True``, this is the first ``required`` option to complete.
        Only one option can be ``default``. This defaults to ``False``.
    required: Optional[:class:`bool`]
        If ``True``, this option must be specified for a valid command
        invocation. Defaults to ``False``.
    choices: Optional[Iterable[:class:`Choice`]]
        If specified, only these values are allowed for this option.
    """
    name = None

    def __init__(self, description: str,
                 type=ApplicationCommandOptionType.STRING, **kwargs):
        self.name = kwargs.pop('name', None) # can be set automatically
        self.type = type
        self.description = description
        self.default = kwargs.pop('default', False)
        self.required = kwargs.pop('required', False)
        self.choices = kwargs.pop('choices', None)

    def to_dict(self):
        data = {
            'type': int(self.type),
            'name': self.name,
            'description': self.description,
        }
        if self.default:
            data['default'] = self.default
        if self.required:
            data['required'] = self.required
        if self.choices is not None:
            data['choices'] = [choice.to_dict for choice in self.choices]
        return data

class Choice:
    """Represents one choice for an option value.

    Parameters
    -----------
    name: :class:`str`
        The description of the choice, displayed to users.
    value: Union[:class:`str`, :class:`int`]
        The actual value fed into the application.
    """
    def __init__(self, name: str, value: Union[str, int]):
        self.name = name
        self.value = value

    def to_dict(self):
        return {'name': self.name, 'value': self.value}

class Command:
    """Represents a slash command.

    Attributes
    -----------
    id: Optional[:class:`int`]
        ID of registered command. Can be None when not yet registered.
    name: :class:`str`
        Command name. Defaults to method name
    description: :class:`str`
        Description shown in command list. Defaults to method doc.
    guild_id: Optional[:class:`int`]
        If present, this command only exists in this guild.
    options: Mapping[:class:`str`, :class:`Option`]
        Options for this command.
    method: Coroutine
        Original callback for the command
    """
    def __init__(self, method: Coroutine, name=None, **kwargs):
        self.id = None
        self.name = name or method.__name__
        self.description = kwargs.pop('description', method.__doc__)
        self.guild_id = kwargs.pop('guild', None)
        self._ctx_arg = None
        self.options = {}
        for arg, typ in method.__annotations__.items():
            if typ is Context:
                self._ctx_arg = arg
            if isinstance(typ, Option):
                self.options[arg] = typ
                if typ.name is None:
                    typ.name = arg
        if self._ctx_arg is None:
            raise ValueError('One argument must be type-hinted SlashContext')
        self.method = method

    def __hash__(self):
        return hash((self.name, self.guild_id))

    def to_dict(self):
        data = {
            'name': self.name,
            'description': self.description
        }
        if self.options:
            data['options'] = [opt.to_dict() for opt in self.options.values()]
        return data

    async def invoke(self, ctx, options):
        kwargs = {self._ctx_arg: ctx}
        for opt in options:
            value = opt.get('value', None)
            opttype = self.options[opt['name']].type
            if opttype == ApplicationCommandOptionType.USER:
                value = await ctx.guild.fetch_member(int(value))
            elif opttype == ApplicationCommandOptionType.CHANNEL:
                value = await ctx.guild.fetch_channel(int(value))
            elif opttype == ApplicationCommandOptionType.ROLE:
                value = ctx.guild.get_role(int(value))
            kwargs[opt['name']] = value
        await self.method(**kwargs)

def cmd(**kwargs):
    """Decorator that transforms a function into a :class:`Command`"""
    def decorator(func):
        return Command(func, **kwargs)
    return decorator

class SlashBot(commands.Bot):
    """A bot that supports slash commands."""

    def __init__(self, *args, **kwargs):
        self.debug_guild = kwargs.pop('debug_guild', None)
        super().__init__(*args, **kwargs)
        self.slash = set()
        self._connection.parsers['INTERACTION_CREATE'] = lambda data: (
            self._connection.dispatch('interaction_create', data))
        @self.listen()
        async def on_ready():
            await self.register_commands()
            self.remove_listener(on_ready)

    def slash_cmd(self, **kwargs):
        """See :class:`Command` doc"""
        def decorator(func):
            cmd = Command(func, **kwargs)
            self.slash.add(cmd)
            return cmd
        return decorator

    def add_slash(self, func, **kwargs):
        """See :class:`Command` doc"""
        self.slash.add(Command(func, **kwargs))

    def add_slash_cog(self, cog):
        """Add all attributes of ``cog`` are :class:`Command` instances."""
        for key in dir(cog):
            obj = getattr(cog, key)
            if isinstance(obj, Command):
                self.slash.add(obj)

    async def application_info(self):
        self.app_info = await super().application_info()
        return self.app_info

    async def on_interaction_create(self, event: dict):
        ctx = Context(self)
        await ctx._ainit(event)
        for maybe_cmd in self.slash:
            if maybe_cmd.id == event['data']['id']:
                cmd = maybe_cmd
                break
        else:
            self.dispatch('error', commands.CommandNotFound(
                f'No command {ctx.command!r} found'))
        ctx.command = cmd
        try:
            await cmd.invoke(ctx, event['data'].get('options', []))
        except commands.CommandError as exc:
            self.dispatch('command_error', ctx, exc)
        except asyncio.CancelledError:
            return
        except Exception as exc:
            try:
                raise commands.CommandInvokeError(exc) from exc
            except commands.CommandInvokeError as exc2:
                self.dispatch('command_error', ctx, exc2)

    async def register_commands(self):
        app_info = await self.application_info()
        global_path = f"/applications/{app_info.id}/commands"
        guild_path = f"/applications/{app_info.id}/guilds/{{0}}/commands"
        for cmd in self.slash:
            data = cmd.to_dict()
            if cmd.guild_id is not None:
                # guild-specific commands
                route = _Route('POST', guild_path.format(cmd.guild_id))
            else:
                route = _Route(
                    'POST',
                    guild_path.format(self.debug_guild)
                    if self.debug_guild is not None
                    else global_path)
            await self.register_command(cmd, route, data)

    async def register_command(self, cmd, route, data):
        resp = await self.http.request(route, json=data)
        cmd.id = resp['id']

# TODO: subcommands