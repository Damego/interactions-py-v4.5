try:
    from orjson import dumps, loads
except ImportError:
    from json import dumps, loads

from asyncio import (
    FIRST_COMPLETED,
    Event,
    Lock,
    Task,
    TimeoutError,
    create_task,
    get_event_loop,
    get_running_loop,
    new_event_loop,
    wait,
    wait_for,
)
from contextlib import suppress
from sys import platform, version_info
from time import perf_counter
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Type, Union
from zlib import decompressobj

from aiohttp import ClientWebSocketResponse, WSMessage, WSMsgType

from ...base import __version__, get_logger
from ...client.enums import ComponentType, IntEnum, InteractionType, OptionType
from ...client.models import Option
from ...utils.missing import MISSING
from ..dispatch import Listener
from ..error import LibraryException
from ..http.client import HTTPClient
from ..models.flags import Intents
from ..models.presence import ClientPresence
from .heartbeat import _Heartbeat
from .processors import Processor
from .ratelimit import WSRateLimit

if TYPE_CHECKING:
    from ...client.context import _Context
    from ..cache import Cache

log = get_logger("gateway")

__all__ = ("WebSocketClient", "OpCodeType")


class OpCodeType(IntEnum):
    """
    An enumerable object for the Gateway's OPCODE result state.
    This is representative of the OPCodes generated by the WebSocket.

    .. note::
        Equivalent of `Gateway Opcodes <https://discord.com/developers/docs/topics/opcodes-and-status-codes#gateway-opcodes>`_ in the Discord API.
    """

    DISPATCH = 0
    HEARTBEAT = 1
    IDENTIFY = 2
    PRESENCE = 3
    VOICE_STATE = 4
    VOICE_PING = 5
    RESUME = 6
    RECONNECT = 7
    REQUEST_MEMBERS = 8
    INVALIDATE_SESSION = 9
    HELLO = 10
    HEARTBEAT_ACK = 11
    GUILD_SYNC = 12


