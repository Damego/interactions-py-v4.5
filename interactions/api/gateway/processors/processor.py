from ...http.client import HTTPClient
from .channel import ChannelProcessor
from .guild import GuildProcessor
from .member import MemberProcessor
from .message import MessageProcessor
from .misc import MiscProcessor
from .scheduled_event import ScheduledEventProcessor


class Processor(
    ChannelProcessor,
    GuildProcessor,
    MemberProcessor,
    MessageProcessor,
    MiscProcessor,
    ScheduledEventProcessor,
):
    def __init__(self, http: HTTPClient):
        super().__init__(http)
