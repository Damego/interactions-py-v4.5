from ...models import gw as events
from ...models.channel import Channel, Thread
from ...models.guild import Guild, StageInstance
from ...models.misc import Snowflake
from .base import BaseProcessor


class ChannelProcessor(BaseProcessor):
    def channel_create(self, data: dict) -> tuple:
        channel = self._create_event(Channel, data)

        guild = self._cache[Guild].get(channel.guild_id)
        guild._channel_ids.add(channel.id)

        return (channel,)

    def channel_update(self, data: dict) -> tuple:
        before, after = self._update_event(Channel, data)

        guild = self._cache[Guild].get(after.guild_id)
        guild._channel_ids.add(after.id)

        return before, after

    def channel_delete(self, data: dict) -> tuple:
        channel = self._delete_event(Channel, id=Snowflake(data["id"]))
        if channel is None:
            channel = Channel(**data)

        guild = self._cache[Guild].get(channel.guild_id)
        guild._channel_ids.remove(channel.id)

        return (channel,)

    def channel_pins_update(self, data: dict) -> tuple:
        return (events.ChannelPins(**data),)

    def thread_create(self, data: dict) -> tuple:
        thread = self._create_event(Thread, data)

        guild = self._cache[Guild].get(thread.guild_id)
        guild._thread_ids.add(thread.id)

        return (thread,)

    def thread_update(self, data: dict) -> tuple:
        before, after = self._update_event(Thread, data)

        guild = self._cache[Guild].get(after.guild_id)
        guild._thread_ids.add(after.id)

        return before, after

    def thread_delete(self, data: dict) -> tuple:
        thread = self._delete_event(Thread, id=Snowflake(data["id"]))
        if thread is None:
            thread = Thread(**data)

        guild = self._cache[Guild].get(thread.guild_id)
        guild._channel_ids.remove(thread.id)

        return (thread,)

    def thread_tuple_sync(self, data: dict) -> tuple:
        return (events.ThreadList(**data),)

    def thread_member_update(self, data: dict) -> tuple:
        return (events.ThreadMember(**data),)

    def thread_members_update(self, data: dict) -> tuple:
        return (events.ThreadMembers(**data),)

    def stage_instance_create(self, data: dict) -> tuple:
        stage_instance = StageInstance(**data)
        self._cache[StageInstance].add(stage_instance)
        return (stage_instance,)

    def stage_instance_update(self, data: dict) -> tuple:
        return self._update_event(StageInstance, data)

    def stage_instance_delete(self, data: dict) -> tuple:
        stage_instance = self._cache[StageInstance].pop(Snowflake(data["id"]))
        if stage_instance is None:
            stage_instance = StageInstance(**data)

        return (stage_instance,)
