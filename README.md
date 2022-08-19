# guild-manager

Since 7th October 2020, unverified bots must maintain a guild count of 99 or fewer 
to access privileged intents. From September 2022, message content becomes a
privileged intent, rendering bots that haven't migrated completely to slash commands
virtually unusable.
This module provides a robust API to automatically manage your bot's guild count by 
leaving guilds matching certain customisable criteria.

## Installation

```bash
pip install -U git+https://github.com/lmaotrigine/guild-manager
```

## Usage

The module can be enabled out-of-the-box using

```py
await bot.load_extension("guild_manager")
```

In this mode, the bot will unconditionally leave any new guilds joined after the guild count hits 98.

You can customize the behavior of guild_manager and hook into the events by inheriting from the
`guild_manager.DefaultManager` cog:

```py
import discord
import guild_manager
from discord.ext import commands


class MyManager(guild_manager.DefaultManager):
    async def whitelisted(self, guild: discord.Guild) -> bool:
        return guild.id == 360268483197665282
    
    async def before_leave(self, guild: discord.Guild) -> None:
        await guild.owner.send('This guild does not have enough users, or has too many bots!')
    
    async def after_leave(self, guild: discord.Guild) -> None:
        print(f'Left guild {guild} (ID: {guild.id})')

# The members intent is required to check how many bots are in a guild
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
async def main():
    async with commands.Bot(command_prefix="$", intents=intents) as bot:

        # Other parameters are detailed in the documentation
        await bot.add_cog(MyBouncer(bot,
            min_member_count=10,
            max_bot_ratio=0.5,
        ))
```
