from __future__ import annotations
from typing import Iterable, List, Mapping, Type, Union, Optional
from dataclasses import dataclass
import discord
from .simples import ButtonStyle

class MessageComponent:
    """An interaction component on a message.

    .. attribute:: type
        :type: int

        The component type. A constant on subclasses.
    """
    type: int

    def to_dict(self) -> dict:
        """Render this component to a dictionary."""
        return {'type': self.type}

class ActionRow(MessageComponent):
    """A container for other components.

    This can be instantiated either like
    ``ActionRow(component1, component2)``
    or like ``ActionRow([component1, component2])``.

    :param first:
        The first of one or multiple subcomponents, *or*
        an iterable of subcomponents.
    :type first: Union[Button, SelectMenu, Iterable[Button]]
    :param *args:
        The rest of the subcomponents, if ``first`` is the first.
    :type *args: Button

    .. attribute:: components
        :type: list[Union[Button, SelectMenu]]

        Up to 5 subcomponents"""
    type = 1

    components: List[NonActionRow]

    def __init__(
        self,
        first: Union[NonActionRow, Iterable[NonActionRow]],
        *args: Button
    ) -> None:
        if isinstance(first, SelectMenu):
            # only one select menu allowed
            self.components = [first]
        elif isinstance(first, Button):
            self.components = [first] + list(args)
        else:
            # if it's not a component, assume it's an iterable of ones
            self.components = list(first) + list(args)

    def to_dict(self) -> dict:
        result = super().to_dict()
        result['components'] = [comp.to_dict() for comp in self.components]
        return result

class Button(MessageComponent):
    """A button that can be pressed.

    .. attribute:: style
        :type: ButtonStyle

        The style of button. There are four colors and one link style.
    .. attribute:: label
        :type: Optional[str]

        The text label of the button. Either this or ``emoji`` is required.
    .. attribute:: emoji
        :type: Optional[discord.PartialEmoji]

        The emoji label of the button.
    .. attribute:: custom_id
        :type: Optional[str]

        Arbitrary dev-defined ID. Forbidden for :attr:`ButtonStyle.LINK`,
        required otherwise.
    .. attribute:: url
        :type: Optional[str]

        URL to link to. Required for :attr:`ButtonStyle.LINK`,
        forbidden otherwise.
    .. attribute: disabled
        :type: bool

        Whether the button is disabled.
    """
    type = 2
    style: ButtonStyle
    label: Optional[str] = None
    emoji: Optional[discord.PartialEmoji] = None
    custom_id: Optional[str] = None
    url: Optional[str] = None
    disabled: bool = False

    def __init__(
        self,
        style: ButtonStyle, label: str = None,
        emoji: discord.PartialEmoji = None,
        custom_id: str = None, url: str = None,
        disabled: bool = False
    ) -> None:
        if style == ButtonStyle.LINK:
            if custom_id is not None:
                raise TypeError('custom_id not allowed on LINK-style Buttons')
            if not url:
                raise TypeError('LINK-style Buttons must have a url')
        else:
            if not custom_id:
                raise TypeError('Non-LINK Buttons must have a custom_id')
            if url is not None:
                raise TypeError('url not allowed on non-LINK Buttons')
        if label is None and emoji is None:
            raise TypeError('Button must have at least one of label or emoji')
        self.style = style
        self.label = label
        self.emoji = emoji
        self.custom_id = custom_id
        self.url = url
        self.disabled = disabled

    def to_dict(self) -> dict:
        result = super().to_dict()
        result.update({
            'style': int(self.style),
            'disabled': self.disabled
        })
        if self.label:
            result['label'] = self.label
        if self.emoji:
            result['emoji'] = self.emoji.to_dict()
        if self.custom_id:
            result['custom_id'] = self.custom_id
        if self.url:
            result['url'] = self.url
        return result

class SelectMenu(MessageComponent):
    """A select menu for picking from choices.

    .. attribute:: custom_id
        :type: str

        Arbitrary dev-defined ID.
    .. attribute:: options
        :type: list[SelectOption]

        The options in the select menu.
    .. attribute:: placeholder
        :type: Optional[str]

        Placeholder text shown if nothing is selected.
    .. attribute:: min_values
        :type: int

        Minimum number of values that can be selected.
        This can be 0 to facilitate choosing none,
        or more than 1 (the default) for a pick-N scheme.
    .. attribute:: max_values
        :type: int

        Maximum number of values that can be selected.
        Leaving both this and ``min_values`` at the default,
        1, recovers the regular mechanics of a simple select
        menu. However, this can also be greater than 1 to
        facilitate choosing a range of numbers of options.
    .. attribute:: disabled
        :type: bool

        Whether the select menu is disabled.
    """
    type = 3
    custom_id: str
    options: List[SelectOption]
    placeholder: Optional[str] = None
    min_values: int = 1
    max_values: int = 1
    disabled: bool = False

    def __init__(
        self,
        custom_id: str, options: Iterable[SelectOption],
        placeholder: str = None, min_values: int = 1,
        max_values: int = 1, disabled: bool = False
    ) -> None:
        self.custom_id = custom_id
        self.options = list(options)
        self.placeholder = placeholder
        self.min_values = min_values
        self.max_values = max_values
        self.disabled = disabled

    def to_dict(self) -> dict:
        result = super().to_dict()
        result.update({
            'custom_id': self.custom_id,
            'options': [opt.to_dict() for opt in self.options],
            'min_values': self.min_values,
            'max_values': self.max_values,
            'disabled': self.disabled
        })
        if self.placeholder:
            result['placeholder'] = self.placeholder
        return result

@dataclass
class SelectOption:
    """An option for a :class:`SelectMenu`.

    .. attribute:: label
        :type: str

        Option value displayed to user.
    .. attribute:: value
        :type: str

        Option value sent to bot.
    .. attribute:: description
        :type: Optional[str]

        Extended description of of the option.
    .. attribute:: emoji
        :type: Optional[discord.PartialEmoji]

        Emoji label for the option.
    .. attribute:: disabled
        :type: bool

        If :const:`True`, this option is selected by default.
    """
    label: str
    value: str
    description: Optional[str] = None
    emoji: Optional[discord.PartialEmoji] = None
    default: bool = False

    def to_dict(self) -> dict:
        result = {
            'label': self.label,
            'value': self.value,
            'default': self.default
        }
        if self.description:
            result['description'] = self.description
        if self.emoji:
            result['emoji'] = self.emoji.to_dict()
        return result

NonActionRow = Union[Button, SelectMenu]

TYPE_CLASSES: Mapping[int, Type[MessageComponent]] = {
    1: ActionRow,
    2: Button,
    3: SelectMenu,
}
