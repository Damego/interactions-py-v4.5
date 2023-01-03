from collections import defaultdict
from typing import (
    TYPE_CHECKING,
    Dict,
    Generic,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    overload,
)

import interactions

if TYPE_CHECKING:
    from .models import Snowflake

    Key = TypeVar("Key", Snowflake, Tuple[Snowflake, Snowflake])

__all__ = (
    "Storage",
    "Cache",
)

_T = TypeVar("_T")
_P = TypeVar("_P")


class Storage(Generic[_T]):
    """
    A class representing a set of items stored as a cache state.

    :ivar Dict[Union[Snowflake, Tuple[Snowflake, Snowflake]], Any] values: The list of items stored.
    """

    __slots__ = ("values",)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} object containing {len(self.values)} items.>"

    def __init__(self, limit: Optional[int] = None) -> None:
        """
        :param Optional[int] limit: The maximum number of items to store
        """
        if not limit:
            limit = float("inf")
        self.values: interactions.LRUDict["Key", _T] = interactions.LRUDict(max_items=limit)

    def merge(self, item: _T, id: Optional["Key"] = None) -> None:
        """
        Merges new data of an item into an already present item of the cache

        :param Any item: The item to merge.
        :param Optional[Union[Snowflake, Tuple[Snowflake, Snowflake]]] id: The unique id of the item.
        """
        if not self.values.get(id or item.id):
            return self.add(item, id)

        _id = id or item.id
        old_item = self.values[_id]

        for attrib in item.__slots__:
            if getattr(old_item, attrib) and not getattr(item, attrib):
                continue
                # we can only assume that discord did not provide it, falsely deleting is worse than not deleting
            if getattr(old_item, attrib) != getattr(item, attrib):

                if isinstance(getattr(item, attrib), list) and not isinstance(
                    getattr(old_item, attrib), list
                ):  # could be None
                    setattr(old_item, attrib, [])
                if isinstance(getattr(old_item, attrib), list):
                    if _attrib := getattr(item, attrib):
                        for value in _attrib:
                            old_item_attrib = getattr(old_item, attrib)
                            if value not in old_item_attrib:
                                old_item_attrib.append(value)
                            setattr(old_item, attrib, old_item_attrib)
                else:
                    setattr(old_item, attrib, getattr(item, attrib))

    def add(self, item: _T, id: Optional["Key"] = None) -> None:
        """
        Adds a new item to the storage.

        :param Any item: The item to add.
        :param Optional[Union[Snowflake, Tuple[Snowflake, Snowflake]]] id: The unique id of the item.
        """
        self.values[id or item.id] = item

    @overload
    def get(self, id: "Key") -> Optional[_T]:
        ...

    @overload
    def get(self, id: "Key", default: _P) -> Union[_T, _P]:
        ...

    def get(self, id: "Key", default: Optional[_P] = None) -> Union[_T, _P, None]:
        """
        Gets an item from the storage.

        :param Union[Snowflake, Tuple[Snowflake, Snowflake]] id: The ID of the item.
        :param Optional[Any] default: The default value to return if the item is not found.
        :return: The item from the storage if any.
        :rtype: Optional[Any]
        """
        return self.values.get(id, default)

    def update(self, data: Dict["Key", _T]):
        """
        Updates multiple items from the storage.

        :param dict data: The data to update with.
        """
        self.values.update(data)

    @overload
    def pop(self, key: "Key") -> Optional[_T]:
        ...

    @overload
    def pop(self, key: "Key", default: _P) -> Union[_T, _P]:
        ...

    def pop(self, key: "Key", default: Optional[_P] = None) -> Union[_T, _P, None]:
        return self.values.pop(key, default)

    @property
    def view(self) -> List[dict]:
        """Views all items from storage.

        :return: The items stored.
        :rtype: List[dict]
        """
        return [v._json for v in self.values.values()]

    def __getitem__(self, item: "Key") -> _T:
        return self.values.__getitem__(item)

    def __setitem__(self, key: "Key", value: _T) -> None:
        return self.values.__setitem__(key, value)

    def __delitem__(self, key: "Key") -> None:
        return self.values.__delitem__(key)


