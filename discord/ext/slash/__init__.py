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
        """Send a message in the bot's name""" # description of command
        # respond to the interaction, must be done within 3 seconds
        await ctx.respond(message, # string (or str()able) message
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

See the wiki_.

.. _wiki: https://github.com/Kenny2github/discord-ext-slash/wiki
'''
from __future__ import annotations
import sys
from enum import IntEnum
from typing import Coroutine, Union, Optional, Mapping, Any, List
from functools import partial
import logging
import asyncio
import discord
from discord.ext import commands

__all__ = [
    'ApplicationCommandOptionType',
    'InteractionResponseType',
    'MessageFlags',
    'Context',
    'Interaction',
    'Option',
    'Choice',
    'Command',
    'Group',
    'cmd',
    'group',
    'SlashBot'
]

__version__ = '0.3.0pre4'

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
        Probably best suited for admin commands,
        or commands with ephemeral responses.
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

class MessageFlags(IntEnum):
    """Flags to pass to the ``flags`` argument of the interaction response.
    See also: https://discord.dev/resources/channel#message-object-message-flags
    """
    CROSSPOSTED = 1 << 0
    IS_CROSSPOST = 1 << 1
    SUPPRESS_EMBEDS = 1 << 2
    SOURCE_MESSAGE_DELETED = 1 << 3
    URGENT = 1 << 4
    HAS_THREAD = 1 << 5
    EPHEMERAL = 1 << 6

class _Route(discord.http.Route):
    BASE = 'https://discord.com/api/v8'

class _AsyncInit:
    async def __new__(cls, *args, **kwargs):
        inst = super().__new__(cls)
        await inst.__init__(*args, **kwargs)
        return inst

    async def __init__(self):
        pass

class Context(discord.Object, _AsyncInit):
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
    options: Mapping[:class:`str`, Any]
        The options passed to the command (including this context).
        More useful in groups and checks.
    me: Optional[:class:`discord.Member`]
        The bot, as a ``Member`` in that context.
        Can be None if the client is not in the guild.
    client: :class:`SlashBot`
        The bot.
    webhook: Optional[:class:`discord.Webhook`]
        Webhook used for sending followup messages.
        None until interaction response has been sent
    """

    id: int
    guild: Union[discord.Guild, discord.Object]
    channel: Union[discord.TextChannel, discord.Object]
    author: discord.Member
    command: Union[Command, Group]
    options: Mapping[str, Any]
    me: Optional[discord.Member]
    client: SlashBot
    webhook: Optional[discord.Webhook]

    async def __init__(self, client: SlashBot, cmd: Command, event: dict):
        self.client = client
        self.command = cmd
        self.id = int(event['id'])
        try:
            self.guild = await self.client.fetch_guild(int(event['guild_id']))
        except discord.HTTPException:
            self.guild = discord.Object(event['guild_id'])
            logger.debug('Fetching guild %s for interaction %s failed',
                         self.guild.id, self.id)
        try:
            self.channel = await self.client.fetch_channel(int(event['channel_id']))
        except discord.HTTPException:
            self.channel = discord.Object(event['channel_id'])
            logger.debug('Fetching channel %s for interaction %s failed',
                         self.channel.id, self.id)
        try:
            self.author = await self.guild.fetch_member(int(event['member']['user']['id']))
        except (discord.HTTPException, AttributeError):
            self.author = discord.Member(
                data=event['member'], guild=self.guild, state=self.client._connection)
            logger.debug('Fetching member for interaction %s failed', self.id)
        self.token = event['token']
        # construct options into function-friendly form
        await self._kwargs_from_options(event['data'].get('options', []))
        try:
            self.me = await self.guild.fetch_member(self.client.user.id)
        except (discord.HTTPException, AttributeError):
            self.me = None
            logger.debug('Fetching member %s (me) in guild %s '
                         'for interaction %s failed',
                         self.client.user.id, self.guild.id, self.id)
        self.webhook = None

    async def _kwargs_from_options(self, options):
        self.cog = self.command.cog
        kwargs = {}
        for opt in options:
            if 'value' in opt:
                value = opt['value']
                for k, v in self.command.options.items():
                    if v.name == opt['name']:
                        opt['name'] = k
                        break
                else:
                    raise commands.CommandInvokeError(
                        f'No such option: {opt["name"]!r}')
                opttype = self.command.options[opt['name']].type
                if opttype == ApplicationCommandOptionType.USER:
                    try:
                        value = await self.guild.fetch_member(int(value))
                    except (discord.HTTPException, AttributeError):
                        value = discord.Object(value)
                        logger.debug('Fetching member %s for interaction %s failed',
                                     value, self.id)
                elif opttype == ApplicationCommandOptionType.CHANNEL:
                    try:
                        value = await self.client.fetch_channel(int(value))
                    except (discord.HTTPException, AttributeError):
                        value = discord.Object(value)
                        logger.debug('Fetching channel %s for interaction %s failed',
                                     value, self.id)
                elif opttype == ApplicationCommandOptionType.ROLE:
                    value = self.guild.get_role(int(value))
                    if value is None:
                        value = discord.Object(value)
                        logger.debug('Getting role %s for interaction %s failed',
                                     value, self.id)
                kwargs[opt['name']] = value
            elif 'options' in opt:
                self.command = self.command.slash[opt['name']]
                await self._kwargs_from_options(opt['options'])
                return
        if isinstance(self.command, Group):
            self.command = self.command.slash[opt['name']]
            await self._kwargs_from_options(opt.get('options', []))
        elif isinstance(self.command, Command):
            kwargs[self.command._ctx_arg] = self
            self.options = kwargs

    def __repr__(self):
        return f'<Interaction id={self.id}>'

    async def respond(
        self, content='', *, embed=None, embeds=None, allowed_mentions=None,
        flags=None, rtype=InteractionResponseType.ChannelMessageWithSource
    ):
        """Respond to the interaction. If called again, edits the response.

        Parameters
        -----------
        content: :class:`str`
            The content of the message.
        embed: :class:`discord.Embed`
            Shorthand for respond(embeds=[embed])
        embeds: Iterable[:class:`discord.Embed`]
            Up to 10 embeds (any more will be silently discarded)
        allowed_mentions: :class:`discord.AllowedMentions`
            Mirrors normal ``allowed_mentions`` in Messageable.send
        flags: Union[int, :class:`MessageFlags`]
            Message flags, ORed together
        rtype: :class:`InteractionResponseType`
            The type of response to send. See that class's documentation.
        """
        content = str(content)
        if embed and embeds:
            raise TypeError('Cannot specify both embed and embeds')
        if embed:
            embeds = [embed]
        if embeds:
            embeds = [emb.to_dict() for emb, _ in zip(embeds, range(10))]
        mentions = self.client.allowed_mentions
        if mentions is not None and allowed_mentions is not None:
            mentions = mentions.merge(allowed_mentions)
        elif allowed_mentions is not None:
            mentions = allowed_mentions
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
                'type': int(rtype)
            }
            if content or embeds:
                data['data'] = {'content': content}
            elif rtype in {InteractionResponseType.ChannelMessage,
                        InteractionResponseType.ChannelMessageWithSource}:
                raise ValueError('sending channel message with no content')
            if embeds:
                data['data']['embeds'] = embeds
            if mentions is not None:
                data['data']['allowed_mentions'] = mentions.to_dict()
            if flags and 'data' in data:
                data['data']['flags'] = int(flags)
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
        return await self.channel.send(*args, **kwargs)

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
    required: Optional[:class:`bool`]
        If ``True``, this option must be specified for a valid command
        invocation. Defaults to ``False``.
    choices: Optional[Iterable[Union[
            :class:`str`, Mapping[str, str], :class:`Choice`]]]
        If specified, only these values are allowed for this option.
        Strings are converted into Choices with the same name and value
        Dicts are passed as kwargs to the Choice constructor.
    """
    description: str
    type: ApplicationCommandOptionType = ApplicationCommandOptionType.STRING
    name: Optional[str] = None
    required: Optional[bool] = False
    choices: Optional[List[Choice]] = None

    def __init__(self, description: str,
                 type=ApplicationCommandOptionType.STRING, **kwargs):
        self.name = kwargs.pop('name', None) # can be set automatically
        self.type = type
        self.description = description
        self.required = kwargs.pop('required', False)
        choices = kwargs.pop('choices', None)
        if choices is not None:
            self.choices = [Choice.from_data(c) for c in choices]
        else:
            self.choices = None

    def __repr__(self):
        return ("Option(name={0.name!r}, type='{0.type!s}', description=..., "
                'required={0.required}, choices={1})').format(
                    self, '[...]' if self.choices else '[]')

    def to_dict(self):
        data = {
            'type': int(self.type),
            'name': self.name,
            'description': self.description,
        }
        if self.required:
            data['required'] = self.required
        if self.choices is not None:
            data['choices'] = [choice.to_dict() for choice in self.choices]
        return data

    def clone(self):
        return type(self)(**self.to_dict())

class Choice:
    """Represents one choice for an option value.

    Parameters
    -----------
    name: :class:`str`
        The description of the choice, displayed to users.
    value: :class:`str`
        The actual value fed into the application.
    """
    name: str
    value: str

    def __init__(self, name: str, value: str):
        self.name = name
        self.value = value

    def __repr__(self):
        return f'Choice(name={self.name!r}, value={self.value!r})'

    @classmethod
    def from_data(cls, data):
        if isinstance(data, cls):
            return data
        if isinstance(data, str):
            return cls(name=data, value=data)
        return cls(**data)

    def to_dict(self):
        return {'name': self.name, 'value': self.value}

class Command:
    """Represents a slash command.

    Attributes
    -----------
    coro: Coroutine
        (Required) Original callback for the command.
    id: Optional[:class:`int`]
        ID of registered command. Can be None when not yet registered,
        or if not a top-level command.
    name: :class:`str`
        Command name. Defaults to coro name.
    description: :class:`str`
        Description shown in command list. Defaults to coro doc.
    guild_id: Optional[:class:`int`]
        If present, this command only exists in this guild.
    parent: Optional[:class:`Group`]
        Parent (sub)command group.
    options: Mapping[:class:`str`, :class:`Option`]
        Options for this command. Not passable as a parameter;
        can only be set by inspecting the function annotations.
    default: :class:`bool`
        If ``True``, invoking the base parent of this command translates
        into invoking this subcommand. (Not settable in arguments.)
    """
    cog = None
    coro: Coroutine
    id: Optional[int]
    name: str
    description: str
    guild_id: Optional[int]
    parent: Optional[Group]
    options: Mapping[str, Option]
    default: bool = False

    def __init__(self, coro: Coroutine, **kwargs):
        self.id = None
        self.name = kwargs.pop('name', coro.__name__)
        self.description = kwargs.pop('description', coro.__doc__)
        if not self.description:
            raise ValueError(f'Please specify a description for {self.name!r}')
        self.guild_id = kwargs.pop('guild', None)
        if self.guild_id is not None:
            self.guild_id = int(self.guild_id)
        self.parent = kwargs.pop('parent', None)
        self._ctx_arg = None
        self.options = {}
        for arg, typ in coro.__annotations__.items():
            if isinstance(typ, str):
                try:
                    # evaluate the annotation in its module's context
                    globs = sys.modules[coro.__module__].__dict__
                    coro.__annotations__[arg] = typ = eval(typ, globs)
                except SyntaxError:
                    continue
            try:
                if issubclass(typ, Context):
                    self._ctx_arg = arg
            except TypeError: # not even a class
                pass
            if isinstance(typ, Option):
                typ = typ.clone()
                self.options[arg] = typ
                if typ.name is None:
                    typ.name = arg
        if self._ctx_arg is None:
            raise ValueError('One argument must be type-hinted slash.Context')
        self.coro = coro
        async def check(*args, **kwargs):
            pass
        self._check = kwargs.pop('check', check)

    @property
    def qualname(self):
        """Fully qualified name of command, including group names."""
        if self.parent is None:
            return self.name
        return self.parent.qualname + ' ' + self.name

    def __str__(self):
        return self.qualname

    def __hash__(self):
        return hash((self.name, self.guild_id))

    def to_dict(self):
        data = {
            'name': self.name,
            'description': self.description
        }
        if self.options:
            data['options'] = [opt.to_dict() for opt in self.options.values()]
        # TODO: the API doesn't support this yet, so it is disabled for now.
        if self.parent is not None and False:
            data['default'] = self.default
        return data

    async def invoke(self, ctx):
        if not await self.can_run(ctx):
            raise commands.CheckFailure(
                f'The check functions for {self.qualname} failed.')
        logger.debug('User %s running, in guild %s channel %s, command: %s',
                     ctx.author.id, ctx.guild.id, ctx.channel.id,
                     ctx.command.qualname)
        await self.invoke_parents(ctx)
        if self.cog is not None:
            await self.coro(self.cog, **ctx.options)
        else:
            await self.coro(**ctx.options)

    def check(self, coro):
        """Set this command's check to this coroutine.
        Can be used as a decorator.
        """
        self._check = coro

    async def can_run(self, ctx):
        parents = []  # highest level parent last
        cogs = []
        parent = self.parent
        while parent is not None:
            if parent.cog is not None:
                if hasattr(parent.cog, 'cog_check'):
                    if parent.cog.cog_check not in cogs:
                        cogs.append(parent.cog.cog_check)
                parents.append(partial(parent._check, parent.cog))
            else:
                parents.append(parent._check)
            parent = parent.parent
        parents.extend(cogs)
        parents.extend(ctx.client._checks)
        parents.reverse()  # highest level parent first
        parents.append(self._check)
        for check in parents:
            if await check(ctx) is False:
                return False
        return True

    async def invoke_parents(self, ctx):
        parents = []
        parent = self.parent
        while parent is not None:
            if parent.cog is not None:
                parents.append(partial(parent.coro, parent.cog))
            else:
                parents.append(parent.coro)
            parent = parent.parent
        parents.reverse()
        for coro in parents:
            await coro(ctx)

class Group(Command):
    """Represents a group of slash commands.
    Attributes are the same unless documented below.

    Attributes
    -----------
    coro: Coroutine
        (Required) Callback invoked when a subcommand of this group is called.
        (This is not a check! Register a check using :func:`Group.check`.)
    slash: Mapping[:class:`str`, Union[:class:`Group`, :class:`Command`]]
        Subcommands of this group.
    """
    cog = None
    slash: Mapping[str, Union[Group, Command]]

    def __init__(self, coro: Coroutine, **kwargs):
        super().__init__(coro, **kwargs)
        self.slash = {}

    def slash_cmd(self, **kwargs):
        """See :class:`Command` doc"""
        kwargs['parent'] = self
        def decorator(func):
            cmd = Command(func, **kwargs)
            cmd.cog = self.cog
            self.slash[cmd.name] = cmd
            return cmd
        return decorator

    def add_slash(self, func, **kwargs):
        """See :class:`Command` doc"""
        self.slash_cmd(**kwargs)(func)

    def slash_group(self, **kwargs):
        """See :class:`Group` doc"""
        kwargs['parent'] = self
        def decorator(func):
            group = Group(func, **kwargs)
            group.cog = self.cog
            self.slash[group.name] = group
            return group
        return decorator

    def add_slash_group(self, func, **kwargs):
        """See :class:`Group` doc"""
        self.slash_group(**kwargs)(func)

    def default(self, cmd: Command):
        """Register ``cmd`` as the default subcommand,
        to be invoked when this base group is invoked.
        The command must already be registered in the group.

        CURRENTLY HAS NO EFFECT - default is not yet supported
        by the API, and is therefore disabled here. This library
        will be updated once the API is.
        """
        if self.slash[cmd.name] is not cmd:
            raise ValueError(f'{cmd!s} not a subcommand of {self!s}')
        for c in self.slash.values():
            c.default = c is cmd

    def to_dict(self):
        data = {
            'name': self.name,
            'description': self.description
        }
        if self.slash:
            data['options'] = []
            for sub in self.slash.values():
                ddict = sub.to_dict()
                if isinstance(sub, Group):
                    ddict['type'] = ApplicationCommandOptionType.SUB_COMMAND_GROUP
                elif isinstance(sub, Command):
                    ddict['type'] = ApplicationCommandOptionType.SUB_COMMAND
                else:
                    raise ValueError(f'What is a {type(sub).__name__} doing here?')
                data['options'].append(ddict)
        # TODO: the API doesn't support this yet, so it is disabled for now.
        if self.parent is not None and False:
            data['default'] = self.default
        return data

def cmd(**kwargs):
    """Decorator that transforms a function into a :class:`Command`"""
    def decorator(func):
        return Command(func, **kwargs)
    return decorator

def group(**kwargs):
    """Decorator that transforms a function into a :class:`Group`"""
    def decorator(func):
        return Group(func, **kwargs)
    return decorator

logger = logging.getLogger('discord.ext.slash')
logger.setLevel(logging.INFO)

class SlashBot(commands.Bot):
    """A bot that supports slash commands."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.debug_guild = int(kwargs.pop('debug_guild', 0) or 0) or None
        self.slash = set()
        @self.listen()
        async def on_ready():
            self.remove_listener(on_ready)
            # only start listening to interaction-create once ready
            self._connection.parsers.setdefault('INTERACTION_CREATE', lambda data: (
                self._connection.dispatch('interaction_create', data)))
            try:
                await self.register_commands()
            except discord.HTTPException:
                logger.exception('Registering commands failed')
                asyncio.create_task(self.close())
                raise

    def slash_cmd(self, **kwargs):
        """See :class:`Command` doc"""
        def decorator(func):
            cmd = Command(func, **kwargs)
            self.slash.add(cmd)
            return cmd
        return decorator

    def add_slash(self, func, **kwargs):
        """See :class:`Command` doc"""
        self.slash_cmd(**kwargs)(func)

    def slash_group(self, **kwargs):
        """See :class:`Group` doc"""
        def decorator(func):
            group = Group(func, **kwargs)
            self.slash.add(group)
            return group
        return decorator

    def add_slash_group(self, func, **kwargs):
        """See :class:`Group` doc"""
        self.slash_group(**kwargs)(func)

    def add_slash_cog(self, cog):
        """Add all attributes of ``cog`` that are
        :class:`Command` or :class:`Group` instances.
        """
        for key in dir(cog):
            obj = getattr(cog, key)
            if isinstance(obj, (Group, Command)):
                obj.cog = cog
                if obj.parent is None:
                    self.slash.add(obj)

    async def application_info(self):
        self.app_info = await super().application_info()
        return self.app_info

    async def on_interaction_create(self, event: dict):
        if event['version'] != 1:
            raise RuntimeError(
                f'Interaction data version {event["version"]} is not supported'
                ', please open an issue for this: '
                'https://github.com/Kenny2github/discord-ext-slash/issues/new')
        for maybe_cmd in self.slash:
            if maybe_cmd.id == int(event['data']['id']):
                cmd = maybe_cmd
                break
        else:
            raise commands.CommandNotFound(
                f'No command {event["data"]["name"]!r} found')
        ctx = await cmd.coro.__annotations__[cmd._ctx_arg](self, cmd, event)
        try:
            await ctx.command.invoke(ctx)
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
        guilds = {}
        for cmd in self.slash:
            cmd.guild_id = cmd.guild_id or self.debug_guild
            guilds.setdefault(cmd.guild_id, {})[cmd.name] = cmd
        state = {
            'POST': {},
            'PATCH': {},
            'DELETE': {}
        }
        route = _Route('GET', global_path)
        if None in guilds:
            global_cmds = await self.http.request(route)
            await self.sync_cmds(state, guilds[None], global_cmds, None)
        for guild_id, guild in guilds.items():
            if guild_id is None:
                continue
            route = _Route('GET', guild_path.format(guild_id))
            guild_cmds = await self.http.request(route)
            await self.sync_cmds(state, guild, guild_cmds, guild_id)
        del guilds
        for method, guilds in state.items():
            for guild_id, guild in guilds.items():
                for name, kwargs in guild.items():
                    if guild_id is None:
                        path = global_path
                    else:
                        path = guild_path.format(guild_id)
                    if 'id' in kwargs:
                        path += f'/{kwargs.pop("id")}'
                    route = _Route(method, path)
                    asyncio.create_task(self.process_command(
                        name, guild_id, route, kwargs))

    async def sync_cmds(self, state, todo, done, guild_id):
        # todo - registered in code
        # done - registered on API
        done = {data['name']: data for data in done}
        # in the API but not in code
        to_delete = set(done.keys()) - set(todo.keys())
        # in both, filtering done later to see which ones to update
        to_update = set(done.keys()) & set(todo.keys())
        # in code but not in API
        to_create = set(todo.keys()) - set(done.keys())
        for name in to_create:
            state['POST'].setdefault(guild_id, {})[name] \
                = {'json': todo[name].to_dict(), 'cmd': todo[name]}
        for name in to_update:
            cmd_dict = todo[name].to_dict()
            cmd_dict['id'] = done[name]['id']
            cmd_dict['application_id'] = done[name]['application_id']
            if done[name] == cmd_dict:
                logger.debug('GET\t%s\tin guild\t%s', name, guild_id)
                todo[name].id = int(done[name]['id'])
            else:
                state['PATCH'].setdefault(guild_id, {})[name] \
                    = {'json': todo[name].to_dict(), 'id': int(done[name]['id']),
                       'cmd': todo[name]}
        for name in to_delete:
            state['DELETE'].setdefault(guild_id, {})[name] \
                = {'id': int(done[name]['id'])}

    async def process_command(self, name, guild_id, route, kwargs):
        cmd = kwargs.pop('cmd', None)
        try:
            data = await self.http.request(route, **kwargs)
        except discord.HTTPException:
            logger.exception('Error when processing command %s', name)
            return
        if cmd is not None:
            cmd.id = int(data['id'])
        logger.debug('%s\t%s\tin guild\t%s', route.method, name, guild_id)
