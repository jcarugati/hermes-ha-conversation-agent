# Instalación y uso

Esta guía configura Hermes Conversation Agent como el agente de conversación de una canalización Assist. Para el modelo de datos, alias y límites, consulta [Configuración avanzada](advanced-configuration.md).

## Antes de empezar

Necesitas lo siguiente:

- Una instalación de Home Assistant que admita integraciones personalizadas y acceso de administrador a su interfaz.
- Una instancia Hermes ya en ejecución, privada y accesible desde Home Assistant.
- La URL raíz de la API Hermes, sin ruta, parámetros ni credenciales en la URL. Usa HTTPS siempre que sea posible.
- Un token Bearer válido para esa API. Guárdalo como secreto y no lo pegues en capturas, registros ni archivos.

El servidor debe ser la API directa de la misma instancia Hermes que usas en otros canales. Durante la configuración, la integración comprueba `GET /health`, `GET /v1/capabilities` autenticado y el contrato de `POST /v1/responses`. Debe anunciar autenticación Bearer obligatoria, `responses_api: true`, `chat_completions: true` y el endpoint fijo de Responses, sin un contrato `security` personalizado.

## Instalar la integración

### Con HACS como repositorio personalizado

El proyecto incluye la metadata necesaria para HACS, pero no presupone que aparezca en una lista pública.

1. En HACS, abre **Integrations** y usa el menú para añadir un repositorio personalizado.
2. Introduce la URL de clonación de este repositorio y selecciona el tipo **Integration**.
3. Busca **Hermes Conversation Agent** dentro de ese repositorio personalizado e instálalo.
4. Reinicia Home Assistant cuando HACS termine.

### Instalación manual

1. Copia la carpeta `custom_components/hermes_conversation` de este repositorio a `<configuración_de_Home_Assistant>/custom_components/hermes_conversation`.
2. Conserva todos sus archivos y subcarpetas; no copies solo archivos Python.
3. Reinicia Home Assistant.

## Configurar la conexión en Home Assistant

1. Ve a **Settings → Devices & services → Add integration**.
2. Busca y selecciona **Hermes Conversation Agent**.
3. Completa los dos campos mostrados por el flujo de configuración:

   - **Hermes base URL**: la URL raíz privada de la API Hermes, por ejemplo con el esquema `https://`. No añadas `/v1/responses` ni un subdirectorio.
   - **Bearer token**: el token de la API Hermes.

4. Si usas `http://`, Home Assistant muestra una pantalla adicional. Marca exactamente **I understand that HTTP exposes the token and request data on the network** solo si el host es local o privado y aceptas el riesgo. HTTPS es la opción recomendada.
5. Espera a que termine la validación. Si la URL, el token o el contrato del servidor no son válidos, la entrada no se guarda.

La integración está diseñada solo para una URL privada. No expongas Hermes en Internet ni uses una pasarela alternativa; las redirecciones y las credenciales incluidas en la URL no se admiten.

## Elegir Hermes en una canalización Assist

1. Abre el editor de la canalización Assist que vas a usar en **Settings → Voice assistants**.
2. En el campo de agente de conversación, selecciona **Hermes Conversation Agent**.
3. Guarda la canalización y asígnala a la voz o al dispositivo con el que la probarás.

La integración devuelve a Assist el texto final de Hermes. Home Assistant mantiene la entrada de voz, la salida de voz y los dispositivos; Hermes conserva las herramientas que tenga configuradas.

## Inicio rápido

Conserva la canalización de voz que ya funciona mientras verificas la nueva entrada.

1. Desde Assist, envía una solicitud de texto sencilla que no controle ningún dispositivo, por ejemplo: «Responde con una frase breve para confirmar la conexión». Comprueba que Assist pronuncia la respuesta de Hermes.
2. Haz una consulta de solo lectura que Hermes esté autorizado a resolver en tu instalación.
3. Prueba una acción inocua que hayas autorizado explícitamente, preferiblemente sobre una entidad de prueba.
4. Solo después de esas verificaciones, usa la canalización para el control habitual.

Una respuesta que contenga llamadas de herramientas y un texto final válido puede hablarse. Si Hermes termina sin texto final, la integración falla de forma segura en lugar de anunciar éxito.

## Cambiar opciones, actualizar el token o eliminar la entrada

Abre la entrada **Hermes Conversation Agent** en **Settings → Devices & services** y elige **Configure** para cambiar sus opciones. Al guardar, Home Assistant recarga la entrada.

Los campos de opciones actuales son:

- **Connect timeout (seconds)**: de 0,1 a 30; valor predeterminado 5.
- **Total timeout (seconds)**: de 1 a 120; valor predeterminado 30.
- **Maximum response characters**: de 256 a 32768; valor predeterminado 8192.
- **Model alias (optional)**: hasta 512 caracteres. Déjalo vacío para usar el modelo predeterminado anunciado por Hermes. Consulta [Configuración avanzada](advanced-configuration.md#alias-de-modelo).

Para una entrada HTTP, Home Assistant vuelve a pedir la confirmación de riesgo antes de abrir las opciones.

Si Hermes rechaza el token durante una solicitud, Home Assistant inicia la pantalla **Update authentication**. Introduce el nuevo valor en **Bearer token** y completa otra vez la confirmación de HTTP si corresponde. La URL no se cambia en este proceso.

Para dejar de usar la integración, abre el menú de la entrada y elige **Delete**. Esto elimina la configuración local de Home Assistant; no detiene Hermes ni modifica sus modelos, herramientas o datos.

## Solución de problemas

| Síntoma | Qué comprobar |
| --- | --- |
| **Could not validate the Hermes endpoint, credentials, and Responses API capability** | Confirma que la URL es la raíz privada de la API, que Home Assistant puede alcanzarla y que el servidor anuncia el contrato directo requerido. Comprueba también el certificado HTTPS. |
| **Hermes rejected the bearer token** | Sustituye el token mediante **Update authentication**. No añadas el token a la URL. |
| La confirmación HTTP no permite continuar | HTTP solo se acepta para `localhost`, sufijos locales admitidos o direcciones privadas. Usa HTTPS si no necesitas HTTP local. |
| Hermes no aparece como agente de conversación | Verifica que la entrada se haya creado sin errores, que Home Assistant se haya reiniciado tras la instalación y que hayas seleccionado **Hermes Conversation Agent** en la canalización Assist. |
| Assist dice que Hermes no está disponible | Comprueba la conectividad privada, el estado de Hermes, la validez del token y el contrato de capacidades. |
| No se pudo confirmar el resultado | Una solicitud ya enviada puede haber llegado a Hermes aunque se agotara el tiempo o se cortara la conexión. Revisa el estado real antes de repetir una acción. La integración no la reintenta automáticamente. |
| El alias de modelo falla | Déjalo vacío para volver al predeterminado de Hermes o usa un alias existente en las rutas de modelos configuradas de esa misma API. |

No hay controles para recuperar, borrar o reutilizar un historial remoto: cada turno de Assist usa una conversación opaca nueva. Lee [Configuración avanzada](advanced-configuration.md#conversaciones-y-privacidad) antes de basar un flujo en contexto conversacional.
