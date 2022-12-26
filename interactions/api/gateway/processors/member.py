from .base import BaseProcessor
from ...models import gw as events
from ...models.guild import Guild
from ...models.misc import Snowflake
from ...models.member import Member


class MemberProcessor(BaseProcessor):
    def guild_member_add(self, data: dict) -> tuple:
        guild_id = Snowflake(data["guild_id"])
        id = guild_id, Snowflake(data["id"])

        member = self._create_event(Member, data, id=id)
        guild = self._cache[Guild].get(guild_id)
        guild._member_ids.add(member.id)

        return (member,)

    def guild_member_update(self, data: dict) -> tuple:
        guild_id = Snowflake(data["guild_id"])
        id = guild_id, Snowflake(data["id"])

        before, after = self._update_event(Member, data, id=id)

        guild = self._cache[Guild].get(guild_id)
        guild._member_ids.add(after.id)

        return before, after

    def guild_member_remove(self, data: dict) -> tuple:
        guild_id = Snowflake(data["guild_id"])
        id = guild_id, Snowflake(data["user"]["id"])

        member = self._delete_event(Member, id=id)
        if member is None:
            member = Member(**data)

        guild = self._cache[Guild].get(guild_id)
        guild._member_ids.remove(member.id)

        return (member,)

    def guild_members_chunk(self, data: dict) -> tuple:
        guild_members = events.GuildMembers(**data)
        cache = self._cache[Member]

        guild = self._cache[Guild].get(guild_members.guild_id)

        for member in guild_members.members:
            cache.merge(member, id=(guild_members.guild_id, member.id))
            guild._member_ids.add(member.id)

        return (guild_members,)