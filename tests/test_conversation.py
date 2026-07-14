"""End-to-end Home Assistant dispatcher tests for the Hermes entity bridge."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components import conversation
from homeassistant.components.conversation import chat_log as chat_log_module
from homeassistant.components.conversation.chat_log import (
    AssistantContent,
    SystemContent,
    UserContent,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import intent
from pytest_homeassistant_custom_component.common import (  # type: ignore[import-untyped]
    MockConfigEntry,
)

from custom_components.hermes_conversation.client import (
    HermesAuthenticationError,
    HermesCapabilities,
    HermesClient,
    HermesClientError,
    HermesIndeterminateError,
    HermesResponse,
)
from custom_components.hermes_conversation.const import (
    CONF_MODEL_ALIAS,
    CONF_TOKEN,
    CONF_URL,
    DOMAIN,
)


def _home_capabilities(model: str) -> HermesCapabilities:
    return HermesCapabilities(
        model=model,
        tool_policy="full_agent",
        mcp_policy="server_managed",
        server_enforced=False,
    )


def _entry(endpoint: str, token: str, *, title: str) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title=title,
        unique_id=endpoint,
        data={CONF_URL: endpoint, CONF_TOKEN: token},
    )


@asynccontextmanager
async def _loaded_entity(
    hass: HomeAssistant,
    *,
    endpoint: str = "https://hermes-one.example.test",
    title: str = "Hermes One",
    model: str = "hermes-model",
) -> AsyncIterator[tuple[MockConfigEntry, MagicMock, str]]:
    entry = _entry(endpoint, "entry-token", title=title)
    entry.add_to_hass(hass)
    client = MagicMock(spec=HermesClient)
    client.async_health = AsyncMock()
    client.async_capabilities = AsyncMock(return_value=_home_capabilities(model))
    client.async_respond = AsyncMock(
        return_value=HermesResponse(response_id="response-id", text="Respuesta breve")
    )

    with patch("custom_components.hermes_conversation.create_client", return_value=client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        registry = er.async_get(hass)
        entities = er.async_entries_for_config_entry(registry, entry.entry_id)
        assert len(entities) == 1
        entity_id = entities[0].entity_id
        try:
            yield entry, client, entity_id
        finally:
            await hass.config_entries.async_unload(entry.entry_id)
            await hass.async_block_till_done()


async def _converse(
    hass: HomeAssistant,
    entity_id: str,
    *,
    text: str = "estado de la casa",
    conversation_id: str | None = "ha-visible-conversation",
) -> conversation.ConversationResult:
    return await conversation.async_converse(
        hass=hass,
        text=text,
        conversation_id=conversation_id,
        context=Context(user_id="ha-user-secret"),
        language="es",
        agent_id=entity_id,
        device_id="ha-device-secret",
        satellite_id="ha-satellite-secret",
        extra_system_prompt="ha-system-secret",
    )


async def test_dispatcher_sends_only_allowlisted_dto_and_returns_spoken_text(
    hass: HomeAssistant,
) -> None:
    """The real HA dispatcher reaches Hermes without leaking HA or ChatLog data."""
    async with _loaded_entity(hass) as (_entry_value, client, entity_id):
        result = await _converse(hass, entity_id)

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert result.response.speech["plain"]["speech"] == "Respuesta breve"
    assert result.conversation_id == "ha-visible-conversation"
    client.async_respond.assert_awaited_once()
    assert client.async_respond.await_args.args == ()
    request = client.async_respond.await_args.kwargs
    assert set(request) == {"model", "utterance", "conversation"}
    assert request["model"] == "hermes-model"
    assert request["utterance"] == "estado de la casa"
    assert request["conversation"] != "ha-visible-conversation"
    assert 1 <= len(request["conversation"]) <= 512
    serialized = repr(request)
    for forbidden in (
        "ha-user-secret",
        "ha-device-secret",
        "ha-satellite-secret",
        "ha-system-secret",
        "entry-token",
        "tools",
        "actions",
        "chat_log",
        "context",
    ):
        assert forbidden not in serialized


async def test_dispatcher_completes_local_chat_log_without_forwarding_it(
    hass: HomeAssistant,
) -> None:
    """HA retains only its local turn while Hermes receives the allowlisted DTO."""
    async with _loaded_entity(hass) as (_entry_value, client, entity_id):
        await _converse(
            hass,
            entity_id,
            text="entrada privada de HA",
            conversation_id="local-chat-log",
        )

        stored = hass.data[chat_log_module.DATA_CHAT_LOGS]["local-chat-log"]
        system_content, user_content, assistant_content = stored.content
        assert isinstance(system_content, SystemContent)
        assert isinstance(user_content, UserContent)
        assert isinstance(assistant_content, AssistantContent)
        assert [
            (system_content.role, system_content.content),
            (user_content.role, user_content.content),
            (assistant_content.role, assistant_content.content),
        ] == [
            ("system", ""),
            ("user", "entrada privada de HA"),
            ("assistant", "Respuesta breve"),
        ]
        assert assistant_content.agent_id == entity_id

    request = client.async_respond.await_args.kwargs
    assert set(request) == {"model", "utterance", "conversation"}
    assert "Respuesta breve" not in repr(request)
    assert "local-chat-log" not in repr(request)


async def test_entries_are_isolated_and_each_register_exactly_one_entity(
    hass: HomeAssistant,
) -> None:
    """Each loaded entry dispatches only through its own client and model."""
    first = _entry("https://one.example.test", "token-one", title="One")
    second = _entry("https://two.example.test", "token-two", title="Two")
    first.add_to_hass(hass)
    second.add_to_hass(hass)
    clients: dict[str, MagicMock] = {}

    def create(_hass: HomeAssistant, entry: MockConfigEntry) -> MagicMock:
        client = MagicMock(spec=HermesClient)
        client.async_health = AsyncMock()
        client.async_capabilities = AsyncMock(
            return_value=_home_capabilities(f"model-{entry.title.lower()}")
        )
        client.async_respond = AsyncMock(
            return_value=HermesResponse(response_id="id", text=entry.title)
        )
        clients[entry.entry_id] = client
        return client

    with patch("custom_components.hermes_conversation.create_client", side_effect=create):
        assert await hass.config_entries.async_setup(first.entry_id)
        await hass.async_block_till_done()
        assert second.state is ConfigEntryState.LOADED
        registry = er.async_get(hass)
        first_entity = er.async_entries_for_config_entry(registry, first.entry_id)
        second_entity = er.async_entries_for_config_entry(registry, second.entry_id)
        assert len(first_entity) == len(second_entity) == 1

        result = await _converse(hass, first_entity[0].entity_id, text="solo primero")

    assert result.response.speech["plain"]["speech"] == "One"
    clients[first.entry_id].async_respond.assert_awaited_once()
    clients[second.entry_id].async_respond.assert_not_awaited()
    assert clients[first.entry_id].async_respond.await_args.kwargs["model"] == "model-one"


@pytest.mark.parametrize(
    ("failure", "expected_speech"),
    [
        (
            HermesClientError("contains https://secret.invalid and transcript"),
            "Hermes no está disponible.",
        ),
        (
            HermesIndeterminateError("token transcript endpoint"),
            "No se pudo confirmar el resultado. Revisa el estado antes de intentarlo de nuevo.",
        ),
        (ValueError("utterance contains transcript"), "La solicitud no es válida."),
    ],
)
async def test_errors_are_sanitized_and_post_is_never_retried(
    hass: HomeAssistant, failure: Exception, expected_speech: str
) -> None:
    """Failures become fixed HA errors and one dispatcher turn makes one client call."""
    async with _loaded_entity(hass) as (_entry_value, client, entity_id):
        client.async_respond.side_effect = failure
        result = await _converse(hass, entity_id, text="sensitive transcript")

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert result.response.speech["plain"]["speech"] == expected_speech
    assert "secret.invalid" not in repr(result.as_dict())
    assert "sensitive transcript" not in repr(result.as_dict())
    client.async_respond.assert_awaited_once()


async def test_request_authentication_error_starts_reauth_without_retry(
    hass: HomeAssistant,
) -> None:
    """A request-time auth rejection starts HA reauth and returns a fixed error."""
    async with _loaded_entity(hass) as (entry, client, entity_id):
        client.async_respond.side_effect = HermesAuthenticationError("expired token")
        result = await _converse(hass, entity_id)

        flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        assert len(flows) == 1
        assert flows[0]["context"]["source"] == "reauth"
        assert flows[0]["context"]["entry_id"] == entry.entry_id

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert result.response.speech["plain"]["speech"] == "Hermes requiere autenticación."
    client.async_respond.assert_awaited_once()


async def test_dispatcher_sends_model_alias_when_configured(
    hass: HomeAssistant,
) -> None:
    """When model_alias is configured, the dispatcher sends it instead of the capabilities model."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Alias",
        unique_id="https://hermes-alias.example.test",
        data={CONF_URL: "https://hermes-alias.example.test", CONF_TOKEN: "entry-token"},
        options={CONF_MODEL_ALIAS: "routed-model-alias"},
    )
    entry.add_to_hass(hass)
    client = MagicMock(spec=HermesClient)
    client.async_health = AsyncMock()
    client.async_capabilities = AsyncMock(return_value=_home_capabilities("hermes-model"))
    client.async_respond = AsyncMock(
        return_value=HermesResponse(response_id="response-id", text="Alias response")
    )

    with patch("custom_components.hermes_conversation.create_client", return_value=client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        registry = er.async_get(hass)
        entities = er.async_entries_for_config_entry(registry, entry.entry_id)
        entity_id = entities[0].entity_id
        try:
            result = await _converse(hass, entity_id)
        finally:
            await hass.config_entries.async_unload(entry.entry_id)
            await hass.async_block_till_done()

    assert result.response.speech["plain"]["speech"] == "Alias response"
    request = client.async_respond.await_args.kwargs
    assert request == {
        "model": "hermes-model",
        "utterance": "estado de la casa",
        "conversation": request["conversation"],
        "model_alias": "routed-model-alias",
    }


async def test_setup_retry_registers_no_entity(hass: HomeAssistant) -> None:
    """An unavailable entry cannot appear as a selectable conversation entity."""
    entry = _entry("https://offline.example.test", "token", title="Offline")
    entry.add_to_hass(hass)
    client = MagicMock(spec=HermesClient)
    client.async_health = AsyncMock(side_effect=HermesClientError("offline"))

    with patch("custom_components.hermes_conversation.create_client", return_value=client):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id) == []


