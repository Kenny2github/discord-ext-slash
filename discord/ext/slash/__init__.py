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
* All descriptions are **required**.
* You must grant the bot ``applications.commands`` permissions in the OAuth2 section of the developer dashboard.

See the `docs <https://discord-ext-slash.rtfd.io>`_.
'''
from __future__ import annotations
import sys
from warnings import warn
from enum import IntEnum, IntFlag
from typing import Coroutine, Dict, Iterable, Set, Tuple, Union, Optional, Mapping, Any, List
from functools import partial
from inspect import signature
import logging
import asyncio
import discord
from discord.ext import commands

__all__ = [
    'SlashWarning',
    'ApplicationCommandOptionType',
    'ApplicationCommandPermissionType',
    'InteractionResponseType',
    'CallbackFlags',
    'Context',
    'Interaction',
    'Option',
    'Choice',
    'CommandPermissionsDict',
    'Command',
    'Group',
    'cmd',
    'group',
    'permit',
    'SlashBot'
]

__version__ = '0.8.0'

class SlashWarning(UserWarning):
    """:mod:`discord.ext.slash`-specific warning type."""

class ApplicationCommandOptionType(IntEnum):
    """Possible :class:`Command` :class:`Option` types.
    Default is :attr:`STRING`.

    .. attribute:: SUB_COMMAND

        Marks a sub-:class:`Command`, only used internally.
    .. attribute:: SUB_COMMAND_GROUP

        Marks a :class:`Group`, only used internally.

    The type signatures of the below attributes mark the type
    that the argument value is passed as. For example, options
    of type :attr:`STRING` are passed as :class:`str`.

    .. attribute:: STRING
        :type: str
    .. attribute:: INTEGER
        :type: int
    .. attribute:: BOOLEAN
        :type: bool
    .. attribute:: USER
        :type: Union[discord.Member, discord.User,
            PartialMember, discord.Object]
    .. attribute:: CHANNEL
        :type: Union[discord.TextChannel, discord.CategoryChannel,
            discord.VoiceChannel, PartialTextChannel, PartialCategoryChannel,
            PartialVoiceChannel, discord.Object]
    .. attribute:: ROLE
        :type: Union[discord.Role, PartialRole, discord.Object]
    .. attribute:: MENTIONABLE
        :type: Union[discord.Member, discord.User, PartialMember,
            discord.Role, PartialRole, discord.Object]
    .. attribute:: NUMBER
        :type: float
    """
    SUB_COMMAND = 1
    SUB_COMMAND_GROUP = 2
    STRING = 3
    INTEGER = 4
    BOOLEAN = 5
    USER = 6
    CHANNEL = 7
    ROLE = 8
    MENTIONABLE = 9
    NUMBER = 10

class ApplicationCommandPermissionType(IntEnum):
    """Possible types of permission grants.
    For use in :meth:`Command.add_perm` and :func:`permit`.

    .. attribute:: ROLE

        Specifies that this permission grant is to a role.
    .. attribute:: USER

        Specifies that this permission grant is to a user.
    """
    ROLE = 1
    USER = 2

class InteractionResponseType(IntEnum):
    """Possible ways to respond to an interaction.
    For use in :meth:`Context.respond`.

    .. attribute:: PONG

        Only used to ACK a Ping, never valid here.
        Included only for completeness.
    .. attribute:: CHANNEL_MESSAGE_WITH_SOURCE

        Show user input and send a message. Default.
    .. attribute:: DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE

        Show user input and display a "waiting for bot" system message.
        Send a response with this type and edit the response later if you
        need to do some asynchronous fetch or something.
    """
    # ACK a Ping
    Pong = PONG = 1
    # Respond immediately to an interaction
    CHANNEL_MESSAGE_WITH_SOURCE = ChannelMessageWithSource = 4
    # ACK an interaction and send a response later
    DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE = DeferredChannelMessageWithSource = 5
    # ACK a command without sending a message, showing the user's input
    # (Former name and description, now renamed)
    AcknowledgeWithSource = DeferredChannelMessageWithSource

class CallbackFlags(IntFlag):
    """Flags to pass to the ``flags`` argument of :meth:`Context.respond`.

    .. attribute:: EPHEMERAL

        Only the user receiving the message can see it
    """
    EPHEMERAL = 1 << 6

MessageFlags = CallbackFlags

class _Route(discord.http.Route):
    BASE = 'https://discord.com/api/v8'

class _AsyncInit:
    async def __new__(cls, *args, **kwargs):
        inst = super().__new__(cls)
        await inst.__init__(*args, **kwargs)
        return inst

    async def __init__(self):
        pass

class PartialObject(discord.Object):
    """Subclasses of this have their .:attr:`guild` as a
    :class:`~discord.Object`, so their guild-related functionality may break.

    .. attribute:: guild
        :type: discord.Object
    """
    guild: discord.Object

class PartialTextChannel(discord.TextChannel, PartialObject):
    """A partial :class:`~discord.TextChannel`."""
    pass

class PartialCategoryChannel(discord.CategoryChannel, PartialObject):
    """A partial :class:`~discord.CategoryChannel`."""
    pass

class PartialVoiceChannel(discord.VoiceChannel, PartialObject):
    """A partial :class:`~discord.VoiceChannel`."""
    pass

class PartialMember(discord.Member, PartialObject):
    """A partial :class:`~discord.Member`."""
    pass

class PartialRole(discord.Role, PartialObject):
    """A partial :class:`~discord.Role`."""
    pass

class Context(discord.Object, _AsyncInit):
    """Object representing an interaction.

    .. attribute:: id
        :type: int

        The interaction ID.
    .. attribute:: guild
        :type: Union[discord.Guild, discord.Object]

        The guild where the interaction took place.
        Can be an :class:`~discord.Object` with just the ID
        if the client is not in the guild.
    .. attribute:: channel
        :type: Union[discord.TextChannel, discord.Object]

        The channel where the command was run.
        Can be an :class:`~discord.Object` with just the ID
        if the client is not in the guild.
    .. attribute:: author
        :type: discord.Member

        The user who ran the command.
        If :attr:`guild` is an :class:`~discord.Object`, a lot of
        :class:`~discord.Member` methods that require the guild will break
        and should not be relied on.
    .. attribute:: command
        :type: Command

        The command that was run.
    .. attribute:: options
        :type: Mapping[str, Any]

        The options passed to the command (including this context).
        More useful in groups and checks.
    .. attribute:: me
        :type: Optional[discord.Member]

        The bot, as a :class:`~discord.Member` in that context.
        Can be :const:`None` if the client is not in the guild.
    .. attribute:: client
        :type: SlashBot

        The bot.
    .. attribute:: webhook
        :type: Optional[discord.Webhook]

        Webhook used for sending followup messages.
        :const:`None` until interaction response has been sent
    """

    id: int
    guild: Union[discord.Guild, discord.Object, None]
    channel: Union[discord.TextChannel, discord.Object]
    author: Union[discord.Member, PartialMember, None]
    command: Union[Command, Group]
    options: Mapping[str, Any]
    me: Union[discord.Member, discord.Object]
    client: SlashBot
    webhook: Optional[discord.Webhook]

    @property
    def bot(self) -> SlashBot:
        """The bot. Alias for :attr:`client`."""
        return self.client

    @bot.setter
    def bot(self, value: SlashBot):
        """The bot. Alias for :attr:`client`."""
        self.client = value

    async def __init__(self, client: SlashBot, cmd: Command, event: dict):
        self.client = client
        self.command = cmd
        self.id = int(event['id'])
        if event.get('guild_id', None):
            self.guild = await self._try_get(
                discord.Object(event['guild_id']), self.client.get_guild,
                self.client.fetch_guild, 'guild')
        else:
            self.guild = None
        self.channel = await self._try_get(
            discord.Object(event['channel_id']), self.client.get_channel,
            self.client.fetch_channel, 'channel')
        if event.get('member', None):
            author = PartialMember(
                data=event['member'], guild=self.guild,
                state=self.client._connection)
            self.author = await self._try_get(
                author, self._get_member,
                self._fetch_member, 'author-member')
        else:
            self.author = None
        self.token = event['token']
        # construct options into function-friendly form
        await self._kwargs_from_options(
            event['data'].get('options', []),
            event['data'].get('resolved', {
                'members': {}, 'users': {},
                'channels': {}, 'roles': {}
            })
        )
        self.me = await self._try_get(
            discord.Object(self.client.user.id), self._get_member,
            self._fetch_member, 'me-member')
        self.webhook = None

    async def _kwargs_from_options(self, options, resolved):
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
                try:
                    opttype = ApplicationCommandOptionType(opttype)
                except ValueError:
                    pass # just use the new int
                if opttype in {
                    ApplicationCommandOptionType.USER,
                    ApplicationCommandOptionType.CHANNEL,
                    ApplicationCommandOptionType.ROLE,
                    ApplicationCommandOptionType.MENTIONABLE,
                }:
                    value = discord.Object(value)
                if opttype == ApplicationCommandOptionType.USER:
                    value = await self._try_get_user(value, resolved)
                elif opttype == ApplicationCommandOptionType.CHANNEL:
                    value = await self._try_get_channel(value, resolved)
                elif opttype == ApplicationCommandOptionType.ROLE:
                    value = await self._try_get_role(value, resolved)
                elif opttype == ApplicationCommandOptionType.MENTIONABLE:
                    # mention less people by default, though no two objects
                    # should have the same snowflake ID anyway
                    value = await self._try_get_user(value, resolved, False)
                    if type(value) is discord.Object:
                        value = await self._try_get_role(value, resolved)
                kwargs[opt['name']] = value
            elif 'options' in opt:
                self.command = self.command.slash[opt['name']]
                await self._kwargs_from_options(opt['options'], resolved)
                return
        if isinstance(self.command, Group):
            self.command = self.command.slash[opt['name']]
            await self._kwargs_from_options(opt.get('options', []), resolved)
        elif isinstance(self.command, Command):
            kwargs[self.command._ctx_arg] = self
            self.options = kwargs

    async def _try_get(
        self, default, get_method, fetch_method, typename, *,
        resolve_method=None, resolved=None, fng=None, fq=None
    ):
        fq = (not self.client.resolve_not_fetch) if fq is None else fq
        fng = self.client.fetch_if_not_get if fng is None else fng
        # always try to get *something*
        if fq or resolved is None \
                or str(default.id) not in resolved[typename+'s']:
            try:
                obj = get_method(default.id)
                if obj is None and fng:
                    logger.debug(
                        'Getting %s %s for interaction %s failed, '
                        'falling back to fetching',
                        typename, default.id, self.id)
                    obj = await fetch_method(default.id)
                elif not fng:
                    raise ValueError
                else:
                    logger.debug(
                        'Got %s %s for interaction %s',
                        typename, obj.id, self.id)
                    return obj
            except discord.HTTPException:
                logger.debug(
                    'Fetching %s %s for interaction %s failed%s',
                    typename, default.id, self.id,
                    ', falling back to resolving'
                    if resolved
                    else ', falling back on default')
            except (AttributeError, ValueError):
                logger.debug(
                    'Getting %s %s for interaction %s failed%s',
                    typename, default.id, self.id,
                    ', falling back to resolving'
                    if resolved
                    else ', falling back on default')
            else:
                logger.debug(
                    'Fetched %s %s for interaction %s',
                    typename, obj.id, self.id)
                return obj
        if resolved is None:
            return default
        obj = resolved[typename+'s'].get(str(default.id), None)
        if obj is None:
            logger.debug(
                'Resolving %s %s for interaction %s failed',
                typename, default.id, self.id)
            return default
        logger.debug(
            'Resolved %s %s for interaction %s',
            typename, default.id, self.id)
        return resolve_method(obj)

    async def _try_get_user(
        self, value: discord.Object,
        resolved: dict, try_user: bool = True
    ):
        def resolve_member(member):
            member['user'] = resolved['users'][str(value.id)]
            return PartialMember(
                data=member, guild=self.guild,
                state=self.client._connection)
        def resolve_user(user):
            return discord.User(
                state=self.client._connection, data=user)
        value = await self._try_get(
            value, self._get_member, self._fetch_member, 'member',
            resolve_method=resolve_member, resolved=resolved)
        if type(value) is discord.Object and try_user:
            value = await self._try_get(
                value, None, None, 'user', fq=False,
                resolve_method=resolve_user, resolved=resolved)
        return value

    async def _try_get_channel(self, value: discord.Object, resolved: dict):
        def get_channel(oid):
            return self.guild.get_channel(oid)
        def resolve_channel(channel):
            # discord.py doesn't access this with a default,
            # but it seems like the resolved object doesn't
            # provide it either, so set it if not set.
            # Also can't use None here because position is
            # used as a sort key too.
            channel.setdefault('position', -1)
            ctype = channel['type']
            ctype, _ = discord.channel._channel_factory(ctype)
            if ctype is discord.TextChannel:
                ctype = PartialTextChannel
            elif ctype is discord.CategoryChannel:
                ctype = PartialCategoryChannel
            elif ctype is discord.VoiceChannel:
                ctype = PartialVoiceChannel
            return ctype(state=self.client._connection,
                            guild=self.guild, data=channel)
        return await self._try_get(
            value, get_channel, self.client.fetch_channel, 'channel',
            resolve_method=resolve_channel, resolved=resolved)

    async def _try_get_role(self, value: discord.Object, resolved: dict):
        def get_role(oid):
            return self.guild.get_role(oid)
        def resolve_role(role):
            # monkeypatch for discord.py
            role['permissions_new'] = role['permissions']
            return PartialRole(state=self.client._connection,
                                guild=self.guild, data=role)
        return await self._try_get(
            value, get_role, None, 'role', fng=False,
            resolve_method=resolve_role, resolved=resolved)

    def _get_member(self, mid):
        return self.guild.get_member(mid)

    async def _fetch_member(self, mid):
        return await self.guild.fetch_member(mid)

    def __repr__(self):
        return f'<Interaction id={self.id}>'

    async def respond(
        self, content='', *, embed: discord.Embed = None,
        embeds: Iterable[discord.Embed] = None,
        allowed_mentions: discord.AllowedMentions = None,
        file: discord.File = None, ephemeral: bool = False,
        deferred: bool = False, flags: Union[CallbackFlags, int] = None,
        rtype: InteractionResponseType = InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE
    ):
        """Respond to the interaction. If called again, edits the response.

        :param str content: The content of the message.
        :param discord.Embed embed: Shorthand for ``respond(embeds=[embed])``
        :param embeds: Up to 10 embeds (any more will be silently discarded)
        :type embeds: Iterable[discord.Embed]
        :param discord.AllowedMentions allowed_mentions:
            Mirrors normal ``allowed_mentions`` in
            :meth:`~discord.abc.Messageable.send`
        :param discord.File file:
            Mirrors normal ``file`` in :meth:`~discord.abc.Messageable.send`
        :param bool ephemeral:
            Shortcut to setting ``flags |=`` :attr:`CallbackFlags.EPHEMERAL`.
            If other flags are present, they are preserved.
        :param bool deferred:
            Shortcut to setting ``rtype =``
            :attr:`~InteractionResponseType.DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE`.
            Overrides ``rtype`` unconditionally if :const:`True`.
        :param flags: Message flags, ORed together
        :type flags: Union[CallbackFlags, int]
        :param InteractionResponseType rtype:
            The type of response to send. See that class's documentation.

        :raises TypeError: if both ``embed`` and ``embeds`` are specified.
        :raises ValueError: if sending channel message without content.
        """
        if deferred:
            rtype = InteractionResponseType.DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE
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
            elif rtype == InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE:
                raise ValueError('sending channel message with no content')
            if embeds:
                data['data']['embeds'] = embeds
            if mentions is not None:
                data['data']['allowed_mentions'] = mentions.to_dict()
            if ephemeral:
                flags = (flags or 0) | MessageFlags.EPHEMERAL
            if flags:
                data.setdefault('data', {})['flags'] = int(flags)
            path = f"/interactions/{self.id}/{self.token}/callback"
            route = _Route('POST', path, channel_id=self.channel.id,
                           guild_id=self.guild.id)
            self.webhook = discord.Webhook.partial(
                id=self.client.app_info.id, token=self.token, adapter=
                discord.AsyncWebhookAdapter(self.client.http._HTTPClient__session))
        if isinstance(file, discord.File):
            form = []
            form.append({'name': 'payload_json',
                         'value': discord.utils.to_json(data)})
            form.append({
                'name': 'file',
                'value': file.fp,
                'filename': file.filename,
                'content_type': 'application/octet-stream'
            })
            await self.client.http.request(route, form=form, files=[file])
        else:
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
        Equivalent to :meth:`~discord.TextChannel.send`
        for :attr:`Context.channel`.

        Only method that works after the interaction token has expired.
        Only works if client is present there as a bot user too.
        """
        return await self.channel.send(*args, **kwargs)

Interaction = Context

class Option:
    """An argument to a :class:`Command`.
    This must be passed as an annotation to the corresponding argument.

    Constructor arguments map directly to attributes, besides the one below
    which has a different type signature:

    :param choices:
        Strings are converted into :class:`Choice` objects with the same
        ``name`` and ``value``. :class:`dict` objects are passed as kwargs to
        the :class:`Choice` constructor.
    :type choices: Optional[Iterable[Union[str, Mapping[str, str], Choice]]]

    .. attribute:: description
        :type: str

        The description of the option, displayed to users.
    .. attribute:: type
        :type: ApplicationCommandOptionType
        :value: :attr:`ApplicationCommandOptionType.STRING`

        The argument type.
    .. attribute:: name
        :type: Optional[str]
        :value: None

        The name of the option, if different from its argument name.
    .. attribute:: required
        :type: bool
        :value: False

        If :const:`True`, this option must be specified for a valid command
        invocation.
    .. attribute:: choices
        :type: Optional[list[Choice]]

        Only these values are allowed for this option.
    """
    description: str
    type: ApplicationCommandOptionType = ApplicationCommandOptionType.STRING
    name: Optional[str] = None
    required: Optional[bool] = False
    choices: Optional[List[Choice]] = None

    def __init__(
        self, description: str,
        type: ApplicationCommandOptionType = ApplicationCommandOptionType.STRING,
        **kwargs
    ):
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

    Constructor arguments map directly to attributes.

    .. attribute:: name
        :type: str

        The description of the choice, displayed to users.
    .. attribute:: value
        :type: str

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

CommandPermissionsDict = Dict[Optional[int], Dict[Tuple[
    int, ApplicationCommandPermissionType], bool]]

class Command(discord.Object):
    """Represents a slash command.

    The following constructor argument does not map to an attribute:

    :param Coroutine check:
        A coroutine to run before calling the command.
        If it returns :const:`False` (not falsy, :const:`False`),
        then the command is not run.

    The following attributes are set by constructor arguments:

    .. attribute:: coro
        :type: Coroutine

        (Required) Original callback for the command.
    .. attribute:: id
        :type: Optional[int]

        ID of registered command. Can be None when not yet registered,
        or if not a top-level command.
    .. attribute:: name
        :type: str

        Command name. Defaults to :attr:`coro` ``.__name__``.
    .. attribute:: description
        :type: str

        Description shown in command list. Default :attr:`coro` ``.__doc__``.
    .. attribute:: guild_id
        :type: Optional[int]
        :value: None

        If present, this command only exists in this guild.
    .. attribute:: parent
        :type: Optional[Group]
        :value: None

        Parent (sub)command group.
    .. attribute:: default_permission
        :type: bool
        :value: True

        If :const:`False`, this command is disabled by default
        when the bot is added to a new guild. It must be re-enabled per user
        or role using permissions.

    :raises TypeError:
        if ``coro`` has a required argument (other than ``self``)
        without an annotation.
    :raises ValueError:
        if no ``description`` is specified and ``coro`` has no docstring.
    :raises ValueError:
        if no arguments to ``coro`` are annotated with
        :class:`Context` or a subclass.

    The following attributes are *not* set by constructor arguments:

    .. attribute:: options
        :type: Mapping[str, Option]

        Options for this command. Set by inspecting the function annotations.
    .. attribute:: permissions
        :type: CommandPermissionsDict

        Permission overrides for this command. A dict of guild IDs to dicts of:
        role or user or member objects (partial or real) to boolean
        enable/disable values to grant/deny permissions.
    .. attribute:: default
        :type: bool
        :value: False

        If :const:`True`, invoking the base parent of this command translates
        into invoking this subcommand. (Not settable in arguments.)

    .. decoratormethod:: check

        Set this command's check to this coroutine.
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
    default_permission: bool = True
    permissions: CommandPermissionsDict

    def __init__(self, coro: Coroutine, **kwargs):
        self.id = None
        self.name = kwargs.pop('name', coro.__name__)
        self.description = kwargs.pop('description', coro.__doc__)
        if not self.description:
            raise ValueError(f'Please specify a description for {self.name!r}')
        self.guild_id = kwargs.pop('guild_id', kwargs.pop('guild', None))
        if self.guild_id is not None:
            self.guild_id = int(self.guild_id)
        self.parent = kwargs.pop('parent', None)
        self.default_permission = kwargs.pop('default_permission', True)
        self.permissions = {}
        self._ctx_arg = None
        self.options = {}
        found_self_arg = False
        for param in signature(coro).parameters.values():
            typ = param.annotation
            if isinstance(typ, str):
                try:
                    # evaluate the annotation in its module's context
                    globs = sys.modules[coro.__module__].__dict__
                    typ = eval(typ, globs)
                except:
                    typ = param.empty
            if (
                not (isinstance(typ, Option) or (
                    isinstance(typ, type) and issubclass(typ, Context)
                ))
                and param.default is param.empty
            ):
                if not found_self_arg:
                    # assume that the first required non-annotated argument
                    # is the self argument to a class' method
                    found_self_arg = True
                    continue
                else:
                    raise TypeError(
                        f'Command {self.name!r} cannot have a '
                        'required argument with no valid annotation')
            try:
                if issubclass(typ, Context):
                    self._ctx_arg = param.name
            except TypeError: # not even a class
                pass
            if isinstance(typ, Option):
                typ = typ.clone()
                if param.default is param.empty:
                    typ.required = True
                self.options[param.name] = typ
                if typ.name is None:
                    typ.name = param.name
        if self._ctx_arg is None:
            raise ValueError('One argument must be type-hinted slash.Context')
        self.coro = coro
        async def check(*args, **kwargs):
            pass
        self._check = kwargs.pop('check', check)

    @property
    def qualname(self) -> str:
        """Fully qualified name of command, including group names."""
        if self.parent is None:
            return self.name
        return self.parent.qualname + ' ' + self.name

    def __str__(self):
        return self.qualname

    def __hash__(self):
        return hash((self.name, self.guild_id))

    def _to_dict_common(self, data: dict):
        if self.parent is None:
            data['default_permission'] = self.default_permission

    def to_dict(self):
        data = {
            'name': self.name,
            'description': self.description
        }
        if self.options:
            data['options'] = [opt.to_dict() for opt in self.options.values()]
        self._to_dict_common(data)
        return data

    def perms_dict(self, guild_id: Optional[int]):
        perms = []
        final = self.permissions.get(None, {}).copy()
        final.update(self.permissions.get(guild_id, {}).items())
        for (oid, type), perm in final.items():
            perms.append({
                'id': oid,
                'type': type.value,
                'permission': perm
            })
        return {'id': self.id, 'permissions': perms}

    def add_perm(
        self, target: Union[discord.Role, discord.abc.User, discord.Object],
        perm: bool, guild_id: Optional[int] = ...,
        type: ApplicationCommandPermissionType = None
    ):
        """Add a permission override.

        :param target: The role or user to assign this permission to.
        :type target: Union[discord.Role, PartialRole, discord.Member,
            discord.User, PartialMember, discord.Object]
        :param bool perm:
            :const:`True` to grant permission, :const:`False` to deny it
        :param guild_id:
            The guild ID to set the permission for, or :const:`None` to apply
            this to the defaults that all guilds inherit for this command.
            If specified, overrides ``target.guild.id``.
            Must be specified if ``target`` is a :class:`~discord.Object` or
            a guildless :class:`~discord.User`.
        :type guild_id: Optional[int]
        :param ApplicationCommandPermissionType type:
            The type of permission grant this is,
            :attr:`~ApplicationCommandPermissionType.ROLE` or
            :attr:`~ApplicationCommandPermissionType.USER`.
            Must be specified if ``target`` is a :class:`~discord.Object`.

        Generally there are four ways of calling this:

        * ``add_perm(target, perm)`` will infer ``guild_id`` and ``type``
          from ``target.guild.id`` and the type of ``target`` (respectively).
        * ``add_perm(target, perm, guild_id)`` will infer the type, but
          manually set the guild ID (e.g. with a :class:`~discord.User` and
          not a :class:`~discord.Member`).
        * ``add_perm(discord.Object(id), perm, guild_id, type)`` will manually
          set the guild ID and type since all you have is an ID.
        * ``add_perm(..., guild_id=None)`` will do any of the above but apply
          the permissions to the defaults that all specific-guild permissions
          will inherit from, instead of applying to any particular guild.

        :raises ValueError: if ``type`` is unspecified but cannot be inferred.
        :raises ValueError:
            if ``guild_id`` is unspecified but cannot be inferred.
        """
        if type is None:
            if isinstance(target, discord.Role):
                type = ApplicationCommandPermissionType.ROLE
            elif isinstance(target, discord.abc.User):
                type = ApplicationCommandPermissionType.USER
            else:
                raise ValueError(
                    'Must specify type if target is not a discord.py model')
        if guild_id is ...:
            if isinstance(target, (discord.Role, discord.Member)):
                guild_id = target.guild.id
            else:
                raise ValueError(
                    'Must specify guild_id if target is not a guilded object')
        self.permissions.setdefault(guild_id, {})[target.id, type] = perm

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
        self._check = coro
        return coro

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
    Attributes and constructor arguments are the same as :class:`Command`
    unless documented below.

    :param Coroutine coro:
        (Required) Callback invoked when a subcommand of this group is called.
        (This is not a check! Register a check using :meth:`~Command.check`.)

    .. attribute:: slash
        :type: Mapping[str, Union[Group, Command]]

        Subcommands of this group.

    .. decoratormethod:: slash_cmd(**kwargs)

        See :meth:`SlashBot.slash_cmd`.
    .. decoratormethod:: slash_group(**kwargs)

        See :meth:`SlashBot.slash_group`.
    """
    cog = None
    slash: Mapping[str, Union[Group, Command]]

    def __init__(self, coro: Coroutine, **kwargs):
        super().__init__(coro, **kwargs)
        self.slash = {}

    def slash_cmd(self, **kwargs):
        kwargs['parent'] = self
        def decorator(func):
            cmd = Command(func, **kwargs)
            cmd.cog = self.cog
            self.slash[cmd.name] = cmd
            return cmd
        return decorator

    def add_slash(self, func, **kwargs):
        """See :meth:`SlashBot.add_slash`."""
        self.slash_cmd(**kwargs)(func)

    def slash_group(self, **kwargs):
        kwargs['parent'] = self
        def decorator(func):
            group = Group(func, **kwargs)
            group.cog = self.cog
            self.slash[group.name] = group
            return group
        return decorator

    def add_slash_group(self, func, **kwargs):
        """See :meth:`SlashBot.add_slash_group`."""
        self.slash_group(**kwargs)(func)

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
        self._to_dict_common(data)
        return data

def cmd(**kwargs):
    """Decorator that transforms a function into a :class:`Command`."""
    def decorator(func):
        return Command(func, **kwargs)
    return decorator

def group(**kwargs):
    """Decorator that transforms a function into a :class:`Group`."""
    def decorator(func):
        return Group(func, **kwargs)
    return decorator

def permit(
    target: Union[discord.Role, discord.abc.User, discord.Object],
    perm: bool, guild_id: Optional[int] = ...,
    type: ApplicationCommandPermissionType = None
):
    """Decorator **on top of a command** that adds a permissions overwrite."""
    def decorator(func: Command):
        func.add_perm(target, perm, guild_id, type)
        return func
    return decorator

logger = logging.getLogger('discord.ext.slash')
logger.setLevel(logging.INFO)

class SlashBot(commands.Bot):
    """A bot that supports slash commands.

    Constructor arguments in addition to those provided to
    :class:`discord.ext.commands.Bot` are as follows:

    :param int debug_guild:
        While testing your bot, it may be useful to have instant command
        updates for global commands. Setting this to a guild ID will redirect
        all global commands to commands specific to that guild. Once in
        production, set this to :const:`None` or do not set it at all.
    :param bool resolve_not_fetch:
        If :const:`True` (the default), Discord objects passed in arguments
        will be resolved from the slash commands API, not retrieved or fetched.
    :param bool fetch_if_not_get:
        If :const:`False` (the default), Discord objects passed in arguments
        will not be fetched from the API if retrieving them from cache fails.

    .. attribute:: app_info
        :type: discord.AppInfo

        Cached output of :meth:`application_info`.
        Might not be present until :func:`on_ready` has fired at least once.
    .. attribute:: slash
        :type: set[Command]

        All top-level :class:`Command` and :class:`Group` objects currently
        registered **in code**.

    .. decoratormethod:: slash_cmd(**kwargs)

        Create a :class:`Command` with the decorated coroutine and ``**kwargs``
        and add it to :attr:`slash`.
    .. decoratormethod:: slash_group(**kwargs)

        Create a :class:`Group` with the decorated coroutine and ``**kwargs``
        and add it to :attr:`slash`.
    """

    slash: Set[Command]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.debug_guild = int(kwargs.pop('debug_guild', 0) or 0) or None
        self.resolve_not_fetch = bool(kwargs.pop('resolve_not_fetch', True))
        self.fetch_if_not_get = bool(kwargs.pop('fetch_if_not_get', False))
        self.slash = set()
        @self.listen()
        async def on_ready():
            self.remove_listener(on_ready)
            # only start listening to interaction-create once ready
            self._connection.parsers.setdefault('INTERACTION_CREATE', lambda data: (
                self._connection.dispatch('interaction_create', data)))
            try:
                await self.register_commands()
                self._connection.dispatch('slash_permissions')
            except discord.HTTPException:
                logger.exception('Registering commands failed')
                asyncio.create_task(self.close())
                raise

    def slash_cmd(self, **kwargs):
        def decorator(func):
            cmd = Command(func, **kwargs)
            self.slash.add(cmd)
            return cmd
        return decorator

    def add_slash(self, func, **kwargs):
        """Non-decorator version of :meth:`slash_cmd`."""
        self.slash_cmd(**kwargs)(func)

    def slash_group(self, **kwargs):
        def decorator(func):
            group = Group(func, **kwargs)
            self.slash.add(group)
            return group
        return decorator

    def add_slash_group(self, func, **kwargs):
        """Non-decorator version of :meth:`slash_group`."""
        self.slash_group(**kwargs)(func)

    def add_slash_cog(self, cog: type):
        """Add all attributes of ``cog`` that are
        :class:`Command` or :class:`Group` instances.

        :param type cog: The cog to read attributes from.
        """
        for key in dir(cog):
            obj = getattr(cog, key)
            if isinstance(obj, (Group, Command)):
                obj.cog = cog
                if obj.parent is None:
                    self.slash.add(obj)

    async def application_info(self):
        """Equivalent to :meth:`discord.Client.application_info`, but
        caches its output in :attr:`app_info`.
        """
        self.app_info = await super().application_info()
        return self.app_info

    async def on_interaction_create(self, event: dict):
        if event['version'] != 1:
            raise RuntimeError(
                f'Interaction data version {event["version"]} is not supported'
                ', please open an issue for this: '
                'https://github.com/Kenny2github/discord-ext-slash/issues/new')
        cmd = discord.utils.get(self.slash, id=int(event['data']['id']))
        if cmd is None:
            warn(f'No command {event["data"]["name"]!r} found '
                 f'by ID {event["data"]["id"]}, falling back to '
                 'name + guild search', SlashWarning)
            cmd = discord.utils.get(
                self.slash, name=event['data']['name'],
                guild_id=int(event['guild_id'] or 0) or None)
        if cmd is None:
            warn(f'No command {event["data"]["name"]!r} found '
                 f'by name and guild ID {event["guild_id"]!r}, '
                 'falling back to name-only search', SlashWarning)
            cmd = discord.utils.get(
                self.slash, name=event['data']['name'])
        if cmd is None:
            raise commands.CommandNotFound(
                f'No command {event["data"]["name"]!r} found by any critera')
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

    async def on_slash_permissions(self):
        await self.register_permissions()

    async def register_commands(self, guild_id: int = None):
        """Update commands on the API.

        :param int guild_id:
            Only update commands specific to this guild.
        """
        app_info = await self.application_info()
        global_path = f"/applications/{app_info.id}/commands"
        guild_path = f"/applications/{app_info.id}/guilds/{{0}}/commands"
        guilds = {g.id: {} for g in self.guilds if guild_id in {g.id, None}}
        for cmd in self.slash:
            cmd.guild_id = cmd.guild_id or self.debug_guild
            if guild_id and cmd.guild_id != guild_id:
                continue
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
        tasks: List[asyncio.Task] = []
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
                    task = asyncio.create_task(self.process_command(
                        name, guild_id, route, kwargs))
                    tasks.append(task)
        await asyncio.gather(*tasks)

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
            up_to_date = all(done[name].get(k, ...) == cmd_dict.get(k, ...)
                             for k in {'name', 'description',
                                       'options', 'default_permission'})
            if up_to_date:
                logger.debug('GET\t%s\tin guild\t%s', name, guild_id)
                todo[name].id = int(done[name]['id'])
            else:
                cmd_dict.pop('name') # can't pass this to PATCH
                state['PATCH'].setdefault(guild_id, {})[name] \
                    = {'json': cmd_dict, 'id': int(done[name]['id']),
                       'cmd': todo[name]}
        for name in to_delete:
            state['DELETE'].setdefault(guild_id, {})[name] \
                = {'id': int(done[name]['id'])}

    async def process_command(self, name, guild_id, route, kwargs):
        cmd = kwargs.pop('cmd', None)
        try:
            data = await self.http.request(route, **kwargs)
        except discord.HTTPException:
            logger.exception('Error when processing command %s:', name)
            return
        finally:
            logger.debug('%s\t%s\tin guild\t%s', route.method, name, guild_id)
        if cmd is not None:
            cmd.id = int(data['id'])

    async def register_permissions(self, guild_id: int = None):
        """Update command permissions on the API.

        :param int guild_id:
            Only update permissions for this guild. Note: All commands
            will still be updated, but only permissions related to this
            guild will be updated.
        """
        try:
            await self._register_permissions(guild_id)
        except discord.HTTPException:
            logger.exception('Registering command permissions failed')
            asyncio.create_task(self.close())
            raise

    async def _register_permissions(self, guild_id: int = None):
        app_info = self.app_info
        guild_path = f"/applications/{app_info.id}/guilds/{{0}}/commands/permissions"
        guild_ids = {g.id for g in self.guilds} | {cmd.guild_id for cmd in self.slash}
        guild_ids.discard(None)
        guilds: Dict[int, List[dict]] = {}
        for cmd in self.slash:
            defaults = cmd.perms_dict(None)
            if defaults['permissions']:
                for gid in guild_ids:
                    # This is only for guilds that have no specific perms.
                    # Guilds that do have specific perms will have the default
                    # perms included in (and updated by) the specific ones.
                    # So if the guild from the overall list has specific perm
                    # overrides, skip it here.
                    if guild_id not in {gid, None} or gid in cmd.permissions:
                        continue
                    guilds.setdefault(gid, []).append(defaults)
            for gid in cmd.permissions:
                if gid is None:
                    continue # don't actually pass None into the API
                if guild_id not in {gid, None}:
                    continue
                guilds.setdefault(gid, []).append(cmd.perms_dict(gid))
        for guild_id, data in guilds.items():
            route = _Route('PUT', guild_path.format(guild_id))
            await self.http.request(route, json=data)
            logger.debug('PUT guild\t%s\tpermissions', guild_id)
