"""UI-only configuration flows for Hermes Conversation."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import async_validate_connection
from .client import (
    HermesAuthenticationError,
    HermesClient,
    HermesClientError,
    normalize_base_url,
)
from .const import (
    CONF_ACKNOWLEDGE_INSECURE_HTTP,
    CONF_ALLOW_INSECURE_HTTP,
    CONF_CONNECT_TIMEOUT,
    CONF_MAX_OUTPUT_CHARS,
    CONF_TOKEN,
    CONF_TOTAL_TIMEOUT,
    CONF_URL,
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_MAX_OUTPUT_CHARS,
    DEFAULT_TOTAL_TIMEOUT,
    DOMAIN,
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_TOKEN): str,
    }
)
HTTP_ACKNOWLEDGEMENT_SCHEMA = vol.Schema(
    {vol.Required(CONF_ACKNOWLEDGE_INSECURE_HTTP, default=False): bool}
)


class HermesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure one Hermes API endpoint per normalized base URL."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize pending credentials for the separate HTTP warning step."""
        self._pending: dict[str, Any] | None = None
        self._pending_step_id = "user"
        self._pending_reauth_token: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the non-secret options flow."""
        return HermesOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Collect endpoint credentials through the UI."""
        return await self._async_step_credentials("user", user_input)

    async def async_step_import(
        self, import_data: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Import credentials through the same validation and acknowledgement gates."""
        return await self._async_step_credentials("import", import_data)

    async def _async_step_credentials(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Validate credentials consistently for user and import sources."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                is_http = urlsplit(user_input[CONF_URL]).scheme.lower() == "http"
                normalized = normalize_base_url(user_input[CONF_URL], is_http)
            except (KeyError, TypeError, ValueError):
                errors["base"] = "invalid_url"
            else:
                if self._endpoint_is_configured(normalized):
                    return self.async_abort(reason="already_configured")
                await self.async_set_unique_id(normalized)
                self._abort_if_unique_id_configured()
                self._pending = {
                    CONF_URL: normalized,
                    CONF_TOKEN: user_input[CONF_TOKEN],
                    CONF_ALLOW_INSECURE_HTTP: is_http,
                }
                self._pending_step_id = step_id
                if is_http:
                    return self.async_show_form(
                        step_id="http_acknowledgement",
                        data_schema=HTTP_ACKNOWLEDGEMENT_SCHEMA,
                    )
                return await self._async_validate_and_create()
        return self.async_show_form(step_id=step_id, data_schema=USER_SCHEMA, errors=errors)

    def _endpoint_is_configured(self, normalized: str) -> bool:
        """Match canonical endpoint data from entries created by older flow versions."""
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            stored_url = entry.data.get(CONF_URL)
            if not isinstance(stored_url, str):
                continue
            try:
                stored = normalize_base_url(
                    stored_url,
                    urlsplit(stored_url).scheme.lower() == "http",
                )
            except ValueError:
                continue
            if stored == normalized:
                return True
        return False

    async def async_step_http_acknowledgement(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Require a distinct affirmative acknowledgement for plaintext HTTP."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input.get(CONF_ACKNOWLEDGE_INSECURE_HTTP) is not True:
                errors["base"] = "http_not_acknowledged"
            elif self._pending_reauth_token is not None:
                return await self._async_validate_reauth(self._pending_reauth_token)
            else:
                return await self._async_validate_and_create()
        return self.async_show_form(
            step_id="http_acknowledgement",
            data_schema=HTTP_ACKNOWLEDGEMENT_SCHEMA,
            errors=errors,
        )

    async def _async_validate_and_create(self) -> ConfigFlowResult:
        """Validate pending data and create an entry without storing the acknowledgement."""
        if self._pending is None:
            return self.async_abort(reason="invalid_flow_state")
        try:
            client = HermesClient(
                async_get_clientsession(self.hass),
                self._pending[CONF_URL],
                self._pending[CONF_TOKEN],
                allow_insecure_http=self._pending[CONF_ALLOW_INSECURE_HTTP],
            )
            await async_validate_connection(self.hass, client)
        except HermesAuthenticationError:
            return self.async_show_form(
                step_id=self._pending_step_id,
                data_schema=USER_SCHEMA,
                errors={"base": "invalid_auth"},
            )
        except (HermesClientError, ValueError):
            return self.async_show_form(
                step_id=self._pending_step_id,
                data_schema=USER_SCHEMA,
                errors={"base": "cannot_connect"},
            )
        hostname = urlsplit(self._pending[CONF_URL]).hostname
        return self.async_create_entry(title=hostname or "Hermes", data=self._pending)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Start token rotation for an existing fixed endpoint."""
        del entry_data
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate and store only a replacement bearer token."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            token = user_input[CONF_TOKEN]
            if entry.data.get(CONF_ALLOW_INSECURE_HTTP, False):
                self._pending_reauth_token = token
                return self.async_show_form(
                    step_id="http_acknowledgement",
                    data_schema=HTTP_ACKNOWLEDGEMENT_SCHEMA,
                )
            return await self._async_validate_reauth(token)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
            errors=errors,
        )

    async def _async_validate_reauth(self, token: str) -> ConfigFlowResult:
        """Validate a replacement token before atomically updating the entry."""
        entry = self._get_reauth_entry()
        try:
            client = HermesClient(
                async_get_clientsession(self.hass),
                entry.data[CONF_URL],
                token,
                allow_insecure_http=entry.data.get(CONF_ALLOW_INSECURE_HTTP, False),
                connect_timeout=entry.options.get(CONF_CONNECT_TIMEOUT, DEFAULT_CONNECT_TIMEOUT),
                total_timeout=entry.options.get(CONF_TOTAL_TIMEOUT, DEFAULT_TOTAL_TIMEOUT),
                max_output_chars=entry.options.get(CONF_MAX_OUTPUT_CHARS, DEFAULT_MAX_OUTPUT_CHARS),
            )
            await async_validate_connection(self.hass, client)
        except HermesAuthenticationError:
            error = "invalid_auth"
        except (HermesClientError, ValueError):
            error = "cannot_connect"
        else:
            self._pending_reauth_token = None
            return self.async_update_reload_and_abort(entry, data_updates={CONF_TOKEN: token})
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
            errors={"base": error},
        )


