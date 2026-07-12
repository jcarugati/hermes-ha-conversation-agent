"""Minimal Home Assistant ConversationEntity compatibility spike."""

from typing import Literal

from homeassistant.components.conversation import (
    ChatLog,
    ConversationEntity,
    ConversationInput,
    ConversationResult,
)
from homeassistant.components.conversation.const import DATA_COMPONENT
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.typing import ConfigType

FIXED_REPLY = "Hermes compatibility spike response. No action was performed."


class HermesCompatibilitySpikeEntity(ConversationEntity):
    """Conversation entity that always returns a fixed, non-action reply."""

    _attr_name = "Hermes compatibility spike"
    _attr_unique_id = "hermes_compatibility_spike"

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Accept any language because the fixed reply does not interpret input."""
        return MATCH_ALL

    async def _async_handle_message(
        self,
        user_input: ConversationInput,
        chat_log: ChatLog,
    ) -> ConversationResult:
        """Return fixed speech without inspecting or forwarding the conversation."""
        del chat_log
        response = intent.IntentResponse(language=user_input.language)
        response.response_type = intent.IntentResponseType.QUERY_ANSWER
        response.async_set_speech(FIXED_REPLY)
        return ConversationResult(
            response=response,
            conversation_id=user_input.conversation_id,
        )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the single spike entity with Home Assistant."""
    del config
    await hass.data[DATA_COMPONENT].async_add_entities([HermesCompatibilitySpikeEntity()])
    return True
