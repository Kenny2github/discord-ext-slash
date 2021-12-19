API Reference
=============

.. currentmodule:: discord.ext.slash

Decorators
----------

.. autodecorator:: cmd
.. autodecorator:: group
.. autodecorator:: permit

Classes
-------

The Bot
~~~~~~~

.. autoclass:: SlashBot

Interaction Context
~~~~~~~~~~~~~~~~~~~

.. autoclass:: Context
.. autoclass:: Interaction

Slash Commands
~~~~~~~~~~~~~~

.. autoclass:: Command
.. autoclass:: Group

Data Classes
~~~~~~~~~~~~

.. autoclass:: Option
.. autoclass:: Choice

Miscellaneous
~~~~~~~~~~~~~

.. autoclass:: SlashWarning
.. autoclass:: CommandPermissionsDict

Partial Objects
~~~~~~~~~~~~~~~

Objects resolved from the slash commands API often do not contain all the
information that discord.py prefers (most notably guild information).

.. autoclass:: PartialObject
   :show-inheritance:
.. autoclass:: PartialTextChannel
   :show-inheritance:
.. autoclass:: PartialCategoryChannel
   :show-inheritance:
.. autoclass:: PartialVoiceChannel
   :show-inheritance:
.. autoclass:: PartialMember
   :show-inheritance:
.. autoclass:: PartialRole
   :show-inheritance:

Enums
-----

.. autoclass:: ApplicationCommandOptionType
.. autoclass:: ApplicationCommandPermissionType
.. autoclass:: InteractionResponseType
.. autoclass:: CallbackFlags
.. autoclass:: MessageFlags
.. autoclass:: ChoiceEnum

Events
------

.. function:: on_interaction_create(event: dict)

   Triggered by Discord interactions. For internal use.

.. function:: on_slash_permissions()

   Triggered immediately after :meth:`SlashBot.register_commands` to give an
   opportunity to register dynamic permissions in code before pushing to the
   API. If overriding using @:meth:`discord.Client.event`, you must await
   :meth:`-SlashBot.register_permissions` at the end of the event handler.
   See ``/stop`` in ``demo_bot.py`` for an example.