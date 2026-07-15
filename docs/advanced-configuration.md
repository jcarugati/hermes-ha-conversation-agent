# Configuración avanzada

Esta integración se conecta únicamente a la API directa de una instancia Hermes ya en ejecución. La guía inicial está en [Instalación y uso](installation-and-usage.md); el recorrido interno se describe en [Arquitectura](architecture.md).

## Alias de modelo

La opción **Model alias (optional)** no añade una selección de agente. Solo determina el valor de `model` que la integración envía a la misma API Hermes.

- Durante la carga o recarga de la entrada, la integración guarda el modelo predeterminado anunciado por `/v1/capabilities`. Si el alias queda en blanco, cada solicitud usa ese modelo configurado y guardado.
- Si Hermes cambia su modelo predeterminado, recarga o reconfigura la entrada para guardar el nuevo valor anunciado.
- Si se completa, la integración reenvía el alias como el único valor de `model`; no comprueba previamente que exista en las rutas. Hermes debe aceptar el alias y devolverlo como `model` en la respuesta.
- El alias no selecciona un perfil, agente o entorno aislado. Tampoco cambia el endpoint ni las herramientas, los servidores MCP o los permisos disponibles en Hermes.

El campo admite como máximo 512 caracteres. Si no quieres usar un alias, déjalo vacío para conservar el modelo guardado durante la última carga o recarga de la entrada.

## Endpoint directo y contrato

La URL configurada es la raíz de la API, no una URL de chat ni de una pasarela. Durante la configuración y cada carga o recarga de la entrada, la integración realiza estas comprobaciones:

1. `GET /health` debe identificar un Hermes saludable.
2. `GET /v1/capabilities` autenticado debe anunciar `responses_api: true`, `chat_completions: true`, autenticación Bearer obligatoria y `POST /v1/responses`, sin un miembro `security` personalizado.
Antes de cada solicitud de Assist, vuelve a ejecutar únicamente `GET /v1/capabilities` autenticado, verifica que el modelo predeterminado siga coincidiendo con el guardado y después envía `POST /v1/responses` autenticado, sin redirecciones y con `stream: false`. No ejecuta `GET /health` antes de cada despacho.

El cuerpo contiene exactamente estos cuatro campos:

```json
{
  "model": "<modelo predeterminado o alias>",
  "input": "<frase de Assist>",
  "conversation": "<clave opaca nueva>",
  "stream": false
}
```

No se usa `/v1/chat/completions`. Un servidor de compatibilidad, una pasarela restringida o un contrato de seguridad distinto no es compatible con esta integración.

## Conversaciones y privacidad

Para cada turno de Assist, la integración genera una clave de conversación opaca y nueva. No lee ni envía el `ChatLog` entrante de Home Assistant, y no conserva ni reenvía contexto entre turnos. Por diseño, no hay controles para restablecer, escoger, recuperar o reutilizar datos remotos.

La clave nueva evita que la integración encadene turnos, pero no impone una política de retención en Hermes. Hermes puede conservar la conversación nombrada de ese turno, la respuesta y los registros de herramientas según su propia política. La integración no garantiza la eliminación remota de esos datos.

Además de los cuatro campos del cuerpo, la solicitud autenticada lleva el token Bearer en su cabecera. No se envían cookies de Home Assistant, identificadores de usuario o dispositivo, contexto, credenciales de HA, tokens de servicio, herramientas, acciones, instrucciones ni sustituciones de prompt. Los registros y diagnósticos deben tratar el token y el texto de la conversación como información sensible.

Como requisito operativo, mantén el servidor en una LAN, Tailnet o detrás de un proxy privado y sin CORS de navegador innecesario. HTTPS verifica el certificado por defecto, pero la integración no valida que su host sea privado. Solo HTTP sin cifrar está limitado técnicamente a hosts locales o privados; debe habilitarse de forma explícita y expone el token y los datos de la solicitud a la red.

## Límites y tiempos de espera

Los límites están pensados para contener solicitudes y respuestas, no para aumentar permisos:

- La entrada de Assist acepta hasta 8192 caracteres; el cuerpo de la solicitud está limitado a 32768 bytes.
- **Connect timeout (seconds)** permite de 0,1 a 30 segundos; el valor inicial es 5.
- **Total timeout (seconds)** permite de 1 a 120 segundos; el valor inicial es 30.
- **Maximum response characters** permite de 256 a 32768; el valor inicial es 8192. Las respuestas HTTP también tienen un límite de tamaño de 1 MiB.
- Las respuestas deben ser JSON y contener texto final no vacío de Hermes; una respuesta que solo contenga registros de herramientas se rechaza.

Una vez que el `POST` se ha enviado, un tiempo de espera o una desconexión tiene resultado indeterminado: Hermes podría haber ejecutado la solicitud. La integración no hace reintentos automáticos. Antes de repetir una acción, especialmente si cambia algo, comprueba su estado real.

## Riesgo operativo

Hermes conserva toda la superficie de herramientas y MCP que tenga configurada para esa instancia. La capacidad de control que ve Assist no es un límite de autorización adicional, y una voz no prueba la identidad de quien habla. Un prompt no sustituye los permisos de Hermes ni los controles de red.

Mantén la ruta de voz que ya funciona mientras haces las primeras comprobaciones. Verifica primero una respuesta escrita en la interfaz de texto de Assist; después, verifica por separado la entrada de voz y la salida TTS. Continúa con una consulta de solo lectura y, por último, una acción inocua autorizada. Consulta también la [política de seguridad](../SECURITY.md).
