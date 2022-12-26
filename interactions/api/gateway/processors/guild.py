from .base import BaseProcessor
from ...models import gw as events
from ...models.guild import Guild, Invite
from ...models.misc import Snowflake
from ...models.role import Role
from ...models.emoji import Emoji
from ...models.message import Sticker


class GuildProcessor(BaseProcessor):
    def guild_create(self, data: dict) -> tuple:
        guild = Guild(**data)
        self._cache[Guild].add(guild)

        return (guild,)

    def guild_update(self, data: dict) -> tuple:
        return self._update_event(Guild, data)

    def guild_delete(self, data: dict) -> tuple:
        guild = self._delete_event(Guild, id=Snowflake(data["id"]))
        return (guild,)

    def guild_ban_add(self, data: dict) -> tuple:
        ban = events.GuildBan(**data)
        return (ban,)

    def guild_ban_remove(self, data: dict) -> tuple:
        return self.guild_ban_add(data)

    def guild_emojis_update(self, data: dict) -> tuple:
        guild_emojis = events.GuildEmojis(**data)

        guild = self._cache[Guild].get(guild_emojis.guild_id)

        [guild._emoji_ids.add(Snowflake(emoji.id)) for emoji in guild_emojis.emojis]
        [self._cache[Emoji].merge(emoji) for emoji in guild_emojis.emojis]

        return (guild_emojis,)

    def guild_stickers_update(self, data: dict) -> tuple:
        guild_stickers = events.GuildStickers(**data)

        guild = self._cache[Guild].get(guild_stickers.guild_id)

        [guild._sticker_ids.add(Snowflake(sticker.id)) for sticker in guild_stickers.stickers]
        [self._cache[Sticker].merge(sticker) for sticker in guild_stickers.stickers]

        return (guild_stickers,)

    def guild_integrations_update(self, data: dict) -> tuple:
        return (events.GuildIntegrations(**data),)

    def voice_state_update(self, data: dict) -> tuple:
        before, after = self._update_event(events.VoiceState, data)

        # User left from voice channel, so we don't need to store it in the cache anymore
        if after.channel_id is None:
            self._cache[events.VoiceState].pop(after.user_id)

        return before, after

    def webhooks_update(self, data: dict) -> tuple:
        webhooks = events.Webhooks(**data)
        return (webhooks,)

    def integration_create(self, data: dict) -> tuple:
        return (events.Integration(**data),)

    def integration_update(self, data: dict) -> tuple:
        return (events.Integration(**data),)

    def integration_delete(self, data: dict) -> tuple:
        return (events.Integration(**data),)

    def invite_create(self, data: dict) -> tuple:
        return (Invite(**data),)

    def invite_delete(self, data: dict) -> tuple:
        return (Invite(**data),)

    def guild_role_create(self, data: dict) -> tuple:
        role = self._create_event(Role, data["role"])

        return (role,)

    def guild_role_update(self, data: dict) -> tuple:
        return self._update_event(Role, data["role"])

    def guild_role_delete(self, data: dict) -> tuple:
        return (self._delete_event(Role, id=data["role_id"]),)