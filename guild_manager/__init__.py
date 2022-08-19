# -*- coding: utf-8 -*-
"""
This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""

from typing import Literal, NamedTuple

from discord.ext.commands import Bot

from .cog import DefaultManager


__version__ = '0.1.0a'


class _VersionInfo(NamedTuple):
    major: int
    minor: int
    micro: int
    releaselevel: Literal['alpha', 'beta', 'candidate', 'final']
    serial: int


version_info: _VersionInfo = _VersionInfo(major=0, minor=1, micro=0, releaselevel='alpha', serial=0)


async def setup(bot: Bot) -> None:
    """Called when this module is loaded using `await bot.load_extension('guild_manager')`"""
    await bot.add_cog(DefaultManager(bot))


del NamedTuple, Literal, _VersionInfo, Bot
