from typing import Type, Union, Tuple, Optional, TypeVar

from ...http.client import HTTPClient
from ...cache import Cache
from ...models.misc import Snowflake, IDMixin
from ....utils.attrs_utils import DictSerializerMixin


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
        obj: Union[DictSerializerMixin, IDMixin] = model(**data)
        cached_object: Union[DictSerializerMixin, IDMixin] = self._cache[model].get(id or obj.id)

        if cached_object:
            before = model(**cached_object._json, _client=self._http)
            cached_object.update(data)
        else:
            before = None
            cached_object = obj

            self._cache[model].add(obj, id=id or obj.id)

        return before, cached_object

    def _delete_event(
        self, model: Type[T], *, id: Union[Tuple[Snowflake, Snowflake], Snowflake]
    ) -> Optional[T]:
        return self._cache[model].pop(id)