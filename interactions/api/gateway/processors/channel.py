from ...models import gw as events
from ...models.channel import Channel, Thread
from ...models.guild import StageInstance
from ...models.misc import Snowflake
from .base import BaseProcessor


class ChannelProcessor(BaseProcessor):
    def channel_create(self, data: dict) -> tuple:
        channel = self._cache.add_channel(data)
        return (channel,)

    def channel_update(self, data: dict) -> tuple:
        before, after = self._update_event(Channel, data)

        if guild := self._cache.get_guild(after.guild_id):
            guild._channel_ids.add(after.id)

        return before, after

    def channel_delete(self, data: dict) -> tuple:
        channel = self._delete_event(Channel, data, id=Snowflake(data["id"]))

        if guild := self._cache.get_guild(channel.guild_id):
            guild._channel_ids.remove(channel.id)

        return (channel,)

    def channel_pins_update(self, data: dict) -> tuple:
        return (events.ChannelPins(**data),)

    def thread_create(self, data: dict) -> tuple:
        thread = self._cache.add_thread(data)

        return (thread,)

    def thread_update(self, data: dict) -> tuple:
        before, after = self._update_event(Thread, data)

        if guild := self._cache.get_guild(after.guild_id):
            guild._thread_ids.add(after.id)

        return before, after

    def thread_delete(self, data: dict) -> tuple:
        thread = self._delete_event(Thread, data, id=Snowflake(data["id"]))

        if guild := self._cache.get_guild(thread.guild_id):
            guild._channel_ids.remove(thread.id)

        return (thread,)

    def thread_tuple_sync(self, data: dict) -> tuple:
        return (events.ThreadList(**data),)

    def thread_member_update(self, data: dict) -> tuple:
        return (events.ThreadMember(**data),)

    def thread_members_update(self, data: dict) -> tuple:
        return (events.ThreadMembers(**data),)

    def stage_instance_create(self, data: dict) -> tuple:
        stage_instance = self._create_event(StageInstance, data)

        return (stage_instance,)

    def stage_instance_update(self, data: dict) -> tuple:
        return self._update_event(StageInstance, data)

    def stage_instance_delete(self, data: dict) -> tuple:
        stage_instance = self._delete_event(Thread, data)

        return (stage_instance,)
