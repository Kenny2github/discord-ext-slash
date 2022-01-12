from __future__ import annotations
from typing import Union, Any, Mapping, Optional, Iterable, TYPE_CHECKING
import discord
from discord.ext import commands
from .logger import logger
from .simples import (
    _AsyncInit, _Route, ApplicationCommandOptionType, CallbackFlags,
    InteractionCallbackType, PartialMember, PartialTextChannel,
    PartialCategoryChannel, PartialVoiceChannel, PartialRole
)
if TYPE_CHECKING:
    # these would be circular imports otherwise
    from .command import Command, Group
    from .bot import SlashBot

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
        :type: Union[discord.Member, discord.User]

        The user who ran the command.
        If :attr:`guild` is an :class:`~discord.Object`, a lot of
        :class:`~discord.Member` methods that require the guild will break
        and should not be relied on.
        If :attr:`guild` is :const:`None` then the command was run in DMs
        and this object will be a :class:`~discord.User` instead.
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
    author: Union[discord.Member, PartialMember, discord.User, None]
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
        if event.get('member'):
            author = PartialMember(
                data=event['member'], guild=self.guild,
                state=self.client._connection)
            self.author = await self._try_get(
                author, self._get_member,
                self._fetch_member, 'author-member')
        elif event.get('user'):
            author = discord.User(
                state=self.client._connection, data=event['user'])
            self.author = await self._try_get(
                author, self.client.get_user,
                self.client.fetch_user, 'author-user')
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
                _enum = self.command.options[opt['name']]._enum
                if _enum is not None:
                    value = _enum.__members__[value]
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
        # use duck typing to avoid circular imports
        if hasattr(self.command, 'slash'):
            self.command = self.command.slash[opt['name']]
            await self._kwargs_from_options(opt.get('options', []), resolved)
        else:
            kwargs[self.command._ctx_arg[0]] = self
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
        rtype: InteractionCallbackType = InteractionCallbackType.CHANNEL_MESSAGE_WITH_SOURCE
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
            :attr:`~InteractionCallbackType.DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE`.
            Overrides ``rtype`` unconditionally if :const:`True`.
        :param flags: Message flags, ORed together
        :type flags: Union[CallbackFlags, int]
        :param InteractionCallbackType rtype:
            The type of response to send. See that class's documentation.

        :raises TypeError: if both ``embed`` and ``embeds`` are specified.
        :raises ValueError: if sending channel message without content.
        """
        if deferred:
            rtype = InteractionCallbackType.DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE
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
                           guild_id=self.guild or self.guild.id)
        else:
            data = {
                'type': int(rtype)
            }
            if content or embeds:
                data['data'] = {'content': content}
            elif rtype == InteractionCallbackType.CHANNEL_MESSAGE_WITH_SOURCE:
                raise ValueError('sending channel message with no content')
            if embeds:
                data['data']['embeds'] = embeds
            if mentions is not None:
                data['data']['allowed_mentions'] = mentions.to_dict()
            if ephemeral:
                flags = (flags or 0) | CallbackFlags.EPHEMERAL
            if flags:
                data.setdefault('data', {})['flags'] = int(flags)
            path = f"/interactions/{self.id}/{self.token}/callback"
            route = _Route('POST', path, channel_id=self.channel.id,
                           guild_id=self.guild or self.guild.id)
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
                       guild_id=self.guild or self.guild.id)
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