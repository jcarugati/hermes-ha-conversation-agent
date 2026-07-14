"""Tests for the UI-only Hermes config and options flows."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_REAUTH, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import InvalidData
from pytest_homeassistant_custom_component.common import (  # type: ignore[import-untyped]
    MockConfigEntry,
)

from custom_components.hermes_conversation.client import (
    HermesAuthenticationError,
    HermesClientError,
    HermesProtocolError,
)
from custom_components.hermes_conversation.const import (
    CONF_ALLOW_INSECURE_HTTP,
    CONF_CONNECT_TIMEOUT,
    CONF_MAX_OUTPUT_CHARS,
    CONF_MODEL_ALIAS,
    CONF_TOKEN,
    CONF_TOTAL_TIMEOUT,
    CONF_URL,
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_MAX_OUTPUT_CHARS,
    DEFAULT_TOTAL_TIMEOUT,
    DOMAIN,
)


async def test_user_https_creates_entry_with_normalized_url(hass: HomeAssistant) -> None:
    """HTTPS is validated and its normalized URL is the unique ID."""
    with (
        patch(
            "custom_components.hermes_conversation.config_flow.async_validate_connection",
            new=AsyncMock(),
        ) as validate,
        patch(
            "custom_components.hermes_conversation.async_validate_connection",
            new=AsyncMock(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_URL: "https://HERMES.Home.Arpa:443/", CONF_TOKEN: "secret"},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "hermes.home.arpa"
    assert result["data"] == {
        CONF_URL: "https://hermes.home.arpa",
        CONF_TOKEN: "secret",
        CONF_ALLOW_INSECURE_HTTP: False,
    }
    assert result["options"] == {}
    assert result["result"].unique_id == "https://hermes.home.arpa"
    validate.assert_awaited_once()


async def test_http_requires_separate_acknowledgement(hass: HomeAssistant) -> None:
    """Plaintext HTTP is never accepted on the credentials form alone."""
    with (
        patch(
            "custom_components.hermes_conversation.config_flow.async_validate_connection",
            new=AsyncMock(),
        ) as validate,
        patch(
            "custom_components.hermes_conversation.async_validate_connection",
            new=AsyncMock(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_URL: "http://192.168.1.10/", CONF_TOKEN: "secret"},
        )
        assert result["type"] == "form"
        assert result["step_id"] == "http_acknowledgement"
        validate.assert_not_awaited()

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"acknowledge_insecure_http": False}
        )
        assert result["type"] == "form"
        assert result["errors"] == {"base": "http_not_acknowledged"}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"acknowledge_insecure_http": True}
        )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_ALLOW_INSECURE_HTTP] is True
    validate.assert_awaited_once()


async def test_invalid_or_unavailable_server_is_not_saved(hass: HomeAssistant) -> None:
    """Malformed input and failed validation return safe form errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_URL: "https://user:pass@example.test", CONF_TOKEN: "secret"},
    )
    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_url"}

    with patch(
        "custom_components.hermes_conversation.config_flow.async_validate_connection",
        new=AsyncMock(side_effect=HermesClientError),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: "https://hermes.example.test", CONF_TOKEN: "secret"},
        )
    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_non_direct_responses_api_cannot_configure(
    hass: HomeAssistant,
) -> None:
    """A Responses-only server is outside the direct Hermes contract."""
    with patch(
        "custom_components.hermes_conversation.config_flow.async_validate_connection",
        new=AsyncMock(
            side_effect=HermesProtocolError("/v1/capabilities does not advertise chat_completions")
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_URL: "https://generic-hermes.example.test", CONF_TOKEN: "secret"},
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}
    assert hass.config_entries.async_entries(DOMAIN) == []