class Cache:
    """
    A class representing the cache.
    This cache collects all of the HTTP requests made for
    the represented instances of the class.

    :ivar defaultdict[Type, Storage] storages: A dictionary denoting the Type and the objects that correspond to the Type.
    """

    __slots__ = ("_http", "storages", "config")

    def __init__(self, config: Dict[Type[_T], int] = None) -> None:
        self._http: interactions.HTTPClient
        self.storages: Dict[Type[_T], Storage[_T]] = defaultdict(Storage)

        if config is not None:
            for type_, limit in config.items():
                self.storages[type_] = Storage(limit)

    def __getitem__(self, item: Type[_T]) -> Storage[_T]:
        return self.storages[item]

    def _get_object(
        self,
        type: Type[_T],
        object_id: Union[
            interactions.Snowflake, Tuple[interactions.Snowflake, interactions.Snowflake]
        ],
    ) -> _T:
        return self.storages[type].get(object_id)

    def _add_object(
        self,
        data: dict,
        type: Type[_T],
        object_id: Union[
            interactions.Snowflake, Tuple[interactions.Snowflake, interactions.Snowflake]
        ] = None,
    ) -> _T:
        object = type(**data, _client=self._http)
        self.storages[type].merge(object, object_id)
        return object

    def get_guild(self, guild_id: interactions.Snowflake) -> interactions.Guild:
        return self._get_object(interactions.Guild, guild_id)

    def add_guild(self, data: dict) -> interactions.Guild:
        return self._add_object(data, interactions.Guild)

    def remove_guild(self, guild_id: interactions.Snowflake) -> Optional[interactions.Guild]:
        return self.storages[interactions.Guild].pop(guild_id)

    def get_channel(self, channel_id: interactions.Snowflake) -> Optional[interactions.Channel]:
        return self._get_object(interactions.Channel, channel_id)

    def add_channel(self, data: dict, guild_id: interactions.Snowflake) -> interactions.Channel:
        channel = self._add_object(data, interactions.Channel)

        if guild := self.get_guild(guild_id):
            guild._channel_ids.add(channel.id)

        return channel

    def add_channels(self, data: List[dict], guild_id: interactions.Snowflake):
        return [self.add_channel(channel, guild_id) for channel in data]

    def remove_channel(
        self, channel_id: interactions.Snowflake, guild_id: interactions.Snowflake
    ) -> Optional[interactions.Channel]:
        channel = self.storages[interactions.Channel].pop(channel_id)

        if guild := self.get_guild(guild_id):
            guild._channel_ids.remove(channel_id)

        return channel

    def get_thread(self, thread_id: interactions.Snowflake) -> Optional[interactions.Thread]:
        return self._get_object(interactions.Thread, thread_id)

    def add_thread(self, data: dict, guild_id: interactions.Snowflake) -> interactions.Thread:
        thread = self._add_object(data, interactions.Thread)

        if guild := self.get_guild(guild_id):
            guild._thread_ids.add(thread.id)

        return thread

    def add_threads(
        self, data: List[dict], guild_id: interactions.Snowflake
    ) -> List[interactions.Thread]:
        return [self.add_thread(thread, guild_id) for thread in data]

    def remove_thread(
        self, thread_id: interactions.Snowflake, guild_id: interactions.Snowflake
    ) -> Optional[interactions.Thread]:
        thread = self.storages[interactions.Thread].pop(thread_id)

        if guild := self.get_guild(guild_id):
            guild._thread_ids.remove(thread_id)

        return thread

    def get_member(
        self, guild_id: interactions.Snowflake, member_id: interactions.Snowflake
    ) -> Optional[interactions.Member]:
        return self._get_object(interactions.Member, object_id=(guild_id, member_id))

    def add_member(self, data: dict, guild_id: interactions.Snowflake) -> interactions.Member:
        _id = (guild_id, interactions.Snowflake(data["user"]["id"]))
        member = self._add_object(data, interactions.Member, object_id=_id)

        if guild := self.get_guild(guild_id):
            guild._member_ids.add(member.id)

        return member

    def add_members(
        self, data: List[dict], guild_id: interactions.Snowflake
    ) -> List[interactions.Member]:
        return [self.add_member(member, guild_id) for member in data]

    def remove_member(self, user_id: interactions.Snowflake, guild_id: interactions.Snowflake):
        member = self.storages[interactions.Member].pop((guild_id, user_id))

        if guild := self.get_guild(guild_id):
            guild._member_ids.remove(user_id)

        return member

    def get_role(self, role_id: interactions.Snowflake) -> Optional[interactions.Role]:
        return self._get_object(interactions.Role, role_id)

    def add_role(self, data: dict, guild_id: interactions.Snowflake) -> interactions.Role:
        role = self._add_object(data, interactions.Role)

        if guild := self.get_guild(guild_id):
            guild._role_ids.add(role.id)

        return role

    def add_roles(
        self, data: List[dict], guild_id: interactions.Snowflake
    ) -> List[interactions.Role]:
        return [self.add_role(role, guild_id) for role in data]

    def remove_role(
        self, role_id: interactions.Snowflake, guild_id: interactions.Snowflake
    ) -> Optional[interactions.Role]:
        role = self.storages[interactions.Role].pop(role_id)

        if guild := self.get_guild(guild_id):
            guild._role_ids.remove(role_id)

        return role

    def get_emoji(self, emoji_id: interactions.Snowflake) -> Optional[interactions.Emoji]:
        return self._get_object(interactions.Emoji, object_id=emoji_id)

    def add_emoji(self, data: dict, guild_id: interactions.Snowflake) -> interactions.Emoji:
        return self._add_object(data, interactions.Emoji, guild_id)

    def add_emojis(
        self, data: List[dict], guild_id: interactions.Snowflake
    ) -> List[interactions.Emoji]:
        return [self.add_emoji(emoji, guild_id) for emoji in data]

    def remove_emoji(
        self, emoji_id: interactions.Snowflake, guild_id: interactions.Snowflake
    ) -> Optional[interactions.Emoji]:
        emoji = self.storages[interactions.Emoji].pop(emoji_id)

        if guild := self.get_guild(guild_id):
            guild._emoji_ids.remove(emoji_id)

        return emoji

    def get_sticker(self, sticker_id: interactions.Snowflake) -> Optional[interactions.Sticker]:
        return self._get_object(interactions.Sticker, object_id=sticker_id)

    def add_sticker(self, data: dict, guild_id: interactions.Snowflake) -> interactions.Sticker:
        return self._add_object(data, interactions.Sticker, guild_id)

    def add_stickers(
        self, data: List[dict], guild_id: interactions.Snowflake
    ) -> List[interactions.Sticker]:
        return [self.add_sticker(sticker, guild_id) for sticker in data]

    def remove_sticker(
        self, sticker_id: interactions.Snowflake, guild_id: interactions.Snowflake
    ) -> Optional[interactions.Emoji]:
        sticker = self.storages[interactions.Emoji].pop(sticker_id)

        if guild := self.get_guild(guild_id):
            guild._sticker_ids.remove(sticker_id)

        return sticker
