"""Home Assistant Conversation entity backed by the narrow Hermes client."""

from __future__ import annotations

import re
import secrets
from collections import OrderedDict
from typing import Final, Literal, override

from homeassistant.components import conversation
from homeassistant.components.conversation import ConversationEntityFeature
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HermesConfigEntry
from .client import (
    HermesAuthenticationError,
    HermesClientError,
    HermesIndeterminateError,
)

_AUTH_ERROR = "Hermes requiere autenticación."
_INDETERMINATE_ERROR = (
    "No se pudo confirmar el resultado. Revisa el estado antes de intentarlo de nuevo."
)
_INVALID_ERROR = "La solicitud no es válida."
_MAX_TRACKED_CONVERSATIONS: Final = 256
_UNAVAILABLE_ERROR = "Hermes no está disponible."
_UNSPEAKABLE_ERROR = (
    "La respuesta no se puede leer en voz alta. Revisa el estado antes de intentarlo de nuevo."
)
_EMOJI: Final = re.compile(
    "[\u200d\u20e3\u2300-\u23ff\u2600-\u27bf\u2b00-\u2bff\ufe0f\U0001f000-\U0001faff]"
)
# Paired emphasis/code delimiters only; a lone or spaced "*" stays (2*3, a * b).
_EMPHASIS: Final = tuple(
    re.compile(rf"(?<![\w{d}])({d}{n})(?![\s{d}])([^{d}\n]+)(?<![\s{d}])\1(?![\w{d}])")
    for d, n in ((r"\*", "{1,3}"), ("_", "{1,3}"), ("~", "{2}"), ("`", ""))
)
# A "-" or "+" before a number is a sign, not a bullet.
_LINE_MARKER: Final = re.compile(r"\s*(?:(#{1,6})|[*•]|[-+](?!\s+\d))\s+")
_ORDERED_ITEM: Final = re.compile(r"\s*\d{1,9}[.)]\s")
_LINK: Final = re.compile(r"!?\[([^\[\]]*)\]\([^()\s]*\)")
_URL: Final = re.compile(r"<?https?://[^\s<>]*[^\s<>.,;:!?)]>?")


def _speech_text(text: str) -> str:
    """Return a TTS-friendly copy, or "" when nothing speakable remains."""
    cleaned = _EMOJI.sub("", _URL.sub("", _LINK.sub(r"\1", text)))
    spoken, after_heading = "", False
    for line in cleaned.splitlines():
        marker = _LINE_MARKER.match(line)
        # Wrapped prose joins with a space; headings and list items end a sentence.
        new_sentence = after_heading or bool(marker or _ORDERED_ITEM.match(line))
        line = line[marker.end() :] if marker else line
        for emphasis in _EMPHASIS:
            line = emphasis.sub(r"\2", line)
        line = re.sub(r"\s+(?=[.,;:!?])", "", " ".join(line.split()))
        if not line:
            continue
        if spoken:
            spoken += ". " if new_sentence and spoken[-1] not in ".,;:!?…" else " "
        spoken += line
        after_heading = bool(marker and marker[1])
    return spoken if any(char.isalnum() for char in spoken) else ""


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HermesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Register exactly one conversation entity for a validated entry."""
    del hass
    async_add_entities([HermesConversationEntity(entry)])


class HermesConversationEntity(conversation.ConversationEntity):
    """Send one data-only turn to the client owned by this config entry."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: HermesConfigEntry) -> None:
        """Bind the entity to one immutable entry runtime."""
        self._entry = entry
        self._attr_unique_id = entry.entry_id
        self._hermes_conversations: OrderedDict[str, str] = OrderedDict()

    def _conversation_ids(self, conversation_id: str | None) -> tuple[str, str]:
        """Return the HA ID and its entry-local opaque Hermes conversation key."""
        if conversation_id is None:
            conversation_id = secrets.token_urlsafe(24)
            while (
                conversation_id in self._hermes_conversations
                or conversation_id in self._hermes_conversations.values()
            ):
                conversation_id = secrets.token_urlsafe(24)

        hermes_conversation = self._hermes_conversations.get(conversation_id)
        if hermes_conversation is not None:
            self._hermes_conversations.move_to_end(conversation_id)
            return conversation_id, hermes_conversation

        hermes_conversation = secrets.token_urlsafe(24)
        while (
            hermes_conversation == conversation_id
            or hermes_conversation in self._hermes_conversations
            or hermes_conversation in self._hermes_conversations.values()
        ):
            hermes_conversation = secrets.token_urlsafe(24)
        self._hermes_conversations[conversation_id] = hermes_conversation
        if len(self._hermes_conversations) > _MAX_TRACKED_CONVERSATIONS:
            self._hermes_conversations.popitem(last=False)

        return conversation_id, hermes_conversation

    @property
    @override
    def supported_features(self) -> ConversationEntityFeature:
        """Advertise control only for the full Hermes runtime."""
        if self._entry.runtime_data.full_agent:
            return ConversationEntityFeature.CONTROL
        return ConversationEntityFeature(0)

    @property
    @override
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Accept the language already selected by Home Assistant Assist."""
        return MATCH_ALL

    @override
    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Submit only allowlisted request fields and return final speech."""
        intent_response = intent.IntentResponse(language=user_input.language)
        conversation_id, hermes_conversation = self._conversation_ids(user_input.conversation_id)
        request = {
            "model": self._entry.runtime_data.model,
            "utterance": user_input.text,
            "conversation": hermes_conversation,
        }
        if self._entry.runtime_data.model_alias:
            request["model_alias"] = self._entry.runtime_data.model_alias
        try:
            result = await self._entry.runtime_data.client.async_respond(**request)
        except HermesAuthenticationError:
            self._entry.async_start_reauth(self.hass)
            intent_response.async_set_error(intent.IntentResponseErrorCode.UNKNOWN, _AUTH_ERROR)
        except HermesIndeterminateError:
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN, _INDETERMINATE_ERROR
            )
        except HermesClientError:
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN, _UNAVAILABLE_ERROR
            )
        except ValueError:
            intent_response.async_set_error(intent.IntentResponseErrorCode.UNKNOWN, _INVALID_ERROR)
        else:
            chat_log.async_add_assistant_content_without_tools(
                conversation.AssistantContent(agent_id=self.entity_id, content=result.text)
            )
            if speech := _speech_text(result.text):
                intent_response.async_set_speech(speech)
            else:
                intent_response.async_set_error(
                    intent.IntentResponseErrorCode.UNKNOWN, _UNSPEAKABLE_ERROR
                )
        return conversation.ConversationResult(
            response=intent_response,
            conversation_id=conversation_id,
            continue_conversation=chat_log.continue_conversation
            and intent_response.response_type is not intent.IntentResponseType.ERROR,
        )
