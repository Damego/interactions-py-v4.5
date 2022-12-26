from ...models import gw as events
from ...models.misc import Snowflake
from .base import BaseProcessor


class ScheduledEventProcessor(BaseProcessor):
    def guild_scheduled_event_create(self, data: dict) -> tuple:
        return (self._create_event(events.GuildScheduledEvent, data),)

    def guild_scheduled_event_update(self, data: dict) -> tuple:
        return self._update_event(events.GuildScheduledEvent, data)

    def guild_scheduled_event_delete(self, data: dict) -> tuple:
        scheduled_event = self._delete_event(events.GuildScheduledEvent, id=Snowflake(data["id"]))
        if scheduled_event is None:
            scheduled_event = events.GuildScheduledEvent(**data)

        return (scheduled_event,)

    def guild_scheduled_event_user_add(self, data: dict) -> tuple:
        return (events.GuildScheduledEventUser(**data),)

    def guild_scheduled_event_user_remove(self, data: dict) -> tuple:
        return (events.GuildScheduledEventUser(**data),)
