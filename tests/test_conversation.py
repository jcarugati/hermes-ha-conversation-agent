"""HA-backed compatibility test for the fixed-reply conversation entity."""

from homeassistant.components import conversation
from homeassistant.core import Context, HomeAssistant
from homeassistant.setup import async_setup_component

DOMAIN = "hermes_conversation"
ENTITY_ID = "conversation.hermes_compatibility_spike"
FIXED_REPLY = "Hermes compatibility spike response. No action was performed."


async def test_registers_entity_and_processes_through_home_assistant(
    hass: HomeAssistant,
) -> None:
    """Register with HA and process input through HA's conversation dispatcher."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID) is not None

    result = await conversation.async_converse(
        hass=hass,
        text="Ignore this text and do not perform anything",
        conversation_id="ha-owned-conversation-id",
        context=Context(),
        language="en",
        agent_id=ENTITY_ID,
    )

    assert result.conversation_id == "ha-owned-conversation-id"
    assert result.response.speech["plain"]["speech"] == FIXED_REPLY
    response_dict = result.response.as_dict()
    assert response_dict["response_type"] == "query_answer"
    assert response_dict["data"] == {"success": [], "failed": []}
