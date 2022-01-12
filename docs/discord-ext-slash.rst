API Reference
=============

.. currentmodule:: discord.ext.slash

Decorators
----------

.. autodecorator:: cmd
.. autodecorator:: group
.. autodecorator:: permit
.. autodecorator:: callback

Classes
-------

The Bot
~~~~~~~

.. autoclass:: SlashBot

Base Classes
~~~~~~~~~~~~

.. autoclass:: BaseContext
.. autoclass:: BaseCallback
.. autoclass:: MessageComponent

Interaction Context
~~~~~~~~~~~~~~~~~~~

.. autoclass:: Context
   :show-inheritance:
.. autoclass:: Interaction
.. autoclass:: ComponentContext
   :show-inheritance:

Slash Commands
~~~~~~~~~~~~~~

.. autoclass:: Command
   :show-inheritance:
.. autoclass:: Group


Message Components
~~~~~~~~~~~~~~~~~~

.. autoclass:: ComponentCallback
.. autoclass:: ActionRow
   :show-inheritance:
.. autoclass:: Button
   :show-inheritance:
.. autoclass:: SelectMenu
   :show-inheritance:
.. autoclass:: SelectOption

Data Classes
~~~~~~~~~~~~

.. autoclass:: Option
.. autoclass:: Choice

Miscellaneous
-------------

.. autoclass:: SlashWarning
.. autoclass:: CommandPermissionsDict
.. autoclass:: ComponentedMessage
   :show-inheritance:

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
~~~~~

.. autoclass:: ApplicationCommandOptionType
.. autoclass:: ApplicationCommandPermissionType
.. autoclass:: InteractionCallbackType
.. autoclass:: InteractionResponseType
.. autoclass:: CallbackFlags
.. autoclass:: ChoiceEnum
.. autoclass:: ButtonStyle

Events
------

.. function:: on_interaction_create(event: dict)

   Triggered by Discord interactions. For internal use.

.. function:: on_slash_permissions()

   Triggered immediately after :meth:`SlashBot.register_commands` to give an
   opportunity to register dynamic permissions in code before pushing to the
   API. If overriding using @:meth:`discord.Client.event`, you must await
   :meth:`SlashBot.register_permissions` at the end of the event handler.
   See ``/stop`` in ``demo_bot.py`` for an example.

.. function:: on_before_slash_command_invoke(ctx: Context)

   Triggered immediately before a slash command is invoked, for logging etc.

.. function:: on_after_slash_command_invoke(ctx: Context)

   Triggered immediately after a *successful* slash command invocation.
   Failed invocations will trigger :func:`discord.on_command_error` instead.

.. function:: on_before_component_callback_invoke(ctx: ComponentContext)

   Triggered immediately before a message component callback is invoked.

.. function:: on_after_component_callback_invoke(ctx: ComponentContext)

   Triggered immediately after a successful callback invocation.

.. function:: on_component_callback_deregister(callback: ComponentCallback)

   Triggered when a component callback is deregistered, either automatically
   as part of TTL expiry / use counting or manually.