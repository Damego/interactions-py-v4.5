from typing import List, Union, Type, Tuple, Optional, TypeVar

from ..http import HTTPClient
from ..cache import Cache
from ..models import gw as events
from ..models.guild import Guild, StageInstance, Invite
from ..models.channel import Channel, Thread
from ..models.misc import Snowflake, IDMixin
from ..models.message import Message
from ..models.user import User
from ..models.member import Member
from ..models.role import Role
from ...utils.attrs_utils import DictSerializerMixin


# TODO:
#   Some create, update, delete events have same behavior. Need to split they into separate methods.
T = TypeVar("T")


class EventProcessor:
    def __init__(self, http: HTTPClient):
        self.http: HTTPClient = http
        self.cache: Cache = http.cache

    # Events with the same logic

    def _create_event(
        self,
        model: Type[T],
        data: dict,
        *,
        id: Union[Snowflake, Tuple[Snowflake, Snowflake]] = None
    ) -> T:
        obj = model(**data)
        self.cache[model].add(obj, id=id)

        return obj

    def _update_event(
        self,
        model: Type[T],
        data: dict,
        *,
        id: Union[Snowflake, Tuple[Snowflake, Snowflake]] = None
    ) -> Tuple[Optional[T], T]:
        obj: Union[DictSerializerMixin, IDMixin] = model(**data)
        cached_object: Union[DictSerializerMixin, IDMixin] = self.cache[model].get(id or obj.id)

        if cached_object:
            before = model(**cached_object._json, _client=self.http)
            cached_object.update(data)
        else:
            before = None
            cached_object = obj

        return before, cached_object

    def _delete_event(self, model: Type[T], *, id: Union[Tuple[Snowflake, Snowflake], Snowflake]) -> Optional[T]:
        return self.cache[model].pop(id)

    # Discord events

    def application_command_permissions_update(self, data: dict) -> tuple:
        return events.ApplicationCommandPermissions(**data),

    def auto_moderation_rule_create(self, data: dict) -> tuple:
        return events.AutoModerationRule(**data),

    def auto_moderation_rule_update(self, data: dict) -> tuple:
        return events.AutoModerationRule(**data),

    def auto_moderation_rule_delete(self, data: dict) -> tuple:
        return events.AutoModerationRule(**data),

    def auto_moderation_action_execution(self, data: dict) -> tuple:
        return events.AutoModerationAction(**data),

    def channel_create(self, data: dict) -> tuple:
        channel = Channel(**data)
        self.cache[Channel].add(channel)

        guild = self.cache[Guild].get(channel.guild_id)
        guild.channels.append(channel)

        return (channel,)

    def channel_update(self, data: dict) -> tuple:
        return self._update_event(Channel, data)

    def channel_delete(self, data: dict) -> tuple:
        channel = self._delete_event(Channel, id=Snowflake(data["id"]))
        if channel is None:
            channel = Channel(**data)

        guild = self.cache[Guild].get(channel.guild_id)
        for index, _channel in guild.channels:
            if channel.id == _channel.id:
                guild.channels.pop(index)
                break

        return (channel,)

    def channel_pins_update(self, data: dict) -> tuple:
        return (events.ChannelPins(**data),)

    def thread_create(self, data: dict) -> tuple:
        thread = Thread(**data)
        self.cache[Thread].add(thread)

        guild = self.cache[Guild].get(thread.guild_id)
        guild.threads.append(thread)

        return (thread,)

    def thread_update(self, data: dict) -> tuple:
        return self._update_event(Thread, data)

    def thread_delete(self, data: dict) -> tuple:
        thread = self._delete_event(Thread, id=Snowflake(data["id"]))
        if thread is None:
            thread = Thread(**data)

        guild = self.cache[Guild].get(thread.guild_id)
        for index, _thread in guild.threads:
            if thread.id == _thread.id:
                guild.threads.pop(index)
                break

        return (thread,)

    def thread_tuple_sync(self, data: dict) -> tuple:
        ...

    def thread_member_update(self, data: dict) -> tuple:
        ...

    def thread_members_update(self, data: dict) -> tuple:
        ...

    def guild_create(self, data: dict) -> tuple:
        guild = Guild(**data)
        self.cache[Guild].add(guild)

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
        # TODO: emojis not stores in the cache
        guild_emojis = events.GuildEmojis(**data)

        # guild_emojis.emojis contains all emojis of the guild

        guild = self.cache[Guild].get(guild_emojis.guild_id)
        guild.emojis.clear()
        guild.emojis.extend(guild_emojis.emojis)

        return guild_emojis,

    def guild_stickers_update(self, data: dict) -> tuple:
        # TODO: stickers not stores in the cache
        guild_stickers = events.GuildStickers(**data)

        # guild_stickers.stickers contains all stickers of the guild

        guild = self.cache[Guild].get(guild_stickers.guild_id)
        guild.stickers.clear()
        guild.stickers.extend(guild_stickers.stickers)

        return guild_stickers,

    def guild_integrations_update(self, data: dict) -> tuple:
        return events.GuildIntegrations(**data),

    def guild_member_add(self, data: dict) -> tuple:
        guild_id = Snowflake(data["guild_id"])
        id = guild_id, Snowflake(data["id"])

        guild_member = self._create_event(events.GuildMember, data, id=id)

        member = self._create_event(Member, data, id=id)
        guild = self.cache[Guild].get(guild_id)
        guild.members.append(member)

        return guild_member,

    def guild_member_update(self, data: dict) -> tuple:
        guild_id = Snowflake(data["guild_id"])
        id = guild_id, Snowflake(data["id"])

        before, after = self._update_event(events.GuildMember, data, id=id)

        if self.cache[Member].get(id) is None:
            member = self._create_event(Member, data, id=id)
            guild = self.cache[Guild].get(guild_id)
            guild.members.append(member)

        return before, after

    def guild_member_remove(self, data: dict) -> tuple:
        guild_id = Snowflake(data["guild_id"])
        id = guild_id, Snowflake(data["user"]["id"])
        guild_member = self._delete_event(events.GuildMember, id=id)

        member = self._delete_event(Member, id=id)
        if member is not None:
            guild = self.cache[Guild].get(guild_id)

            # TODO: Remove this line after refactoring Guild
            [guild.members.pop(index) for index, _member in enumerate(guild.members) if _member.id == member.id]

        return guild_member,

    def guild_members_chunk(self, data: dict) -> tuple:
        guild_members = events.GuildMembers(**data)
        cache = self.cache[Member]

        for member in guild_members.members:
            cache.add(member, (guild_members.guild_id, member.id))

        return guild_members,

    def guild_role_create(self, data: dict) -> tuple:
        role = self._create_event(Role, data["role"])

        return role,

    def guild_role_update(self, data: dict) -> tuple:
        return self._update_event(Role, data["role"])

    def guild_role_delete(self, data: dict) -> tuple:
        return self._delete_event(Role, id=data["role_id"]),

    def guild_scheduled_event_create(self, data: dict) -> tuple:
        return self._create_event(events.GuildScheduledEvent, data),

    def guild_scheduled_event_update(self, data: dict) -> tuple:
        return self._update_event(events.GuildScheduledEvent, data)

    def guild_scheduled_event_delete(self, data: dict) -> tuple:
        scheduled_event = self._delete_event(events.GuildScheduledEvent, id=Snowflake(data["id"]))
        if scheduled_event is None:
            scheduled_event = events.GuildScheduledEvent(**data)

        return scheduled_event,

    def guild_scheduled_event_user_add(self, data: dict) -> tuple:
        return events.GuildScheduledEventUser(**data),

    def guild_scheduled_event_user_remove(self, data: dict) -> tuple:
        return events.GuildScheduledEventUser(**data),

    def integration_create(self, data: dict) -> tuple:
        return events.Integration(**data),

    def integration_update(self, data: dict) -> tuple:
        return events.Integration(**data),

    def integration_delete(self, data: dict) -> tuple:
        return events.Integration(**data),

    def invite_create(self, data: dict) -> tuple:
        return Invite(**data),

    def invite_delete(self, data: dict) -> tuple:
        return Invite(**data),

    def message_create(self, data: dict) -> tuple:
        message = Message(**data)
        self.cache[Message].add(message)

        return (message,)

    def message_update(self, data: dict) -> tuple:
        return self._update_event(Message, data)

    def message_delete(self, data: dict) -> tuple:
        message = self.cache[Message].pop(Snowflake(data["id"]))
        if message is None:
            message = Message(**data)

        return (message,)

    def message_delete_bulk(self, data: dict) -> tuple:
        message_delete = events.MessageDelete(**data)
        message_ids = message_delete.ids
        cache = self.cache[Message]

        [cache.pop(message_id) for message_id in message_ids]

        return (message_delete,)

    def message_reaction_add(self, data: dict) -> tuple:
        message_reaction = events.MessageReaction(**data)
        return (message_reaction,)

    def message_reaction_remove(self, data: dict) -> tuple:
        return self.message_reaction_add(data)

    def message_reaction_remove_all(self, data: dict) -> tuple:
        message_reaction_remove = events.MessageReactionRemove(**data)
        return (message_reaction_remove,)

    def message_reaction_remove_emoji(self, data: dict) -> tuple:
        return self.message_reaction_remove_all(data)

    def presence_update(self, data: dict) -> tuple:
        presence = events.Presence(**data)
        self.cache[events.Presence].add(presence, presence.user.id)
        return (presence,)

    def stage_instance_create(self, data: dict) -> tuple:
        stage_instance = StageInstance(**data)
        self.cache[StageInstance].add(stage_instance)
        return (stage_instance,)

    def stage_instance_update(self, data: dict) -> tuple:
        return self._update_event(StageInstance, data)

    def stage_instance_delete(self, data: dict) -> tuple:
        stage_instance = self.cache[StageInstance].pop(Snowflake(data["id"]))
        if stage_instance is None:
            stage_instance = StageInstance(**data)

        return (stage_instance,)

    def user_update(self, data: dict) -> tuple:
        return self._update_event(User, data)

    def voice_state_update(self, data: dict) -> tuple:
        before, after = self._update_event(events.VoiceState, data)

        # User left from voice channel, so we don't need to store it in the cache anymore
        if after.channel_id is None:
            self.cache[events.VoiceState].pop(after.user_id)

        return before, after

    def webhooks_update(self, data: dict) -> tuple:
        webhooks = events.Webhooks(**data)
        return (webhooks,)

    # External events

    def guild_join(self, unavailable_guilds: List[str], guild: Guild) -> bool:
        guild_id = str(guild.id)

        if guild_id in unavailable_guilds:
            unavailable_guilds.remove(guild_id)
            return False

        return True
