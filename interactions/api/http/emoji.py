from typing import TYPE_CHECKING, List, Optional

from ..models.emoji import Emoji
from ..models.guild import Guild
from ..models.misc import Snowflake
from .request import _Request
from .route import Route

if TYPE_CHECKING:
    from ...api.cache import Cache

__all__ = ("EmojiRequest",)


class EmojiRequest:
    _req: _Request
    cache: "Cache"

    def __init__(self) -> None:
        pass

    async def get_all_emoji(self, guild_id: int) -> List[dict]:
        """
        Gets all emojis from a guild.

        :param guild_id: Guild ID snowflake.
        :return: A list of emojis.
        """
        res = await self._req.request(Route("GET", f"/guilds/{guild_id}/emojis"))

        [self.cache[Emoji].merge(Emoji(**emoji, _client=self)) for emoji in res]

        return res

    async def get_guild_emoji(self, guild_id: int, emoji_id: int) -> dict:
        """
        Gets an emote from a guild.

        :param guild_id: Guild ID snowflake.
        :param emoji_id: Emoji ID snowflake.
        :return: Emoji object
        """
        res = await self._req.request(Route("GET", f"/guilds/{guild_id}/emojis/{emoji_id}"))

        self.cache[Emoji].merge(Emoji(**res, _client=self))

        return res

    async def create_guild_emoji(
        self, guild_id: int, payload: dict, reason: Optional[str] = None
    ) -> dict:
        """
        Creates an emoji.

        :param guild_id: Guild ID snowflake.
        :param payload: Emoji parameters.
        :param reason: Optionally, give a reason.
        :return: An emoji object with the included parameters.
        """
        res = await self._req.request(
            Route("POST", f"/guilds/{guild_id}/emojis"), json=payload, reason=reason
        )

        self.cache[Emoji].add(Emoji(**res, _client=self))

        return res

    async def modify_guild_emoji(
        self, guild_id: int, emoji_id: int, payload: dict, reason: Optional[str] = None
    ) -> dict:
        """
        Modifies an emoji.

        :param guild_id: Guild ID snowflake.
        :param emoji_id: Emoji ID snowflake
        :param payload: Emoji parameters with updated attributes
        :param reason: Optionally, give a reason.
        :return: An emoji object with updated attributes.
        """
        res = await self._req.request(
            Route("PATCH", f"/guilds/{guild_id}/emojis/{emoji_id}"), json=payload, reason=reason
        )

        self.cache[Emoji].merge(Emoji(**res, _client=self))

        return res

    async def delete_guild_emoji(
        self, guild_id: int, emoji_id: int, reason: Optional[str] = None
    ) -> None:
        """
        Deletes an emoji.

        :param guild_id: Guild ID snowflake.
        :param emoji_id: Emoji ID snowflake
        :param reason: Optionally, give a reason.
        """
        await self._req.request(
            Route("DELETE", f"/guilds/{guild_id}/emojis/{emoji_id}"), reason=reason
        )

        self.cache[Emoji].pop(Snowflake(emoji_id))
