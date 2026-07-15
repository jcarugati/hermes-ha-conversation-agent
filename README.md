# Hermes Conversation Agent para Home Assistant

Hermes Conversation Agent conecta una canalización de Assist de Home Assistant con la API de una instancia Hermes que ya está en ejecución y que el operador mantiene privada. Home Assistant conserva la palabra de activación, voz a texto, texto a voz, Assist y el registro de dispositivos; Hermes se ocupa del razonamiento y de las herramientas que tenga configuradas.

**Inicio rápido:** sigue la [guía de instalación y uso](docs/installation-and-usage.md#inicio-rápido).

## Qué hace y qué no hace

La integración es un adaptador HTTP pequeño. Envía cada frase de Assist al endpoint directo autenticado de la misma instancia Hermes y devuelve el texto final para que Assist lo pronuncie.

Solo funciona con el contrato directo de Hermes: `POST /v1/responses`, autenticación Bearer y respuestas no transmitidas (`stream: false`). No usa `/v1/chat/completions`, no instala una segunda plataforma de automatización y no reenvía herramientas, esquemas de Home Assistant, credenciales de HA ni el historial de ChatLog.

Hermes conserva su propia política de herramientas y MCP. Por tanto, elegir esta integración no crea un perfil aislado ni una lista de permisos exclusiva de Home Assistant.

## Privacidad y seguridad

- Es un requisito operativo mantener la API de Hermes en una LAN, Tailnet o detrás de un proxy privado y protegerla con un token Bearer. La integración no comprueba que un host HTTPS sea privado.
- HTTPS se verifica de forma predeterminada. Solo los hosts HTTP sin cifrar se limitan técnicamente a nombres locales o direcciones privadas, requieren habilitación explícita y muestran una advertencia.
- En cada turno se envían únicamente `model`, `input`, `conversation` y `stream: false`. La clave de conversación es opaca y nueva en cada turno; no se reenvían el `ChatLog` ni contexto entre turnos de Assist. Hermes puede conservar esa conversación de un turno, la respuesta y los registros de herramientas según su propia política, y la integración no garantiza su eliminación remota.
- Una frase de voz no autentica a la persona que la dijo. Prueba primero consultas de solo lectura y acciones inocuas autorizadas.

Consulta los detalles operativos y de riesgo en [Configuración avanzada](docs/advanced-configuration.md) y en la [política de seguridad](SECURITY.md).

## Estado actual

La integración dispone de configuración desde la interfaz de Home Assistant, renovación de token cuando Hermes rechaza la autenticación y opciones para límites de solicitud y alias de modelo. Admite una conexión directa por entrada de configuración; no ofrece controles de historial ni una pasarela alternativa.

## Logotipo

El logotipo local se incluye con la integración en [`custom_components/hermes_conversation/assets/logo.png`](custom_components/hermes_conversation/assets/logo.png). No se distribuye mediante el catálogo de Home Assistant Brands, por lo que Home Assistant o HACS pueden mostrar un icono genérico.

La descripción equivalente en inglés es: **not published through Home Assistant Brands**.

## Documentación

- [Instalación y uso](docs/installation-and-usage.md): guía para empezar, canalización Assist y solución de problemas.
- [Configuración avanzada](docs/advanced-configuration.md): alias de modelo, privacidad, límites y riesgos.
- [Arquitectura](docs/architecture.md): recorrido de datos y límites del adaptador.
- [Contrato de la API Responses](docs/hermes-responses-contract.md): contrato técnico que debe anunciar el servidor Hermes.
- [Política de seguridad](SECURITY.md): modelo de confianza y divulgación responsable.
