from ...models import gw as events
from ...models.message import Message
from ...models.misc import Snowflake
from .base import BaseProcessor


class MessageProcessor(BaseProcessor):
    def message_create(self, data: dict) -> tuple:
        return self._create_event(Message, data),

    def message_update(self, data: dict) -> tuple:
        return self._update_event(Message, data)

    def message_delete(self, data: dict) -> tuple:
        message = self._delete_event(Message, id=Snowflake(data["id"]))
        if message is None:
            message = Message(**data)

        return (message,)

    def message_delete_bulk(self, data: dict) -> tuple:
        message_delete = events.MessageDelete(**data)
        message_ids = message_delete.ids
        cache = self._cache[Message]

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