async def test_non_direct_responses_api_rejection_registers_no_bridge(
    hass: HomeAssistant,
) -> None:
    """A non-direct Responses server cannot become a callable HA bridge."""
    entry = _entry("https://generic-hermes.example.test", "token", title="Generic")
    entry.add_to_hass(hass)
    client = MagicMock(spec=HermesClient)
    client.async_health = AsyncMock()
    client.async_capabilities = AsyncMock(
        side_effect=HermesClientError("/v1/capabilities does not advertise chat_completions")
    )

    with patch("custom_components.hermes_conversation.create_client", return_value=client):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id) == []


async def test_unload_and_reload_do_not_double_entity_instances(hass: HomeAssistant) -> None:
    """Platform lifecycle removes the entity and reload creates only one replacement."""
    entry = _entry("https://reload.example.test", "token", title="Reload")
    entry.add_to_hass(hass)
    clients: list[MagicMock] = []

    def create(_hass: HomeAssistant, _entry: MockConfigEntry) -> MagicMock:
        client = MagicMock(spec=HermesClient)
        client.async_health = AsyncMock()
        client.async_capabilities = AsyncMock(return_value=_home_capabilities("model"))
        client.async_respond = AsyncMock(return_value=HermesResponse(response_id="id", text="ok"))
        clients.append(client)
        return client

    with patch("custom_components.hermes_conversation.create_client", side_effect=create):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        registry = er.async_get(hass)
        entity_id = er.async_entries_for_config_entry(registry, entry.entry_id)[0].entity_id
        assert hass.states.get(entity_id) is not None

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        unloaded_state = hass.states.get(entity_id)
        assert unloaded_state is not None
        assert unloaded_state.state == "unavailable"

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(clients) == 2
    assert len(er.async_entries_for_config_entry(registry, entry.entry_id)) == 1
    assert hass.states.get(entity_id) is not None
