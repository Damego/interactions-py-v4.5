from typing import Optional, Tuple, Type, TypeVar, Union

from ....utils.attrs_utils import DictSerializerMixin
from ...cache import Cache
from ...http.client import HTTPClient
from ...models.misc import IDMixin, Snowflake

T = TypeVar("T")


class BaseProcessor:
    def __init__(self, http: HTTPClient):
        self._http: HTTPClient = http
        self._cache: Cache = http.cache

    def _create_event(
        self,
        model: Type[T],
        data: dict,
        *,
        id: Union[Snowflake, Tuple[Snowflake, Snowflake]] = None
    ) -> T:
        obj = model(**data)
        self._cache[model].add(obj, id=id)

        return obj

    def _update_event(
        self,
        model: Type[T],
        data: dict,
        *,
        id: Union[Snowflake, Tuple[Snowflake, Snowflake]] = None
    ) -> Tuple[Optional[T], T]:
        obj: DictSerializerMixin = model(**data)
        _id = obj.id if hasattr(obj, "id") and not id else id
        cached_object: DictSerializerMixin = self._cache[model].get(_id)

        if cached_object:
            before = model(**cached_object._json, _client=self._http)
            cached_object.update(data)
        else:
            before = None
            cached_object = obj

            self._cache[model].add(obj, id=_id)

        return before, cached_object

    def _delete_event(
        self, model: Type[T], data: dict, *, id: Union[Tuple[Snowflake, Snowflake], Snowflake]
    ) -> T:
        obj = self._cache[model].pop(id)
        if obj is None:
            obj = model(**data)

        return obj
