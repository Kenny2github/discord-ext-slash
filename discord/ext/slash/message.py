from typing import List
import discord
from .components import MessageComponent

class ComponentedMessage(discord.Message):
    """Monkeypatch discord.py's Message to include components."""

    __slots__ = discord.Message.__slots__ + ('components',)

    components: List[MessageComponent]

    def __init__(self, *, state, channel, data):
        super().__init__(state=state, channel=channel, data=data)
        self.components = [MessageComponent.from_dict(d)
                           for d in data.get('components', [])]