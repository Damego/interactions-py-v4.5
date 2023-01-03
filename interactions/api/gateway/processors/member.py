from ...models import gw as events
from ...models.guild import Guild
from ...models.member import Member
from ...models.misc import Snowflake
from .base import BaseProcessor


class MemberProcessor(BaseProcessor):
    def guild_member_add(self, data: dict) -> tuple:
        guild_id = Snowflake(data["guild_id"])
        member = self._cache.add_member(data, guild_id)

        return (member,)

    def guild_member_update(self, data: dict) -> tuple:
        guild_id = Snowflake(data["guild_id"])
        id = guild_id, Snowflake(data["user"]["id"])

        before, after = self._update_event(Member, data, id=id)

        if guild := self._cache.get_guild(guild_id):
            guild._member_ids.add(after.id)

        return before, after

    def guild_member_remove(self, data: dict) -> tuple:
        guild_id = Snowflake(data["guild_id"])
        user_id = Snowflake(data["user"]["id"])

        member = self._cache.remove_member(user_id, guild_id)
        if member is None:
            member = Member(**data)

        return (member,)

    def guild_members_chunk(self, data: dict) -> tuple:
        guild_members = events.GuildMembers(**data)
        cache = self._cache[Member]

        guild = self._cache[Guild].get(guild_members.guild_id)

        for member in guild_members.members:
            cache.add(member, id=(guild_members.guild_id, member.id))  # With `merge` method it will take a long time
            guild._member_ids.add(member.id)

        return (guild_members,)
