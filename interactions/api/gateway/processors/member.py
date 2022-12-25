from .base import BaseProcessor
from ...models import gw as events
from ...models.guild import Guild
from ...models.misc import Snowflake
from ...models.member import Member


class MemberProcessor(BaseProcessor):
    def guild_member_add(self, data: dict) -> tuple:
        guild_id = Snowflake(data["guild_id"])
        id = guild_id, Snowflake(data["id"])

        guild_member = self._create_event(events.GuildMember, data, id=id)

        member = self._create_event(Member, data, id=id)
        guild = self._cache[Guild].get(guild_id)
        guild.members.append(member)

        return (guild_member,)

    def guild_member_update(self, data: dict) -> tuple:
        guild_id = Snowflake(data["guild_id"])
        id = guild_id, Snowflake(data["id"])

        before, after = self._update_event(events.GuildMember, data, id=id)

        if self._cache[Member].get(id) is None:
            member = self._create_event(Member, data, id=id)
            guild = self._cache[Guild].get(guild_id)
            guild.members.append(member)

        return before, after

    def guild_member_remove(self, data: dict) -> tuple:
        guild_id = Snowflake(data["guild_id"])
        id = guild_id, Snowflake(data["user"]["id"])
        guild_member = self._delete_event(events.GuildMember, id=id)

        member = self._delete_event(Member, id=id)
        if member is not None:
            guild = self._cache[Guild].get(guild_id)

            # TODO: Remove this line after refactoring Guild
            [
                guild.members.pop(index)
                for index, _member in enumerate(guild.members)
                if _member.id == member.id
            ]

        return (guild_member,)

    def guild_members_chunk(self, data: dict) -> tuple:
        guild_members = events.GuildMembers(**data)
        cache = self._cache[Member]

        for member in guild_members.members:
            cache.add(member, (guild_members.guild_id, member.id))

        return (guild_members,)