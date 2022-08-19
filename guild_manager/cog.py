"""
This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""

import datetime
import logging
from typing import Any, Optional, Union

import discord
from discord.ext import commands, tasks


__all__ = ('DefaultManager',)

_log = logging.getLogger(__name__)


class DefaultManager(commands.Cog):
    """A guild manager used to leave guilds automatically under certain criteria.

    This class is a subclass of :class:`discord.ext.commands.Cog`, meaning it can be loaded
    into a :class:`discord.ext.commands.Bot` using `bot.add_cog`. In addition,
    it can be customised to implement anything a :class:`discord.ext.commands.Cog` could
    implement, such as commands to manage its behaviour.

    Note:
        If your bot is disconnected from the discord gateway due to a network
        disconnection or otherwise, this cog will not be able to leave any guilds
        during that time. It is recommended to manually set your bot to private from
        the developer dashboard instead, if this risk is too significant.

    Attributes
    -----------
    bot: :class:`discord.ext.commands.Bot`
        The bot instance this cog is associated with.

    max_guilds: :class:`int`
        The maximum number of guilds the bot is allowed to join. By default, this is
        set to 98 guilds.

        Whenever a new guild is joined above this limit, that guild is immediately left,
        and :meth:`self.on_guild_limit_reached` is called.

        Note:
            Under very rare circumstances it is possible that two or more guilds are joined
            in quick succession before the bot can leave them, which may lead the guild count
            to be exceeded temporarily. As a result, it is recommended to leave a "safety net"
            in your bot's maximum guild count to account for this behaviour. The default limit
            of 98 ensures that multiple guilds joined simultaneously will not cause the bot to
            exceed 99 guilds, but this value may be adjusted as necessary.

    min_members: Optional[:class:`int`]
        The minimum member count enforced on guilds. If a guild does not have this many
        members, the bot will leave that guild. See :meth:`self.leave_criteria` for more
        information on which criteria are used to determine whether a guild should be left.
        Defaults to `None`.
        Note:
            This requires the :meth:`discord.Intents.members` intent to function properly
            with periodic guild checks. Without this intent, the :prop:`member_count` field
            of guilds will not be up to date. However, newly joined guilds will always have
            this field up to date.

    max_members: Optional[:class:`int`]
        The maximum member count enforced on guilds. If a guild has more members than this,
        the bot will leave that guild. See :meth:`self.leave_criteria` for more
        information on which criteria are used to determine whether a guild should be left.
        Defaults to `None`.

        Note:
            This requires the :meth:`discord.Intents.members` intent to function properly
            with periodic guild checks. Without this intent, the :prop:`member_count` field
            of guilds will not be up to date. However, newly joined guilds will always have
            this field up to date.

    max_bot_ratio: Optional[:class:`float`]
        The maximum proportion of guild members that are allowed to be bots. If a guild has
        more bots than specified here, this bot will leave that guild. See
        :meth:`self.leave_criteria` for more information on which criteria are used to
        determine whether a guild should be left. Defaults to `None`.

        Note:
            This requires the :meth:`discord.Intents.members` intent to function.
            If it is not provided in the bot constructor and the developer dashboard, the
            bot will not have access to the member lists of guilds, and therefore cannot
            count the number of bots in a guild.

    min_guild_age: Optional[:class:`datetime.timedelta`]
        The minimum age enforced on guilds. If a guild was created more recently than this,
        the bot will leave that guild. See :meth:`self.leave_criteria` for more
        information on which criteria are used to determine whether a guild should be left.
        Defaults to `None`.

    frequency: Optional[Union[:class:`datetime.timedelta`, :class:`float`]]
        How often the bot should check already joined guilds for eligibility.
        If this is set to `None`, the bot will not periodically check existing guilds for this leave criteria.
        If this is a :class:`datetime.timedelta`, it is interpreted as the duration between waves of checks.
        If this is a :class:`float`, it is interpreted as the number of seconds between waves of checks.
    """

    def __init__(
        self,
        bot: commands.Bot,
        *,
        max_guilds: int = 98,
        min_members: Optional[int] = None,
        max_members: Optional[int] = None,
        max_bot_ratio: Optional[float] = None,
        min_guild_age: Optional[datetime.timedelta] = None,
        frequency: Optional[Union[datetime.timedelta, int, float]] = None,
    ) -> None:
        self.bot = bot
        self.max_guilds = max_guilds
        self.min_members = min_members
        self.max_members = max_members
        self.max_bot_ratio = max_bot_ratio
        self.min_guild_age = min_guild_age
        self.frequency = frequency

        self.__seconds: float = discord.utils.MISSING
        if self.frequency is not None:
            if isinstance(self.frequency, datetime.timedelta):
                self.__seconds = self.frequency.total_seconds()
            elif isinstance(self.frequency, (int, float)):
                self.__seconds = self.frequency
            else:
                raise TypeError(
                    f'expected frequency to be a datetime.timedelta or a number, got {self.frequency.__class__!r}'
                )

    async def cog_load(self) -> None:
        if self.__seconds is not discord.utils.MISSING:
            self._check_guilds.change_interval(seconds=self.__seconds)
            self._check_guilds.start()

    async def cog_unload(self) -> None:
        if self.__seconds is not discord.utils.MISSING:
            self._check_guilds.cancel()

    @tasks.loop()
    async def _check_guilds(self) -> None:
        for guild in self.bot.guilds:
            if await self.leave_criteria(guild):
                await self.before_leave(guild, new=False)
                await guild.leave()
                await self.after_leave(guild, new=False)

    async def leave_criteria(self, guild: discord.Guild) -> bool:
        """Performs the logic determining whether a guild should be left.

        This typically shouldn't be overridden.

        Returns `True` if :param:`guild` fits any of the criteria for rejection
        and is not whitelisted. Returns `False` otherwise.

        The criteria, if specified, are:
        * The member count (both mimimum and maximum)
        * The proportion of bots to members in the guild (maximum)
        * The guild age (mimimum)
        * Custom criteria defined in :meth:`self.extra_criteria`

        If any of these limits are broken, and :meth:`self.whitelisted` returns
        `False`, this function will return `True`.
        Parameters
        -----------
        guild: :class:`discord.Guild`
            The guild being checked.
        """
        if await discord.utils.maybe_coroutine(self.whitelisted, guild):
            return False
        if self.min_guild_age is not None and discord.utils.utcnow() - guild.created_at > self.min_guild_age:
            return True
        if self.min_members is not None:
            if guild.member_count is None:
                _log.warning(
                    'member_count for guild %s (ID: %s) is None. Cannot check min_members criteria.', guild.name, guild.id
                )
            else:
                if guild.member_count < self.min_members:
                    return True
        if self.max_members is not None:
            if guild.member_count is None:
                _log.warning(
                    'member_count for guild %s (ID: %s) is None. Cannot check max_members criteria.', guild.name, guild.id
                )
            else:
                if guild.member_count > self.max_members:
                    return True
        if self.max_bot_ratio is not None:
            if guild.member_count is None:
                _log.warning(
                    'member_count for guild %s (ID: %s) is None. Cannot check max_bot_ratio criteria.', guild.name, guild.id
                )
            else:
                bots = sum(m.bot for m in guild.members)
                if bots / guild.member_count > self.max_bot_ratio:
                    return True
        return await discord.utils.maybe_coroutine(self.extra_criteria, guild)

    def whitelisted(self, guild: discord.Guild, /) -> bool:
        """A method to determine whether a guild should not be left,
        even if it fits leaving criteria.

        This should be overridden to whitelist certain guilds.

        This function may be a coroutine.

        Returns `True` if the guild is whitelisted, and `False` otherwise.

        By default, this returns `False`

        Parameters
        -----------
        guild: :class:`discord.Guild`
            The guild being checked.
        """
        return False

    def extra_criteria(self, guild: discord.Guild, /) -> bool:
        """Contains custom logic used to determine whether a guild should be left.

        This should be overridden to add any additional criteria to check guilds on.

        This function may be a coroutine.

        Returns `True` if the guild should be left, and `False` otherwise.

        By default, this returns `False`.

        Parameters
        -----------
        guild: :class:`discord.Guild`
            The guild being checked.
        """
        return False

    async def before_leave(self, guild: discord.Guild, /, *, new: bool = True) -> Any:
        """Called before a guild is left.

        This is called before the guild is left, and can be used to do any cleanup
        necessary.

         This will not be called if the bot meets or exceeds its :attribute:`max_guilds` count as a result of this guild.
        Instead, :meth:`self.on_guild_limit_reached` will be called.

        Parameters
        -----------
        guild: :class:`discord.Guild`
            The guild being left.
        new: :class:`bool`
            Whether the guild was just joined. If `False`, the guild is an existing guild that just met the criteria for leaving.
        """
        pass

    async def after_leave(self, guild: discord.Guild, /, *, new: bool = True) -> Any:
        """Called after a guild is left.

        This is called after the guild is left, and can be used to do any cleanup
        necessary.

        Parameters
        -----------
        guild: :class:`discord.Guild`
            The guild being left.

            Note:
                The bot may or may not be in the guild when this is executed. To determine whether
                or the bot has already left this guild, check whether the value of :attr:`guild.me` is `None`.

        new: :class:`bool`
            Whether the guild was just joined. If `False`, the guild is an existing guild that just met the criteria for leaving.
        """
        pass

    async def on_guild_limit_reached(self, guild: discord.Guild, /) -> Any:
        """Called when the bot's guild count is greater than or equal to :attribute:`self.max_guilds`
        as a result of joining :param:`guild`.

        This event is called regardless of whether a guild is eligible.

        Parameters
        -----------
        guild: :class:`discord.Guild`
            The guild that was just joined.

            Note:
                The bot may or may not be in the guild when this is executed. To determine whether
                or the bot has already left this guild, check whether the value of :attr:`guild.me` is `None`.
        """
        pass

    @commands.Cog.listener('on_guild_join')
    async def _on_guild_join(self, guild: discord.Guild) -> Any:
        if len(self.bot.guilds) >= self.max_guilds:
            await self.on_guild_limit_reached(guild)
            await guild.leave()
            await self.after_leave(guild)
        elif await self.leave_criteria(guild):
            await self.before_leave(guild)
            await guild.leave()
            await self.after_leave(guild)
