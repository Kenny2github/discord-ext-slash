⚠️ Archived
============
Please use the native features available in discord.py.

----

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

* ``discord.ext.slash.Context`` emulates
  ``discord.ext.commands.Context``, but only to a certain extent.
  Notably, ``ctx.message`` does not exist, because slash commands can be run
  completely without the involvement of messages. However, channel and author
  information is still available.
* All descriptions are **required**.
* You must grant the bot ``applications.commands`` permissions in the OAuth2 section of the developer dashboard.

See the `docs <https://discord-ext-slash.rtfd.io>`_.
