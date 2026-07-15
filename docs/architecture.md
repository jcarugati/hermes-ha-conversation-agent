# Arquitectura

Para configurar la integración, empieza con [Instalación y uso](installation-and-usage.md). Para el alias de modelo, los límites y los riesgos operativos, consulta [Configuración avanzada](advanced-configuration.md).

```text
Dispositivo de voz
  → Assist de Home Assistant (STT, canalización y TTS)
  → entidad Hermes Conversation Agent
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
2. La entidad crea una clave de conversación opaca nueva para ese turno y escoge el modelo predeterminado anunciado por Hermes o el alias configurado.
3. Antes de enviar la solicitud, el cliente vuelve a validar las capacidades directas autenticadas de Hermes.
4. El cliente envía exclusivamente `{model, input, conversation, stream: false}` a `POST /v1/responses`, con redirecciones desactivadas.
5. Si la respuesta completada incluye texto final no vacío, la entidad se lo devuelve a Assist para que Home Assistant lo pronuncie.

Los registros de herramientas de Hermes pueden preceder al texto final. Una respuesta terminada que contenga solo registros de herramientas se considera un error y nunca se convierte en una respuesta hablada satisfactoria.

## Límites de confianza y datos

El adaptador acepta solo un servidor Hermes privado que use autenticación Bearer y anuncie `responses_api: true`, `chat_completions: true` y el endpoint fijo `POST /v1/responses`, sin un contrato `security` personalizado. Comprueba el estado, las capacidades y el contrato durante la configuración; valida las capacidades otra vez al cargar la entrada y antes de cada envío.

La solicitud no contiene historial de ChatLog, cookies, contexto de Home Assistant, identificadores de usuario o dispositivo, credenciales de HA, tokens de servicio, herramientas, acciones, instrucciones ni sustituciones de prompt. El cliente usa una sesión sin cookies para no cruzar las de Home Assistant.

Cada turno es independiente: la clave opaca de conversación no se reutiliza y la integración no expone controles de historial. El token Bearer solo se transmite en la cabecera de autenticación, no en la URL ni en registros.

## Modelo y disponibilidad

El alias de modelo sustituye únicamente el valor de `model` en el mismo cuerpo de cuatro campos. No cambia el endpoint ni selecciona una instancia, perfil o agente aislado. Para elegirlo correctamente, debe ser una ruta de modelo que ya exista en la API Hermes configurada; los detalles están en [Configuración avanzada](advanced-configuration.md#alias-de-modelo).

Después de que un `POST` se haya enviado, un tiempo de espera o desconexión se trata como resultado indeterminado y no se reintenta automáticamente. La persona que opera Home Assistant debe verificar el estado real antes de repetir una acción.
