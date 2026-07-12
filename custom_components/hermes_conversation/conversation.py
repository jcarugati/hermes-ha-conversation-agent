"""Home Assistant Conversation entity backed by the narrow Hermes client."""

from __future__ import annotations

import secrets
from typing import Literal, override

from homeassistant.components import conversation
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
_UNAVAILABLE_ERROR = "Hermes no está disponible."


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
        del chat_log
        response = intent.IntentResponse(language=user_input.language)
        try:
            result = await self._entry.runtime_data.client.async_respond(
                model=self._entry.runtime_data.model,
                utterance=user_input.text,
                conversation=secrets.token_urlsafe(24),
            )
        except HermesAuthenticationError:
            self._entry.async_start_reauth(self.hass)
            response.async_set_error(intent.IntentResponseErrorCode.UNKNOWN, _AUTH_ERROR)
        except HermesIndeterminateError:
            response.async_set_error(intent.IntentResponseErrorCode.UNKNOWN, _INDETERMINATE_ERROR)
        except HermesClientError:
            response.async_set_error(intent.IntentResponseErrorCode.UNKNOWN, _UNAVAILABLE_ERROR)
        except ValueError:
            response.async_set_error(intent.IntentResponseErrorCode.UNKNOWN, _INVALID_ERROR)
        else:
            response.async_set_speech(result.text)
        return conversation.ConversationResult(
            response=response,
            conversation_id=user_input.conversation_id,
        )
