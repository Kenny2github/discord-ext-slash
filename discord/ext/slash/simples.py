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