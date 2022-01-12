from typing import Set, List, Dict, Optional
from warnings import warn
import asyncio
import discord
from discord.ext import commands
from .logger import logger
from .simples import InteractionType, SlashWarning, _Route
from .command import Command, ComponentCallback, Group
from .context import BaseContext, ComponentContext, Context

DEFAULT_TTL = 15*60 # 15 minutes, matches slash command token expiry

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

    .. attribute:: comp_callbacks
        :type: set[ComponentCallback]

        All :class:`ComponentCallback` objects currently registered.

    .. decoratormethod:: slash_cmd(**kwargs)

        Create a :class:`Command` with the decorated coroutine and ``**kwargs``
        and add it to :attr:`slash`.
    .. decoratormethod:: slash_group(**kwargs)

        Create a :class:`Group` with the decorated coroutine and ``**kwargs``
        and add it to :attr:`slash`.

    .. decoratormethod:: component_callback(matcher, ttl, **kwargs)

        Create a :class:`ComponentCallback` with the decorated coroutine
        and ``**kwargs`` and add it to :attr:`comp_callbacks`.

        :param float ttl:
            Wait this long after registering the callback, and then
            deregister it. Default value is 15 minutes. Set to :const:`None`
            to disable autoderegistration, but if doing so make sure to clean
            up the callbacks after you're done using them by calling
            :meth:`ComponentCallback.deregister`.
    """

    slash: Set[Command]
    comp_callbacks: Set[ComponentCallback]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.debug_guild = int(kwargs.pop('debug_guild', 0) or 0) or None
        self.resolve_not_fetch = bool(kwargs.pop('resolve_not_fetch', True))
        self.fetch_if_not_get = bool(kwargs.pop('fetch_if_not_get', False))
        self.slash = set()
        self.comp_callbacks = set()
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
        """Non-decorator version of :meth:`slash_cmd`.

        If ``func`` is a :class:`Command` it will be directly added.
        """
        if isinstance(func, Command):
            self.slash.add(func)
        else:
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
        :class:`BaseCallback` instances.

        :param type cog: The cog to read attributes from.
        """
        for key in dir(cog):
            obj = getattr(cog, key)
            if isinstance(obj, (Group, Command)):
                obj.cog = cog
                if obj.parent is None:
                    self.slash.add(obj)
            elif isinstance(obj, ComponentCallback):
                obj.cog = cog
                self.comp_callbacks.add(obj)

    async def wait_and_deregister(
        self, callback: ComponentCallback, ttl: Optional[float]
    ) -> None:
        if ttl is not None:
            await asyncio.sleep(ttl)
            callback.deregister(self)

    def component_callback(self, matcher, ttl=DEFAULT_TTL, **kwargs):
        def decorator(func):
            callback = ComponentCallback(func, matcher, **kwargs)
            self.comp_callbacks.add(callback)
            asyncio.create_task(self.wait_and_deregister(callback, ttl))
            return callback
        return decorator

    def add_component_callback(self, func, matcher=None, ttl=DEFAULT_TTL, **kwargs):
        """Non-decorator version of :meth:`component_callback`.

        If ``func`` is a :class:`ComponentCallback` it will be directly added.
        """
        if isinstance(func, ComponentCallback):
            self.comp_callbacks.add(func)
            asyncio.create_task(self.wait_and_deregister(func, ttl))
        elif matcher is None:
            raise TypeError('matcher is a required argument '
                            'when not adding a premade callback')
        else:
            self.component_callback(matcher, ttl, **kwargs)(func)

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
        logger.debug('%s', event)
        if event['type'] == InteractionType.APPLICATION_COMMAND:
            await self.handle_slash_command(event)
        elif event['type'] == InteractionType.MESSAGE_COMPONENT:
            await self.handle_component_interaction(event)

    async def do_invoke(self, ctx: BaseContext, event_name: str):
        self.dispatch(f'before_{event_name}_invoke', ctx)
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
        else:
            self.dispatch(f'after_{event_name}_invoke', ctx)

    async def handle_slash_command(self, event: dict):
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
        ctx: Context = await cmd._ctx_arg[1](self, cmd, event)
        await self.do_invoke(ctx, 'slash_command')

    async def handle_component_interaction(self, event: dict):
        ctx: ComponentContext = await ComponentContext(self, None, event)
        for c in self.comp_callbacks:
            ctx.command = c
            if await c.matcher(ctx):
                break
        else:
            raise commands.CommandNotFound(
                f'No command found matching {ctx!r}')
        await self.do_invoke(ctx, 'component_callback')

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
                todo[name].id = int(done[name]['id'])
                logger.debug('GET\t%s\t%s\tin guild\t%s', name, todo[name].id, guild_id)
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
        all_guild_ids = {g.id for g in self.guilds} | {cmd.guild_id for cmd in self.slash}
        all_guild_ids.discard(None)
        guilds: Dict[int, List[dict]] = {}
        for cmd in self.slash:
            defaults = cmd.perms_dict(None)
            if defaults['permissions']:
                # don't set defaults in all guilds if the command itself
                # is limited to only one guild
                guild_ids = all_guild_ids if cmd.guild_id is None else {cmd.guild_id}
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
            logger.debug('PUT\tpermissions for all commands\tin guild\t%s', guild_id)
            await self.http.request(route, json=data)