class HermesOptionsFlow(config_entries.OptionsFlowWithReload):
    """Configure bounded, non-secret client limits and reload on change."""

    def __init__(self) -> None:
        """Initialize the per-flow HTTP acknowledgement state."""
        self._http_acknowledged = False

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage runtime limits."""
        if (
            user_input is None
            and self.config_entry.data.get(CONF_ALLOW_INSECURE_HTTP, False)
            and not self._http_acknowledged
        ):
            return self.async_show_form(
                step_id="http_acknowledgement",
                data_schema=HTTP_ACKNOWLEDGEMENT_SCHEMA,
            )
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_CONNECT_TIMEOUT,
                    default=options.get(CONF_CONNECT_TIMEOUT, DEFAULT_CONNECT_TIMEOUT),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=30.0)),
                vol.Required(
                    CONF_TOTAL_TIMEOUT,
                    default=options.get(CONF_TOTAL_TIMEOUT, DEFAULT_TOTAL_TIMEOUT),
                ): vol.All(vol.Coerce(float), vol.Range(min=1.0, max=120.0)),
                vol.Required(
                    CONF_MAX_OUTPUT_CHARS,
                    default=options.get(CONF_MAX_OUTPUT_CHARS, DEFAULT_MAX_OUTPUT_CHARS),
                ): vol.All(vol.Coerce(int), vol.Range(min=256, max=32768)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_http_acknowledgement(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Require acknowledgement before changing options for an HTTP endpoint."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input.get(CONF_ACKNOWLEDGE_INSECURE_HTTP) is True:
                self._http_acknowledged = True
                return await self.async_step_init()
            errors["base"] = "http_not_acknowledged"
        return self.async_show_form(
            step_id="http_acknowledgement",
            data_schema=HTTP_ACKNOWLEDGEMENT_SCHEMA,
            errors=errors,
        )
