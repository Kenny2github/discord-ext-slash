
Support slash commands.

Example Usage
=============

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
        # propagate. Useful because commands are
        # re-registered every time the bot starts.
        debug_guild=7293012031203012
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
        """Send a message in the bot's name""" # description of command
        await ctx.respond(message, # respond to the interaction
            # sends a message without showing the command invocation
            rtype=slash.InteractionResponseType.ChannelMessage)

    client.run(token)

Notes
=====
* ``slash.Context`` emulates ``commands.Context``, but only to a certain extent.
  Notably, ``ctx.message`` does not exist, because slash commands can be run
  completely without the involvement of messages. However, channel and author
  information is still available.
* All descriptions are **required**.

Not Yet Supported
=================
* Subcommands
