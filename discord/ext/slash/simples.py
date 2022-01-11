from enum import Enum, IntEnum, IntFlag
import discord

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

class InteractionType(IntEnum):
    """Possible types of interaction.

    .. attribute:: PING

        Only used in webhook-based interactions.
        Included only for completeness.
    .. attribute:: APPLICATION_COMMAND

        A :class:`Command` interaction.
    .. attribute:: MESSAGE_COMPONENT

        An interaction from a :class:`Button` or :class:`SelectMenu`.
    .. attribute:: APPLICATION_COMMAND_AUTOCOMPLETE

        An interaction for autocompleting :class:`Option` values.
    """
    PING = 1
    APPLICATION_COMMAND = 2
    MESSAGE_COMPONENT = 3
    APPLICATION_COMMAND_AUTOCOMPLETE = 4

class InteractionCallbackType(IntEnum):
    """Possible ways to respond to an interaction.
    For use in :meth:`Context.respond`.

    .. attribute:: PONG

        Only used to ACK a :attr:`InteractionType.PING`, never valid here.
        Included only for completeness.
    .. attribute:: CHANNEL_MESSAGE_WITH_SOURCE

        Show user input and send a message. Default for slash commands.
    .. attribute:: DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE

        Show user input and display a "waiting for bot" system message.
        Send a response with this type and edit the response later if you
        need to do some asynchronous fetch or something.
    .. attribute:: DEFERRED_UPDATE_MESSAGE

        ACK a component interaction and edit the original message later.
        The user does not see a loading state.
    .. attribute:: UPDATE_MESSAGE

        Edit the original message a component is attached.
    .. attribute:: APPLICATION_COMMAND_AUTOCOMPLETE_RESULT

        Respond with autocomplete suggestions.
    """
    # ACK a Ping
    PONG = 1
    CHANNEL_MESSAGE_WITH_SOURCE = 4
    DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE = 5
    DEFERRED_UPDATE_MESSAGE = 6
    UPDATE_MESSAGE = 7
    APPLICATION_COMMAND_AUTOCOMPLETE_RESULT = 8

InteractionResponseType = InteractionCallbackType

class CallbackFlags(IntFlag):
    """Flags to pass to the ``flags`` argument of :meth:`Context.respond`.

    .. attribute:: EPHEMERAL

        Only the user receiving the message can see it
    """
    EPHEMERAL = 1 << 6

MessageFlags = CallbackFlags

class ChoiceEnum(Enum):
    """Callback parameters annotated with subclasses of this class
    will use the enums as choices. See the ``/numbers`` command in the
    demo bot for an example.
    """
    pass

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