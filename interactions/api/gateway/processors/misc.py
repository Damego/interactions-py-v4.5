from ...models import gw as events
from ...models.user import User
from .base import BaseProcessor


class MiscProcessor(BaseProcessor):

    # Application command permissions

    def application_command_permissions_update(self, data: dict) -> tuple:
        return (events.ApplicationCommandPermissions(**data),)

    # Auto moderation

    def auto_moderation_rule_create(self, data: dict) -> tuple:
        return (events.AutoModerationRule(**data),)

    def auto_moderation_rule_update(self, data: dict) -> tuple:
        return (events.AutoModerationRule(**data),)

    def auto_moderation_rule_delete(self, data: dict) -> tuple:
        return (events.AutoModerationRule(**data),)

    def auto_moderation_action_execution(self, data: dict) -> tuple:
        return (events.AutoModerationAction(**data),)

    # User

    def presence_update(self, data: dict) -> tuple:
        presence = events.Presence(**data)
        self._cache[events.Presence].add(presence, presence.user.id)
        return (presence,)

    def user_update(self, data: dict) -> tuple:
        return self._update_event(User, data)