async def test_duplicate_normalized_url_is_rejected(hass: HomeAssistant) -> None:
    """Equivalent endpoint spellings cannot create multiple entries."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="https://hermes.example.test",
        data={CONF_URL: "https://hermes.example.test", CONF_TOKEN: "old"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_URL: "https://HERMES.EXAMPLE.TEST/", CONF_TOKEN: "new"},
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_duplicate_noncanonical_entry_is_rejected(hass: HomeAssistant) -> None:
    """Canonical comparison also covers entries stored before canonical identities."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="https://HERMES.Example.Test.:443",
        data={CONF_URL: "https://HERMES.Example.Test.:443", CONF_TOKEN: "old"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_URL: "https://hermes.example.test", CONF_TOKEN: "new"},
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_duplicate_prevention_is_atomic_across_concurrent_flows(
    hass: HomeAssistant,
) -> None:
    """An in-progress canonical identity reserves the endpoint for one flow."""
    validation_started = asyncio.Event()
    release_validation = asyncio.Event()

    async def validate(*args: object) -> None:
        del args
        validation_started.set()
        await release_validation.wait()

    with patch(
        "custom_components.hermes_conversation.config_flow.async_validate_connection",
        side_effect=validate,
    ):
        first = asyncio.create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_USER},
                data={
                    CONF_URL: "https://B\N{LATIN SMALL LETTER U WITH DIAERESIS}CHER.example.:443/",
                    CONF_TOKEN: "first",
                },
            )
        )
        await validation_started.wait()
        second = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_URL: "https://xn--bcher-kva.example", CONF_TOKEN: "second"},
        )
        release_validation.set()
        first_result = await first

    assert first_result["type"] == "create_entry"
    assert second["type"] == "abort"
    assert second["reason"] == "already_in_progress"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_import_http_requires_acknowledgement(hass: HomeAssistant) -> None:
    """Imported plaintext credentials cannot validate before acknowledgement."""
    with patch(
        "custom_components.hermes_conversation.config_flow.async_validate_connection",
        new=AsyncMock(),
    ) as validate:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_URL: "http://127.0.0.1:8124", CONF_TOKEN: "secret"},
        )
        assert result["type"] == "form"
        assert result["step_id"] == "http_acknowledgement"
        validate.assert_not_awaited()

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"acknowledge_insecure_http": True}
        )

    assert result["type"] == "create_entry"
    validate.assert_awaited_once()


async def test_reauth_validates_token_then_updates_and_reloads(hass: HomeAssistant) -> None:
    """Reauth rotates only the secret and reloads the existing entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="https://hermes.example.test",
        data={
            CONF_URL: "https://hermes.example.test",
            CONF_TOKEN: "old",
            CONF_ALLOW_INSECURE_HTTP: False,
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.hermes_conversation.config_flow.async_validate_connection",
            new=AsyncMock(),
        ) as validate,
        patch.object(hass.config_entries, "async_schedule_reload") as reload_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
            data=entry.data,
        )
        assert result["type"] == "form"
        assert result["step_id"] == "reauth_confirm"
        assert result["data_schema"] is not None
        assert list(result["data_schema"].schema) == [CONF_TOKEN]

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TOKEN: "rotated"}
        )

    assert result["type"] == "abort"
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_TOKEN] == "rotated"
    assert entry.data[CONF_URL] == "https://hermes.example.test"
    validate.assert_awaited_once()
    reload_entry.assert_called_once_with(entry.entry_id)


async def test_failed_reauth_preserves_old_data_and_does_not_reload(
    hass: HomeAssistant,
) -> None:
    """Rejected replacement credentials never mutate or reload the entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="https://hermes.example.test",
        data={CONF_URL: "https://hermes.example.test", CONF_TOKEN: "old"},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.hermes_conversation.config_flow.async_validate_connection",
            new=AsyncMock(side_effect=HermesAuthenticationError("HTTP 403")),
        ),
        patch.object(hass.config_entries, "async_schedule_reload") as reload_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
            data=entry.data,
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TOKEN: "rejected"}
        )

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data[CONF_TOKEN] == "old"
    reload_entry.assert_not_called()


