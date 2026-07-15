# Arquitectura

Para configurar la integración, empieza con [Instalación y uso](installation-and-usage.md). Para el alias de modelo, los límites y los riesgos operativos, consulta [Configuración avanzada](advanced-configuration.md).

```text
Dispositivo de voz
  → Assist de Home Assistant (STT, canalización y TTS)
  → entidad de conversación de la entrada Hermes
  → POST /v1/responses autenticado en la API privada de Hermes
  → texto final de Hermes
  → TTS de Home Assistant
  → Dispositivo de voz
```

## Responsabilidades

Home Assistant conserva la palabra de activación, STT, TTS, Assist, las automatizaciones nativas, el registro de dispositivos y sus propias credenciales. Hermes conserva el razonamiento, las rutas de modelos y su política de herramientas y MCP.

Hermes Conversation Agent es solamente el adaptador entre ambos. No crea esquemas de herramientas de Home Assistant, no ejecuta callbacks de HA, no añade otra plataforma de automatización y no cambia las capacidades configuradas en Hermes.

## Flujo de una solicitud

1. Assist entrega el texto actual a la entidad de conversación.
2. La entidad crea una clave de conversación opaca nueva para ese turno y escoge el modelo predeterminado guardado al cargar la entrada o el alias configurado.
3. Antes de enviar la solicitud, el cliente vuelve a validar las capacidades directas autenticadas de Hermes.
4. El cliente envía exclusivamente `{model, input, conversation, stream: false}` a `POST /v1/responses`, con redirecciones desactivadas.
5. Si la respuesta completada incluye texto final no vacío, la entidad se lo devuelve a Assist para que Home Assistant lo pronuncie.

Los registros de herramientas de Hermes pueden preceder al texto final. Una respuesta terminada que contenga solo registros de herramientas se considera un error y nunca se convierte en una respuesta hablada satisfactoria.

## Límites de confianza y datos

El operador debe conectar el adaptador a un servidor Hermes privado que use autenticación Bearer y anuncie `responses_api: true`, `chat_completions: true` y el endpoint fijo `POST /v1/responses`, sin un contrato `security` personalizado. La configuración y cada carga o recarga comprueban `GET /health` y las capacidades autenticadas. Cada despacho vuelve a validar únicamente las capacidades autenticadas antes del `POST`; no repite la comprobación de salud.

La integración no demuestra que un host HTTPS sea privado; esa exposición en LAN, Tailnet o proxy privado es responsabilidad del operador. Solo las URLs HTTP sin cifrar están limitadas técnicamente a hosts locales o direcciones privadas.

La solicitud no contiene historial de ChatLog, cookies, contexto de Home Assistant, identificadores de usuario o dispositivo, credenciales de HA, tokens de servicio, herramientas, acciones, instrucciones ni sustituciones de prompt. El cliente usa una sesión sin cookies para no cruzar las de Home Assistant.

La integración no enlaza turnos: la clave opaca de conversación no se reutiliza y no se reenvían el `ChatLog` ni contexto entre turnos. Sin embargo, Hermes puede conservar la conversación nombrada de un turno, su respuesta y los registros de herramientas según su propia política; la integración no ofrece una garantía de retención o eliminación remota. El token Bearer solo se transmite en la cabecera de autenticación, no en la URL ni en registros.

## Modelo y disponibilidad

La carga o recarga de la entrada guarda el modelo predeterminado anunciado por capacidades. Sin alias, se usa ese valor guardado; si Hermes cambia su modelo predeterminado, hay que recargar o reconfigurar la entrada. Un alias sustituye únicamente el valor de `model` en el mismo cuerpo de cuatro campos. La integración no lo valida previamente contra las rutas: Hermes debe aceptarlo y devolverlo como `model`. El alias no cambia el endpoint ni selecciona una instancia, perfil o agente aislado, y tampoco modifica herramientas o permisos. Los detalles están en [Configuración avanzada](advanced-configuration.md#alias-de-modelo).

Después de que un `POST` se haya enviado, un tiempo de espera o desconexión se trata como resultado indeterminado y no se reintenta automáticamente. La persona que opera Home Assistant debe verificar el estado real antes de repetir una acción.