class WebSocketClient:
    """
    A class representing the client's connection to the Gateway via. WebSocket.

    .. note ::
        The ``__heartbeat_event`` Event object is different from the one built in to the Heartbeater object.
        The latter is used to trace heartbeat acknowledgement.

    :ivar AbstractEventLoop _loop: The asynchronous event loop.
    :ivar Listener _dispatch: The built-in event dispatcher.
    :ivar WSRateLimit _ratelimiter: The websocket ratelimiter object.
    :ivar HTTPClient _http: The user-facing HTTP client.
    :ivar ClientWebSocketResponse _client: The WebSocket data of the connection.
    :ivar Event __closed: Whether the connection has been closed or not.
    :ivar dict _options: The connection options made during connection.
    :ivar Intents _intents: The gateway intents used for connection.
    :ivar dict _ready: The contents of the application returned when ready.
    :ivar _Heartbeat __heartbeater: The context state of a "heartbeat" made to the Gateway.
    :ivar Event __heartbeat_event: The state of the overall heartbeat process.
    :ivar Optional[List[Tuple[int]]] __shard: The shards used during connection.
    :ivar Optional[ClientPresence] __presence: The presence used in connection.
    :ivar Event ready: The ready state of the client as an ``asyncio.Event``.
    :ivar Task _task: The task containing the heartbeat manager process.
    :ivar bool __started: Whether the client has started.
    :ivar Optional[str] session_id: The ID of the ongoing session.
    :ivar Optional[int] sequence: The sequence identifier of the ongoing session.
    :ivar float _last_send: The latest time of the last send_packet function call since connection creation, in seconds.
    :ivar float _last_ack: The latest time of the last ``HEARTBEAT_ACK`` event since connection creation, in seconds.
    :ivar Optional[str] resume_url: The Websocket ratelimit URL for resuming connections, if any.
    :ivar Optional[str] ws_url: The Websocket URL for instantiating connections without resuming.
    :ivar Lock reconnect_lock: The lock used for reconnecting the client.
    :ivar Lock _closing_lock: The lock used for closing the client.
    :ivar Optional[Task] __stopping: The task containing stopping the client, if any.
    """

    __slots__ = (
        "_loop",
        "_dispatch",
        "__unavailable_guilds",
        "_ratelimiter",
        "_http",
        "_client",
        "_cache",
        "_event_processor",
        "__closed",  # placeholder to work with variables atm. its event variant of "_closed"
        "_options",
        "_intents",
        "_ready",
        "__heartbeater",
        "__shard",
        "__presence",
        "_zlib",
        "_task",
        "__heartbeat_event",
        "__started",
        "session_id",
        "sequence",
        "ready",
        "_last_send",
        "_last_ack",
        "resume_url",
        "ws_url",
        "reconnect_lock",
        "_closing_lock",
        "__stopping",
    )

    def __init__(
        self,
        intents: Intents,
        cache: "Cache",
        session_id: Optional[str] = MISSING,
        sequence: Optional[int] = MISSING,
        shards: Optional[List[Tuple[int]]] = MISSING,
        presence: Optional[ClientPresence] = MISSING,
    ) -> None:
        """
        :param str token: The token of the application for connecting to the Gateway.
        :param Intents intents: The Gateway intents of the application for event dispatch.
        :param Optional[str] session_id: The ID of the session if trying to reconnect. Defaults to ``None``.
        :param Optional[int] sequence: The identifier sequence if trying to reconnect. Defaults to ``None``.
        :param Optional[List[Tuple[int]]] shards: The list of shards for the application's initial connection, if provided. Defaults to ``None``.
        :param Optional[ClientPresence] presence: The presence shown on an application once first connected. Defaults to ``None``.
        """
        try:
            self._loop = get_event_loop() if version_info < (3, 10) else get_running_loop()
        except RuntimeError:
            self._loop = new_event_loop()
        self._dispatch: Listener = Listener()
        self.__unavailable_guilds = []

        self._ratelimiter = (
            WSRateLimit(loop=self._loop) if version_info < (3, 10) else WSRateLimit()
        )
        self.__heartbeater: _Heartbeat = _Heartbeat(
            loop=self._loop if version_info < (3, 10) else None
        )
        self._http: Optional[HTTPClient] = None
        self._cache: "Cache" = cache
        self._event_processor: Optional[Processor] = None

        self._client: Optional["ClientWebSocketResponse"] = None

        self.__closed: Event = Event(loop=self._loop) if version_info < (3, 10) else Event()
        self._options: dict = {
            "max_msg_size": 0,
            "timeout": 60,
            "autoclose": False,
            "compress": 0,
            "headers": {
                "User-Agent": f"DiscordBot (https://github.com/interactions-py/library {__version__}) "
            },
        }

        self._intents: Intents = intents
        self.__shard: Optional[List[Tuple[int]]] = None if shards is MISSING else shards
        self.__presence: Optional[ClientPresence] = None if presence is MISSING else presence

        self._task: Optional[Task] = None
        self.__heartbeat_event = Event(loop=self._loop) if version_info < (3, 10) else Event()
        self.__started: bool = False

        self.session_id: Optional[str] = None if session_id is MISSING else session_id
        self.sequence: Optional[str] = None if sequence is MISSING else sequence
        self.ready: Event = Event(loop=self._loop) if version_info < (3, 10) else Event()

        self._last_send: float = perf_counter()
        self._last_ack: float = perf_counter()

        self.resume_url: Optional[str] = None
        self.ws_url: Optional[str] = None
        self.reconnect_lock = Lock(loop=self._loop) if version_info < (3, 10) else Lock()

        self._closing_lock = Event(loop=self._loop) if version_info < (3, 10) else Event()

        self.__stopping: Optional[Task] = None

        self._zlib = decompressobj()

    @property
    def latency(self) -> float:
        """
        The latency of the connection, in seconds.
        """
        return self._last_ack - self._last_send

    async def run_heartbeat(self) -> None:
        """Controls the heartbeat manager. Do note that this shouldn't be executed by outside processes."""

        if self.__heartbeat_event.is_set():  # resets task of heartbeat event mgr loop
            # Because we're hardresetting the process every instance its called, also helps with recursion
            self.__heartbeat_event.clear()

        if not self.__heartbeater.event.is_set():  # resets task of heartbeat ack event
            self.__heartbeater.event.set()

        try:
            await self._manage_heartbeat()
        except Exception:
            self._closing_lock.set()
            log.exception("Heartbeater exception.")

    async def _manage_heartbeat(self) -> None:
        """Manages the heartbeat loop."""
        log.debug(f"Sending heartbeat every {self.__heartbeater.delay / 1000} seconds...")
        while not self.__heartbeat_event.is_set():

            log.debug("Sending heartbeat...")
            if not self.__heartbeater.event.is_set():
                log.debug("HEARTBEAT_ACK missing, reconnecting...")
                await self._reconnect(True)  # resume here.

            self.__heartbeater.event.clear()
            await self.__heartbeat()

            try:
                # wait for next iteration, accounting for latency
                await wait_for(
                    self.__heartbeat_event.wait(), timeout=self.__heartbeater.delay / 1000
                )
            except TimeoutError:
                continue  # Then we can check heartbeat ack this way and then like it autorestarts.
            else:
                return  # break loop because something went wrong.

    async def run(self) -> None:
        """
        Handles the client's connection with the Gateway.
        """

        if self._http is None:
            raise RuntimeError("Missed http client")

        if self._event_processor is None:
            self._event_processor = Processor(self._http)

        url = await self._http.get_gateway()
        self.ws_url = url
        self._client = await self._http._req._session.ws_connect(url, **self._options)

        data = await self.__receive_packet(True)  # First data is the hello packet.

        self.__heartbeater.delay = data["d"]["heartbeat_interval"]

        self._task = create_task(self.run_heartbeat())

        await self.__identify(self.__shard, self.__presence)

        self.__closed.set()
        self.__heartbeater.event.set()

        while True:
            if self.__stopping is None:
                self.__stopping = create_task(self._closing_lock.wait())
            _receive = create_task(self.__receive_packet())

            done, _ = await wait({self.__stopping, _receive}, return_when=FIRST_COMPLETED)
            # Using asyncio.wait to find which one reaches first, when its *closed* or when a message is
            # *received*

            if _receive in done:
                msg = await _receive
            else:
                await self.__stopping
                _receive.cancel()
                return

            if msg is not None:  # this can happen
                await self._handle_stream(msg)

    async def _handle_stream(self, stream: Dict[str, Any]):
        """
        Parses raw stream data recieved from the Gateway, including Gateway opcodes and events.

        .. note ::
            This should never be called directly.

        :param Dict[str, Any] stream: The packet stream to handle.
        """
        op: Optional[int] = stream.get("op")
        event: Optional[str] = stream.get("t")
        data: Optional[Dict[str, Any]] = stream.get("d")

        if seq := stream.get("s"):
            self.sequence = seq

        if op != OpCodeType.DISPATCH:
            log.debug(data)

            if op == OpCodeType.HEARTBEAT:
                await self.__heartbeat()
            if op == OpCodeType.HEARTBEAT_ACK:
                self._last_ack = perf_counter()
                log.debug("HEARTBEAT_ACK")
                self.__heartbeater.event.set()

            if op == OpCodeType.INVALIDATE_SESSION:
                log.debug("INVALID_SESSION")
                self.ready.clear()
                await self._reconnect(bool(data))

            if op == OpCodeType.RECONNECT:
                log.debug("RECONNECT")
                await self._reconnect(True)

        elif event == "RESUMED":
            log.debug(f"RESUMED (session_id: {self.session_id}, seq: {self.sequence})")
        elif event == "READY":
            self.ready.set()
            self._dispatch.dispatch("on_ready")
            self._ready = data
            self.__unavailable_guilds = [i["id"] for i in data["guilds"]]
            self.session_id = data["session_id"]
            self.resume_url = data["resume_gateway_url"]
            if not self.__started:
                self.__started = True
                self._dispatch.dispatch("on_start")
            log.debug(f"READY (session_id: {self.session_id}, seq: {self.sequence})")
        else:
            log.debug(f"{event}: {str(data).encode('utf-8')}")
            self._dispatch_event(event, data)

    async def wait_until_ready(self) -> None:
        """Waits for the client to become ready according to the Gateway."""
        await self.ready.wait()

    def _dispatch_event(self, event: str, data: dict) -> None:
        """
        Dispatches an event from the Gateway.

        :param str event: The name of the event.
        :param dict data: The data for the event.
        """
        self._dispatch.dispatch("raw_socket_create", event, data)

        if event == "INTERACTION_CREATE":
            self._dispatch_interaction_event(data)
        elif event not in {"TYPING_START", "VOICE_SERVER_UPDATE"}:
            self._dispatch_discord_event(event, data)

    def _dispatch_interaction_event(self, data: dict) -> None:
        """
        Dispatches interaction event from the Gateway.

        :param dict data: The data of interaction for the event.
        """
        if data.get("type") is None:
            return log.warning(
                "Context is being created for the interaction, but no type is specified. Skipping..."
            )

        _context = self.__contextualize(data)
        _name: str = ""
        __args: list = [_context]
        __kwargs: dict = {}

        if data["type"] == InteractionType.APPLICATION_COMMAND:
            _name = f"command_{_context.data.name}"

            if options := _context.data.options:
                for option in options:
                    _type = self.__option_type_context(
                        _context,
                        option.type.value,
                    )
                    if _type:
                        _type[option.value]._client = self._http
                        option.value = _type[option.value]
                    _option = self.__sub_command_context(option, _context)
                    __kwargs.update(_option)

            self._dispatch.dispatch("on_command", _context)
        elif data["type"] == InteractionType.MESSAGE_COMPONENT:
            _name = f"component_{_context.data.custom_id}"

            if values := _context.data.values:
                if _context.data.component_type.value not in {5, 6, 7, 8}:
                    __args.append(values)
                else:
                    _list = []  # temp storage for items
                    _data = self.__select_option_type_context(
                        _context, _context.data.component_type.value
                    )  # resolved.
                    for value in values:
                        _list.append(_data[value])
                    __args.append(_list)

            self._dispatch.dispatch("on_component", _context)
        elif data["type"] == InteractionType.APPLICATION_COMMAND_AUTOCOMPLETE:
            _name = f"autocomplete_{_context.data.name}"

            for option in _context.data.options:
                if option.type not in (
                    OptionType.SUB_COMMAND,
                    OptionType.SUB_COMMAND_GROUP,
                ):
                    if option.focused:
                        _name += f"_{option.name}"
                        __args.append(option.value)
                        break

                elif option.type == OptionType.SUB_COMMAND:
                    for _option in option.options:
                        if _option.focused:
                            _name += f"_{_option.name}"
                            __args.append(_option.value)
                            break

                elif option.type == OptionType.SUB_COMMAND_GROUP:
                    for _option in option.options:
                        for __option in _option.options:
                            if __option.focused:
                                _name += f"_{__option.name}"
                                __args.append(__option.value)
                                break
                        break

            self._dispatch.dispatch("on_autocomplete", _context)
        elif data["type"] == InteractionType.MODAL_SUBMIT:
            _name = f"modal_{_context.data.custom_id}"

            __args.extend(
                [
                    component.value
                    for action_row in _context.data.components
                    for component in action_row.components
                ]
            )

            self._dispatch.dispatch("on_modal", _context)

        self._dispatch.dispatch(_name, *__args, **__kwargs)
        self._dispatch.dispatch("on_interaction", _context)
        self._dispatch.dispatch("on_interaction_create", _context)

    def _dispatch_discord_event(self, event: str, data: dict) -> None:
        """
        Dispatches a discord event from the Gateway.

        :param str event: The name of the event.
        :param dict data: The data for the event.
        """
        name: str = event.lower()
        data["_client"] = self._http

        try:
            method = getattr(self._event_processor, name)
        except AttributeError:
            return log.warning(f"Got an unexpected event {event}.")

        args: tuple = method(data)

        # I don't like this but idk
        if name == "guild_create":
            guild_id = str(args[0].id)
            if guild_id in self.__unavailable_guilds:
                self.__unavailable_guilds.remove(guild_id)
            else:
                self._dispatch.dispatch("on_guild_join", *args)

        self._dispatch.dispatch(f"on_{name}", *args)

    def __contextualize(self, data: dict) -> "_Context":
        """
        Takes raw data given back from the Gateway
        and gives "context" based off of what it is.

        :param dict data: The data from the Gateway.
        :return: The context object.
        :rtype: Any
        """
        if data["type"] != InteractionType.PING:
            _context: str = ""

            if data["type"] in (
                InteractionType.APPLICATION_COMMAND,
                InteractionType.APPLICATION_COMMAND_AUTOCOMPLETE,
                InteractionType.MODAL_SUBMIT,
            ):
                _context = "CommandContext"
            elif data["type"] == InteractionType.MESSAGE_COMPONENT:
                _context = "ComponentContext"

            data["_client"] = self._http
            context: Type["_Context"] = getattr(__import__("interactions.client.context"), _context)

            return context(**data)

    def __sub_command_context(self, option: Option, context: "_Context") -> Union[Tuple[str], dict]:
        """
        Checks if an application command schema has sub commands
        needed for argument collection.

        :param Option option: The option object
        :param _Context context: The context to refer subcommands from.
        :return: A dictionary of the collected options, if any.
        :rtype: Union[Tuple[str], dict]
        """
        __kwargs: dict = {}

        def _check_auto(_option: Option) -> Optional[Tuple[str]]:
            return (_option.name, _option.value) if _option.focused else None

        check = _check_auto(option)

        if check:
            return check
        if options := option.options:
            if option.type == OptionType.SUB_COMMAND:
                __kwargs["sub_command"] = option.name

                for sub_option in options:
                    _check = _check_auto(sub_option)
                    _type = self.__option_type_context(
                        context,
                        sub_option.type,
                    )

                    if _type:
                        _type[sub_option.value]._client = self._http
                        sub_option.value = _type[sub_option.value]
                    if _check:
                        return _check

                    __kwargs[sub_option.name] = sub_option.value
            elif option.type == OptionType.SUB_COMMAND_GROUP:
                __kwargs["sub_command_group"] = option.name
                for _group_option in option.options:
                    _check_auto(_group_option)
                    __kwargs["sub_command"] = _group_option.name

                    for sub_option in _group_option.options:
                        _check = _check_auto(sub_option)
                        _type = self.__option_type_context(
                            context,
                            sub_option.type,
                        )

                        if _type:
                            _type[sub_option.value]._client = self._http
                            sub_option.value = _type[sub_option.value]
                        if _check:
                            return _check

                        __kwargs[sub_option.name] = sub_option.value

        elif option.type == OptionType.SUB_COMMAND:
            # sub_command_groups must have options so there is no extra check needed for those
            __kwargs["sub_command"] = option.name

        elif (name := option.name) is not None and (value := option.value) is not None:
            __kwargs[name] = value

        return __kwargs

    def __option_type_context(self, context: "_Context", type: int) -> dict:
        """
        Looks up the type of option respective to the existing
        option types.

        :param _Context context: The context to refer types from.
        :param int type: The option type.
        :return: The option type context.
        :rtype: dict
        """
        _resolved = {}
        if type == OptionType.USER.value:
            _resolved = (
                context.data.resolved.members if context.guild_id else context.data.resolved.users
            )
            if context.guild_id:
                with suppress(AttributeError):  # edge-case
                    for key in _resolved.keys():
                        _resolved[key]._extras["guild_id"] = context.guild_id
        elif type == OptionType.CHANNEL.value:
            _resolved = context.data.resolved.channels
        elif type == OptionType.ROLE.value:
            _resolved = context.data.resolved.roles
        elif type == OptionType.ATTACHMENT.value:
            _resolved = context.data.resolved.attachments
        elif type == OptionType.MENTIONABLE.value:
            _roles = context.data.resolved.roles if context.data.resolved.roles is not None else {}
            _members = (
                context.data.resolved.members if context.guild_id else context.data.resolved.users
            )
            if context.guild_id:
                with suppress(AttributeError):  # edge-case
                    for member in _members.values():
                        member._extras["guild_id"] = context.guild_id

            _resolved = _members | _roles

        return _resolved

    def __select_option_type_context(self, context: "_Context", type: int) -> dict:
        """
        Looks up the type of select menu respective to the existing option types. This is applicable for non-string
        select menus.

        :param context: The context to refer types from.
        :type context: object
        :param type: The option type.
        :type type: int
        :return: The select menu type context.
        :rtype: dict
        """

        _resolved = {}

        if type == ComponentType.USER_SELECT.value:
            _resolved = (
                context.data.resolved.members if context.guild_id else context.data.resolved.users
            )
            if context.guild_id:
                with suppress(AttributeError):  # edge-case
                    for key in _resolved.keys():
                        _resolved[key]._extras["guild_id"] = context.guild_id
        elif type == ComponentType.CHANNEL_SELECT.value:
            _resolved = context.data.resolved.channels
        elif type == ComponentType.ROLE_SELECT.value:
            _resolved = context.data.resolved.roles
        elif type == ComponentType.MENTIONABLE_SELECT.value:
            members = (
                context.data.resolved.members if context.guild_id else context.data.resolved.users
            )
            roles = context.data.resolved.roles

            if context.guild_id:
                with suppress(AttributeError):  # edge-case
                    for member in members.values():
                        member._extras["guild_id"] = context.guild_id

            _resolved = members | roles

        return _resolved

    async def _reconnect(self, to_resume: bool, code: Optional[int] = 1012) -> None:
        """
        Restarts the client's connection and heartbeat with the Gateway.
        """

        self.ready.clear()

        async with self.reconnect_lock:
            self.__closed.clear()

            if self._client is not None:
                await self._client.close(code=code)

            self._client = None

            self._zlib = decompressobj()

            # We need to check about existing heartbeater tasks for edge cases.

            if self._task:
                self._task.cancel()
                if self.__heartbeat_event.is_set():
                    self.__heartbeat_event.clear()  # Because we're hardresetting the process

            if not to_resume:
                url = self.ws_url if self.ws_url else await self._http.get_gateway()
            else:
                url = f"{self.resume_url}?v=10&encoding=json&compress=zlib-stream"

            self._client = await self._http._req._session.ws_connect(url, **self._options)

            data = await self.__receive_packet(True)  # First data is the hello packet.

            self.__heartbeater.delay = data["d"]["heartbeat_interval"]

            self._task = create_task(self.run_heartbeat())

            if not to_resume:
                await self.__identify(self.__shard, self.__presence)
            else:
                await self.__resume()

            self.__closed.set()
            self.__heartbeat_event.set()

    async def __receive_packet(self, ignore_lock: bool = False) -> Optional[Dict[str, Any]]:
        """
        Receives a stream of packets sent from the Gateway in an async process.

        :return: The packet stream.
        :rtype: Optional[Dict[str, Any]]
        """

        buffer = bytearray()

        while True:

            if not ignore_lock:
                # meaning if we're reconnecting or something because of tasks
                await self.__closed.wait()

            packet: WSMessage = await self._client.receive()

            if packet.type == WSMsgType.CLOSE:
                log.debug(f"Disconnecting from gateway = {packet.data}::{packet.extra}")

                if packet.data >= 4000:
                    # This means that the error code is 4000+, which may signify Discord-provided error codes.

                    raise LibraryException(packet.data)

                if ignore_lock:
                    raise LibraryException(
                        message="Discord unexpectedly wants to close the WS on receiving by force.",
                        severity=50,
                    )

                await self._reconnect(packet.data != 1000, packet.data)
                continue

            elif packet.type == WSMsgType.CLOSED:
                # We need to wait/reconnect depending about other event holders.

                if ignore_lock:
                    raise LibraryException(
                        message="Discord unexpectedly closed on receiving by force.", severity=50
                    )

                if not self.__closed.is_set():
                    await self.__closed.wait()

                    # Edge case on force reconnecting if we dont
                else:
                    await self._reconnect(True)

            elif packet.type == WSMsgType.CLOSING:

                if ignore_lock:
                    raise LibraryException(
                        message="Discord unexpectedly closing on receiving by force.", severity=50
                    )

                await self.__closed.wait()
                continue

            if packet.data is None:
                continue  # We just loop it over because it could just be processing something.

            if isinstance(packet.data, bytes):
                buffer.extend(packet.data)

                if len(packet.data) < 4 or packet.data[-4:] != b"\x00\x00\xff\xff":
                    # buffer isn't done we need to wait
                    continue

                msg = self._zlib.decompress(buffer)
                msg = msg.decode("utf-8")
            else:
                msg = packet.data

            try:
                _msg = loads(msg)
            except Exception as e:
                import traceback

                log.debug(
                    f'Error serialising message: {"".join(traceback.format_exception(type(e), e, e.__traceback__))}.'
                )
                # There's an edge case when the packet's None... or some other deserialisation error.
                # Instead of raising an exception, we just log it to debug, so it doesn't annoy end user's console logs.
                _msg = None

            return _msg

    async def _send_packet(self, data: Dict[str, Any]) -> None:
        """
        Sends a packet to the Gateway.

        :param Dict[str, Any] data: The data to send to the Gateway.
        """
        _data = dumps(data) if isinstance(data, dict) else data
        packet: str = _data.decode("utf-8") if isinstance(_data, bytes) else _data
        log.debug(packet)

        if data["op"] in {OpCodeType.IDENTIFY.value, OpCodeType.RESUME.value}:
            # This can't use the reconnect lock *because* its already referenced in
            # self._reconnect(), hence an infinite hang.

            if self._client is not None:
                self._last_send = perf_counter()

                await self._client.send_str(packet)
        else:
            async with self.reconnect_lock:  # needs to lock while it reconnects.

                if data["op"] != OpCodeType.HEARTBEAT.value:
                    # This is because the ratelimiter limits already accounts for this.
                    await self._ratelimiter.block()

                if self._client is not None:  # this mitigates against another edge case.
                    self._last_send = perf_counter()

                    await self._client.send_str(packet)

    async def __identify(
        self, shard: Optional[List[Tuple[int]]] = None, presence: Optional[ClientPresence] = None
    ) -> None:
        """
        Sends an ``IDENTIFY`` packet to the gateway.

        :param Optional[List[Tuple[int]]] shard: The shard ID to identify under.
        :param Optional[ClientPresence] presence: The presence to change the bot to on identify.
        """
        self.__shard = shard
        self.__presence = presence
        payload: dict = {
            "op": OpCodeType.IDENTIFY.value,
            "d": {
                "token": self._http.token,
                "intents": self._intents.value,
                "properties": {
                    "os": platform,
                    "browser": "interactions.py",
                    "device": "interactions.py",
                },
                "compress": True,
            },
        }

        if isinstance(shard, List) and len(shard) >= 1:
            payload["d"]["shard"] = shard
        if isinstance(presence, ClientPresence):
            payload["d"]["presence"] = presence._json

        log.debug(f"IDENTIFYING: {payload}")
        await self._send_packet(payload)
        log.debug("IDENTIFY")

    async def __resume(self) -> None:
        """Sends a ``RESUME`` packet to the gateway."""
        payload: dict = {
            "op": OpCodeType.RESUME.value,
            "d": {"token": self._http.token, "seq": self.sequence, "session_id": self.session_id},
        }
        log.debug(f"RESUMING: {payload}")
        await self._send_packet(payload)
        log.debug("RESUME")

    async def __heartbeat(self) -> None:
        """Sends a ``HEARTBEAT`` packet to the gateway."""
        payload: dict = {"op": OpCodeType.HEARTBEAT.value, "d": self.sequence}
        await self._send_packet(payload)
        log.debug("HEARTBEAT")

    @property
    def shard(self) -> Optional[List[Tuple[int]]]:
        """Returns the current shard"""
        return self.__shard

    @property
    def presence(self) -> Optional[ClientPresence]:
        """Returns the current presence."""
        return self.__presence

    async def _update_presence(self, presence: ClientPresence) -> None:
        """
        Sends an ``UPDATE_PRESENCE`` packet to the gateway.

        .. note::
            There is a ratelimit to using this method (5 per minute).
            As there's no gateway ratelimiter yet, breaking this ratelimit
            will force your bot to disconnect.

        :param ClientPresence presence: The presence to change the bot to on identify.
        """
        _presence = presence._json
        payload: dict = {"op": OpCodeType.PRESENCE.value, "d": _presence}
        await self._send_packet(payload)
        log.debug(f"UPDATE_PRESENCE: {_presence}")
        self.__presence = presence

    async def request_guild_members(
        self,
        guild_id: int,
        limit: int,
        query: Optional[str] = None,
        presences: Optional[bool] = None,
        user_ids: Optional[Union[int, List[int]]] = None,
        nonce: Optional[str] = None,
    ) -> None:
        """Sends an ``REQUEST_MEMBERS`` packet to the gateway.

        :param int guild_id: ID of the guild to get members for.
        :param int limit: Maximum number of members to send matching the 'query' parameter. Required when specifying 'query'.
        :param Optional[str] query: String that username starts with.
        :param Optional[bool] presences: Used to specify if we want the presences of the matched members.
        :param Optional[Union[int, List[int]]] user_ids: Used to specify which users you wish to fetch.
        :param Optional[str] nonce: Nonce to identify the Guild Members Chunk response.
        """
        data: dict = {"guild_id": guild_id, "query": query or "", "limit": limit}

        if presences is not None:
            data["presences"] = presences
        if user_ids is not None:
            data["user_ids"] = user_ids
        if nonce is not None:
            data["nonce"] = nonce

        payload: dict = {"op": OpCodeType.REQUEST_MEMBERS.value, "d": data}

        await self._send_packet(payload)
        log.debug(f"REQUEST_MEMBERS: {payload}")

    async def close(self) -> None:
        """
        Closes the current connection.
        """
        if self._client:
            await self._client.close()
        self.__closed.set()