async def test_reauth_http_requires_acknowledgement_before_validation(
    hass: HomeAssistant,
) -> None:
    """Token rotation against HTTP has its own explicit acknowledgement gate."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="http://127.0.0.1:8124",
        data={
            CONF_URL: "http://127.0.0.1:8124",
            CONF_TOKEN: "old",
            CONF_ALLOW_INSECURE_HTTP: True,
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.hermes_conversation.config_flow.async_validate_connection",
        new=AsyncMock(),
    ) as validate:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
            data=entry.data,
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TOKEN: "rotated"}
        )
        assert result["step_id"] == "http_acknowledgement"
        validate.assert_not_awaited()

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"acknowledge_insecure_http": True}
        )

    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_TOKEN] == "rotated"
    validate.assert_awaited_once()


async def test_options_are_non_secret_and_reload_entry(hass: HomeAssistant) -> None:
    """Options expose bounded runtime limits but never credentials."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "https://hermes.example.test", CONF_TOKEN: "secret"},
    )
    entry.add_to_hass(hass)

    with patch.object(hass.config_entries, "async_schedule_reload") as reload_entry:
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] == "form"
        assert result["data_schema"] is not None
        schema = result["data_schema"].schema
        assert CONF_TOKEN not in schema
        assert CONF_URL not in schema
        markers = {marker.schema: marker for marker in schema}
        assert markers[CONF_CONNECT_TIMEOUT].default() == DEFAULT_CONNECT_TIMEOUT
        assert markers[CONF_TOTAL_TIMEOUT].default() == DEFAULT_TOTAL_TIMEOUT
        assert markers[CONF_MAX_OUTPUT_CHARS].default() == DEFAULT_MAX_OUTPUT_CHARS

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_CONNECT_TIMEOUT: 3.0,
                CONF_TOTAL_TIMEOUT: 20.0,
                CONF_MAX_OUTPUT_CHARS: 4096,
            },
        )

    assert result["type"] == "create_entry"
    assert entry.options == {
        CONF_CONNECT_TIMEOUT: 3.0,
        CONF_TOTAL_TIMEOUT: 20.0,
        CONF_MAX_OUTPUT_CHARS: 4096,
        CONF_MODEL_ALIAS: "",
    }
    reload_entry.assert_called_once_with(entry.entry_id)


async def test_http_options_require_acknowledgement_before_changes(
    hass: HomeAssistant,
) -> None:
    """Options for a plaintext endpoint cannot be changed without acknowledgement."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: "http://127.0.0.1:8124",
            CONF_TOKEN: "secret",
            CONF_ALLOW_INSECURE_HTTP: True,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "form"
    assert result["step_id"] == "http_acknowledgement"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"acknowledge_insecure_http": False}
    )
    assert result["errors"] == {"base": "http_not_acknowledged"}
    assert entry.options == {}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"acknowledge_insecure_http": True}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "init"


async def test_options_include_optional_model_alias(hass: HomeAssistant) -> None:
    """Options expose an optional model alias field that defaults to empty."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "https://hermes.example.test", CONF_TOKEN: "secret"},
    )
    entry.add_to_hass(hass)

    with patch.object(hass.config_entries, "async_schedule_reload"):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] == "form"
        assert result["data_schema"] is not None
        schema = result["data_schema"].schema
        markers = {marker.schema: marker for marker in schema}
        assert CONF_MODEL_ALIAS in markers
        assert markers[CONF_MODEL_ALIAS].default() == ""

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_CONNECT_TIMEOUT: 5.0,
                CONF_TOTAL_TIMEOUT: 30.0,
                CONF_MAX_OUTPUT_CHARS: 8192,
                CONF_MODEL_ALIAS: "custom-route",
            },
        )

    assert result["type"] == "create_entry"
    assert entry.options[CONF_MODEL_ALIAS] == "custom-route"


async def test_options_model_alias_empty_is_accepted(hass: HomeAssistant) -> None:
    """Empty model alias is valid and means 'use capabilities model'."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "https://hermes.example.test", CONF_TOKEN: "secret"},
    )
    entry.add_to_hass(hass)

    with patch.object(hass.config_entries, "async_schedule_reload"):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_CONNECT_TIMEOUT: 5.0,
                CONF_TOTAL_TIMEOUT: 30.0,
                CONF_MAX_OUTPUT_CHARS: 8192,
                CONF_MODEL_ALIAS: "",
            },
        )

    assert result["type"] == "create_entry"
    assert entry.options[CONF_MODEL_ALIAS] == ""


async def test_options_model_alias_is_bounded(hass: HomeAssistant) -> None:
    """A model alias cannot exceed the client's model-field limit."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "https://hermes.example.test", CONF_TOKEN: "secret"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    with pytest.raises(InvalidData, match=CONF_MODEL_ALIAS):
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_CONNECT_TIMEOUT: 5.0,
                CONF_TOTAL_TIMEOUT: 30.0,
                CONF_MAX_OUTPUT_CHARS: 8192,
                CONF_MODEL_ALIAS: "x" * 513,
            },
        )
