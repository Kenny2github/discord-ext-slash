from __future__ import annotations
from typing import Optional, List, Set, Union, Type
import discord
from .simples import ApplicationCommandOptionType, ChoiceEnum

class Option:
    """An argument to a :class:`Command`.
    This must be passed as an annotation to the corresponding argument.

    Constructor arguments map directly to attributes, besides the ones below
    which have different type signatures:

    :param description:
        Annotating a parameter with ``EnumClass`` has the same effect as
        with ``Option(description=EnumClass)``.
    :type description: Union[str, Type[ChoiceEnum]]
    :param choices:
        Strings are converted into :class:`Choice` objects with the same
        ``name`` and ``value``. :class:`dict` objects are passed as kwargs to
        the :class:`Choice` constructor.
    :type choices: Optional[Iterable[Union[str, Mapping[str, str], Choice]]]
    :param channel_types:
        Pass either the raw integers or the enum values.
    :type channel_types: Optional[Iterable[Union[int, discord.ChannelType]]]
    :param channel_type:
        A shortcut to ``channel_types=[channel_type]``.
    :type channel_type: Optional[Union[int, discord.ChannelType]]

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
    .. attribute:: channel_types
        :type: Optional[set[discord.ChannelType]]

        Sets ``type`` to :attr:`ApplicationCommandOptionType.CHANNEL`,
        additionally restricted to a set of specific channel types.
    .. attribute:: min_value
        :type: Union[int, float, None]

        For numerical options, this is the minimum value allowable.
        If ``type`` is not a numerical type, it is inferred from the
        type of this argument. Otherwise, this argument is cast to the
        type corresponding to ``type``.
    .. attribute:: max_value
        :type: Union[int, float, None]

        Same as ``min_value`` but maximum. If both ``min_value`` and
        ``max_value`` are specified, *and* ``type`` is non-numeric,
        ``type`` is inferred from this argument, not ``min_value``.
    """
    description: str
    type: ApplicationCommandOptionType = ApplicationCommandOptionType.STRING
    name: Optional[str] = None
    required: Optional[bool] = False
    choices: Optional[List[Choice]] = None
    channel_types: Optional[Set[discord.ChannelType]] = None
    min_value: Union[int, float, None] = None
    max_value: Union[int, float, None] = None

    _enum: Optional[Type[ChoiceEnum]] = None

    @staticmethod
    def value_to_enum(value: Union[int, discord.ChannelType]):
        if isinstance(value, discord.ChannelType):
            return value
        return discord.ChannelType(value)

    def __init__(
        self, description: Union[str, Type[ChoiceEnum]],
        type: ApplicationCommandOptionType = ApplicationCommandOptionType.STRING,
        **kwargs
    ):
        self.name = kwargs.pop('name', None) # can be set automatically
        if 'channel_types' in kwargs:
            self.channel_types = set(map(self.value_to_enum, kwargs.pop('channel_types')))
            self.type = ApplicationCommandOptionType.CHANNEL
        elif 'channel_type' in kwargs:
            self.channel_types = {self.value_to_enum(kwargs.pop('channel_type'))}
            self.type = ApplicationCommandOptionType.CHANNEL
        else:
            self.type = ApplicationCommandOptionType(type)
        if 'max_value' in kwargs:
            self.max_value = kwargs.pop('max_value')
            if self.type == ApplicationCommandOptionType.INTEGER:
                self.max_value = int(self.max_value)
            elif self.type == ApplicationCommandOptionType.NUMBER:
                self.max_value = float(self.max_value)
            elif isinstance(self.max_value, int):
                self.type = ApplicationCommandOptionType.INTEGER
            elif isinstance(self.max_value, float):
                self.type = ApplicationCommandOptionType.NUMBER
        if 'min_value' in kwargs:
            self.min_value = kwargs.pop('min_value')
            if self.type == ApplicationCommandOptionType.INTEGER:
                self.min_value = int(self.min_value)
            elif self.type == ApplicationCommandOptionType.NUMBER:
                self.min_value = float(self.min_value)
            elif isinstance(self.min_value, int):
                self.type = ApplicationCommandOptionType.INTEGER
            elif isinstance(self.min_value, float):
                self.type = ApplicationCommandOptionType.NUMBER
        if isinstance(description, str):
            self.description = description
        elif issubclass(description, ChoiceEnum):
            kwargs['choices'] = [
                Choice(desc.value, attr)
                for attr, desc in description.__members__.items()]
            self._enum = description
            self.description = description.__doc__
            self.type = ApplicationCommandOptionType.STRING
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
        if self.channel_types:
            data['channel_types'] = [t.value for t in self.channel_types]
        if self.min_value is not None:
            data['min_value'] = self.min_value
        if self.max_value is not None:
            data['max_value'] = self.max_value
        return data

    def clone(self):
        value = type(self)(**self.to_dict())
        if self._enum is not None:
            value._enum = self._enum
        return value

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
