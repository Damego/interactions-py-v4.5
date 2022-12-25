from .base import BaseProcessor
from ...models import gw as events
from ...models.guild import Guild, StageInstance
from ...models.misc import Snowflake
from ...models.channel import Channel, Thread


class ChannelProcessor(BaseProcessor):
    def channel_create(self, data: dict) -> tuple:
        channel = Channel(**data)
        self._cache[Channel].add(channel)

        guild = self._cache[Guild].get(channel.guild_id)
        guild.channels.append(channel)

        return (channel,)

    def channel_update(self, data: dict) -> tuple:
        return self._update_event(Channel, data)

    def channel_delete(self, data: dict) -> tuple:
        channel = self._delete_event(Channel, id=Snowflake(data["id"]))
        if channel is None:
            channel = Channel(**data)

        guild = self._cache[Guild].get(channel.guild_id)
        for index, _channel in guild.channels:
            if channel.id == _channel.id:
                guild.channels.pop(index)
                break

        return (channel,)

    def channel_pins_update(self, data: dict) -> tuple:
        return (events.ChannelPins(**data),)

    def thread_create(self, data: dict) -> tuple:
        thread = Thread(**data)
        self._cache[Thread].add(thread)

        guild = self._cache[Guild].get(thread.guild_id)
        guild.threads.append(thread)

        return (thread,)

    def thread_update(self, data: dict) -> tuple:
        return self._update_event(Thread, data)

    def thread_delete(self, data: dict) -> tuple:
        thread = self._delete_event(Thread, id=Snowflake(data["id"]))
        if thread is None:
            thread = Thread(**data)

        guild = self._cache[Guild].get(thread.guild_id)
        for index, _thread in guild.threads:
            if thread.id == _thread.id:
                guild.threads.pop(index)
                break

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