from typing import Optional, List, Union, Tuple, TYPE_CHECKING

from ...utils.missing import MISSING
from ...api.models.flags import MessageFlags

if TYPE_CHECKING:
    from .component import ActionRow, Button, SelectMenu
    from ...api.models.misc import File, AllowedMentions
    from ...api.models.message import Attachment, Embed, Sticker


class Messageable:
    @staticmethod
    def _prepare_payload(
        *,
        content: Optional[str] = MISSING,
        components: Optional[
            Union[
                "ActionRow",
                "Button",
                "SelectMenu",
                List["ActionRow"],
                List["Button"],
                List["SelectMenu"],
            ]
        ] = MISSING,
        tts: Optional[bool] = MISSING,
        attachments: Optional[List["Attachment"]] = MISSING,
        files: Optional[Union["File", List["File"]]] = MISSING,
        embeds: Optional[Union["Embed", List["Embed"]]] = MISSING,
        allowed_mentions: Optional["AllowedMentions"] = MISSING,
        flags: Optional[MessageFlags] = MISSING,
        stickers: Optional[Union["Sticker", List["Sticker"]]] = MISSING
    ) -> Tuple[dict, List["File"]]:
        payload = {}

        if content is not MISSING:
            payload["content"] = content
        if components is not MISSING:
            from .component import _build_components

            payload["components"] = _build_components(components)
        if tts is not MISSING:
            payload["tts"] = tts
        if embeds is not MISSING:
            payload["embeds"] = [embed._json for embed in embeds] if isinstance(embeds, list) else [embeds._json]
        if allowed_mentions is not MISSING:
            payload["allowed_mentions"] = allowed_mentions._json

        if not files or files is MISSING:
            _files = []
        elif isinstance(files, list):
            _files = [file._json_payload(id) for id, file in enumerate(files)]
        else:
            _files = [files._json_payload(0)]
            files = [files]

        payload["attachments"] = _files

        if attachments is not MISSING:
            payload["attachments"].extend([attachment._json for attachment in attachments])
        if flags is not MISSING:
            payload["flags"] = flags.value
        if stickers is not MISSING:
            payload["sticker_ids"] = (
                [int(sticker.id) for sticker in stickers]
                if isinstance(stickers, list)
                else [stickers.id]
            )

        return payload, files
