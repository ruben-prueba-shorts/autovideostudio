# Windows, YouTube y limpieza — 30 de octubre de 2026

Se amplía el orquestador de [ORCHESTRATOR.md](ORCHESTRATOR.md). No se repiten las generaciones Flow/Mako ni la prueba sintética de 18 minutos/160 imágenes. AutoVideo PR #3 sigue siendo una rama de desarrollo; ClipFarming PR #2 se reutiliza sin modificarlo en esta fase.

## Qué está implementado y qué se ha ejecutado

| Parte | Implementación | Evidencia real de esta fase |
| --- | --- | --- |
| Preparación Windows | `tools/Install-Factory.ps1`: dependencias opcionales, fuentes de ambas ramas, entorno Python aislado, carpeta dedicada y lanzador | **No ejecutada en Windows**. No hay terminal Windows disponible; Brave sí está conectado. `http://127.0.0.1:8765/` devolvió conexión rechazada |
| Comprobación local | `tools/windows_smoke.py`, reutiliza la misma fixture FFmpeg ya existente | Ejecutada en **Linux**: entrega sintética de 6 s, vídeo y Short H.264/AAC, interrupción tras montaje, reanudación con hash y mtime del maestro intactos |
| Canales | Confirmación de rol + ID exacto devuelto por OAuth `channels.list(mine=true)`; no reutiliza credenciales de otro rol | Cuatro canales vistos en Studio y sus IDs leídos de las cabeceras. **No hay cuatro autorizaciones OAuth locales**; los datos de cuenta no se publican en este repositorio |
| Subida | Cliente oficial OAuth de escritorio; protocolo HTTPS reanudable; URI cifrada con DPAPI, sesiones por archivo | Pruebas de contrato y servidor **simulado**, no subida real |
| Programación | Subida inicial privada sin `publishAt`; procesamiento confirmado; actualización privada + fecha futura; GET independiente para verificar | Estados, calendario, respuesta final perdida y procesamiento probados con simulador. No hay prueba de programación pública en una cuenta real |
| Limpieza | Inventario exacto por recibos, hashes, enlaces, estados de todos los vídeos y verificación reciente; vista de simulación | **0 archivos borrados**. Muestra real: 4 derivados, **30.991.816 bytes potenciales**. La evidencia simulada bloquea la elegibilidad real |

Pruebas: **25 nuevas de YouTube**, **11 del orquestador**, **4 del motor FFmpeg**, **6 Node de AutoVideo**, **2 pruebas UI aisladas**. No se presenta la ejecución anterior de ClipFarming ni la prueba larga anterior como nuevas pruebas. Medidas: [validation/youtube-windows-results.json](validation/youtube-windows-results.json).

La primera ejecución del nuevo smoke encontró un error SQLite de E/S. Se detectó que los contextos de conexión confirmaban transacciones sin cerrar explícitamente el descriptor; `ClosingConnection` ahora cierra tras commit/rollback. El smoke posterior, las pruebas de recuperación y la regresión pasaron. El harness de copia de seguridad también cerraba tarde sus conexiones; se corrigió, se añadió checkpoint al terminar y se verificó el estado desde **otro proceso y la interfaz**. No se afirma que se haya demostrado la causa única del error inicial ni que estas pruebas sustituyan una ejecución en Windows. Se conserva la evidencia de la ejecución fallida.

## Instalación en el PC: paso que falta ejecutar allí

Descargar `tools/Install-Factory.ps1` de la rama del PR #3. Revisarlo y ejecutarlo desde una consola **del Windows del usuario**, sin desactivar sus protecciones:

```powershell
powershell -NoProfile -File .\Install-Factory.ps1 -InstallDependencies -WithOAuth -SmokeTest
```

Destino predeterminado: `%LOCALAPPDATA%\YouTubeFactory`. Debe ser nuevo/vacío. Puede elegirse otro con `-Root "D:\YouTubeFactory"`. El instalador rechaza una carpeta con archivos existentes; no actualiza ni borra una instalación anterior. Si una instalación queda incompleta, conservarla para diagnosticar y usar otra carpeta vacía o completar los pasos manuales documentados. No se requiere ni se intenta acceso de administrador; si un paquete no permite instalación por usuario, se detiene.

- Sin `-InstallDependencies` solo usa programas que ya estén instalados.
- Opcionalmente usa **WinGet**, repositorio oficial: `Python.Python.3.13`, `OpenJS.NodeJS.LTS`, `Gyan.FFmpeg`. No acepta contratos automáticamente ni omite comprobaciones de hashes o malware. Algunos instaladores pueden requerir intervención o un método manual.
- [Python](https://www.python.org/downloads/windows/) y [Node.js](https://nodejs.org/en/download) son las fuentes de los fabricantes. [FFmpeg](https://ffmpeg.org/download.html) publica código fuente y enlaza las compilaciones Windows de Gyan/BtbN; **Gyan es una compilación enlazada, no un binario publicado por FFmpeg**. WinGet documenta sus opciones de alcance y origen en [Microsoft Learn](https://learn.microsoft.com/windows/package-manager/winget/install).
- Resuelve cada rama existente a un commit y descarga ese snapshot por HTTPS desde GitHub. Conserva los ZIP y `source-versions.json` con commits/hashes. Son **snapshots de desarrollo, no clones con historial Git**. No utiliza main ni modifica las webs públicas.
- Crea `.venv` y `data/`, con SQLite, inbox, producciones y entregas. No requiere `npm install` para el motor.
- `-WithOAuth` instala únicamente `google-auth` y `google-auth-oauthlib` desde PyPI, dentro de `.venv`. No conecta cuentas ni activa facturación.
- `-SmokeTest` escribe un caso **sintético**, unos 6 segundos, dentro de `data/diagnostics/`. Comprueba guardar, renderizar, interrumpir y recuperar. Su `pc-proof.json` distingue Windows/Linux. No es una nueva prueba de narración natural o de 18 minutos.

Al terminar se crea `Start-Factory.cmd`. Mantener ese proceso abierto y entrar en `http://127.0.0.1:8765/`. La aplicación solo escucha en loopback; no abre puertos públicos ni instala un servicio/tarea de inicio. Cerrar la pestaña no detiene el proceso. Apagar/suspender Windows sí puede interrumpir el trabajo.

**No se ha probado todavía que los resultados terminen en el disco del usuario.** El asistente puede manejar la aplicación mediante Brave cuando esté arrancada allí; disponer del navegador no da acceso a PowerShell ni permite iniciar ejecutables Windows desde este entorno Linux.

## OAuth y correspondencia de canales

1. En un proyecto de Google propio, habilitar **YouTube Data API v3**, configurar audiencia/usuarios de prueba y crear un cliente OAuth de tipo **Desktop**. No crear claves de pago, no vincular tarjeta, no activar facturación. Si la consola lo exige, parar y documentarlo.
2. Descargar el JSON oficial **al PC**, fuera del repositorio. No enviarlo, ni enviar tokens/contraseñas por chat.
3. Empezar por lectura. El usuario realiza personalmente la selección Google/Brand y el consentimiento:

```powershell
.\.venv\Scripts\python.exe .\src\autovideostudio\tools\youtube_official.py connect .\data .\oauth-client.json life-ranges-es UC_ID_EXACTO_OBSERVADO
```

Repetir para `life-ranges-en`, `finance-es`, `finance-en`, siempre usando el ID observado de **ese** canal. La llamada de lectura no sube ni modifica vídeos. El ID se vuelve a comprobar mediante `channels.list(mine=true)`; si la sesión responde con otro canal o varios, se detiene. Ni un correo ni un nombre visible se usan como identidad suficiente.

La opción `--write` solicita un consentimiento nuevo para `youtube.force-ssl` y fija la correspondencia permanente en SQLite. **No se ejecutó en esta fase.** La lectura usa `youtube.readonly`. `videos.insert` admite `youtube.upload`, pero `videos.update` (necesario para programar después del procesamiento) no lo admite: por eso la operación completa requiere un permiso de edición más amplio. La aplicación no ofrece borrar vídeos ni escribir comentarios aunque el scope de Google también permita esas operaciones. [Permisos oficiales de videos.update](https://developers.google.com/youtube/v3/docs/videos/update).

Los refresh tokens y las URLs de sesiones reanudables se guardan con **Windows DPAPI, usuario actual**, en `data/youtube-secrets/`. No hay respaldo en texto plano ni datos de autenticación en SQLite, Git o logs. **DPAPI no se ha probado en Windows**; en Linux se verificó que falla sin crear un token en texto plano. No confundir protección de credenciales con copia de seguridad: reinstalar Windows o cambiar el contexto de usuario puede requerir autorizar de nuevo.

OAuth en modo externo **Testing** emite refresh tokens de siete días para estos scopes. Puede requerir reconsentimiento; no sirve para prometer operación indefinida desatendida. La verificación OAuth, la auditoría API de YouTube y las funciones/penalizaciones de cada canal son comprobaciones distintas. Algunas excepciones para uso personal existen, pero no se asume que se apliquen al proyecto sin inspeccionarlo. [OAuth](https://developers.google.com/identity/protocols/oauth2), [flujo de escritorio con PKCE](https://developers.google.com/identity/protocols/oauth2/native-app), [verificación](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification).

## Planes, calendario y aprobación de la primera subida

La interfaz permite **preparar un plan sin subir** y consultar estado/canal/fecha. Para pruebas privadas, cada archivo debe tener fecha `null`:

```json
{
  "mode": "private",
  "review": {
    "contentApproved": true,
    "madeForKids": false,
    "containsSyntheticMedia": true,
    "categoryId": "22"
  },
  "videos": {"long.mp4": null, "shorts/short-01.mp4": null}
}
```

**Los valores de audiencia/divulgación son un ejemplo, no decisiones tomadas por el usuario ni una revisión editorial realizada.** Deben revisarse para cada entrega. Para programar, `mode` es `schedule` y cada archivo lleva su fecha ISO con desfase explícito, por ejemplo `2026-11-20T18:00:00+01:00`. No se adivina la hora de verano. El motor exige al menos cinco minutos futuros al preparar y al programar; si el procesamiento dura demasiado, se bloquea en vez de publicar inmediatamente.

El plan incluye **todos** los Shorts y el largo, título/descripción/etiquetas/idioma, miniatura del largo, audiencia, divulgación, ID de canal, huellas y fechas independientes. SQLite reserva huecos de treinta minutos mínimos por canal con transacción; un mismo MP4 por hash no puede reservarse dos veces para el mismo canal. Planes y correspondencias son inmutables: cambiar un canal o calendario ya preparado requiere una migración revisada, todavía no implementada. La política de horarios habitual de los cuatro canales queda por acordar.

CLI equivalente:

```powershell
.\.venv\Scripts\python.exe .\src\autovideostudio\tools\youtube_factory.py prepare .\data PROD_ID .\schedule.json
.\.venv\Scripts\python.exe .\src\autovideostudio\tools\youtube_factory.py show .\data YT_BATCH_ID
```

Antes de la primera transferencia, mostrar al usuario **nombre e ID de canal, archivo/vídeo, miniatura/metadatos, visibilidad y, si procede, fechas** y obtener su autorización expresa. El código exige un permiso local separado, vinculado al hash exacto del plan, canal, modo y caducidad. **No se ha creado ese permiso; no hay botón que lo active ni aprobación automática**. La autorización de programar no se deduce de un consentimiento OAuth ni de una subida privada. El modo de reglas automáticas para aprobar futuros planes **no está habilitado**.

El cliente `youtube_official.py step` puede avanzar un paso con un plan autorizado; `verify` relee los recursos. Todavía falta el control local para conceder/revocar ese permiso desde una revisión personal y un trabajador de publicación continuo aprobado. Preparar el cliente no equivale a tener publicación desatendida en marcha.

## Recuperación y verificaciones

`tools/youtube_factory.py` extiende la misma SQLite con canales, lotes, elementos, reservas, hashes y auditoría. No cambia un encargo de montaje terminado para fingir que está publicado. Estados separados:

`awaiting_approval`, `upload_pending`, `uploading`, `upload_uncertain`, `processing`, `ready_to_schedule`, `scheduling`, `scheduled`, `failed`.

- Un trabajador reclama un lease por lote. Conserva el resultado/ID de cada archivo y nunca guarda una URI de subida como texto en la tabla.
- Sesión reanudable persistida antes de enviar vídeo. Cada paso consulta el offset remoto; un final cuya respuesta se perdió recupera el **mismo ID**. No crea otro `videos.insert`.
- Una sesión expirada o un crash antes de guardar la URI pasa a `upload_uncertain`; no reinicia automáticamente un upload que podría haberse completado. Hace falta reconciliación personal. No se inventa el hash del archivo alojado, porque YouTube no lo proporciona.
- Errores temporales respetan espera/Retry-After y máximo tres intentos. No hay bucle de reintentos rápido. `retry_item` recupera un fallo explícito conservando la sesión o el vídeo existente; no autoriza un insert nuevo ante resultado incierto.
- Tras recibir ID se consulta `videos.list`: canal e ID exactos, `status.uploadStatus=processed`, `processingDetails.processingStatus=succeeded` y ausencia de visibilidad inesperada.
- Inicialmente siempre `privacyStatus=private`, sin `publishAt`, `notifySubscribers=false`. Tras procesar se sube la miniatura del largo y se programa; los Shorts conservan su propio horario. La selección final de miniatura para Shorts puede estar limitada por YouTube y no se promete personalización idéntica al largo.
- Un PUT satisfactorio de programación **no basta**. Otro GET debe devolver fecha exacta, privado, título, audiencia, divulgación y procesamiento correcto. Si falla, se conservan los archivos.
- Un estado `scheduled` no garantiza que la plataforma vaya a publicar en el futuro: restricciones, penalizaciones o reclamaciones pueden impedirlo. La API genérica no es una auditoría de copyright ni de la aptitud futura del canal.

## Cuotas, restricciones y coste

Consulta oficial del **30-10-2026**: [calculadora](https://developers.google.com/youtube/v3/determine_quota_cost) y [videos.insert](https://developers.google.com/youtube/v3/docs/videos/insert) indican **100 videos.insert/día**, coste **1** del bucket Video Uploads por llamada, 100 búsquedas/día y 10.000 unidades/día para otras operaciones. `videos.update` y `thumbnails.set` cuestan unas 50 unidades cada uno; las lecturas también gastan cuota. **Unidades de cuota no son euros.** No se ha consultado la cuota efectiva de un proyecto del usuario ni se promete ese límite para todas las cuentas. No hay facturación, compra de cuota, rotación de proyectos ni elusión de límites en el cliente. Ante un límite se detiene/reintenta con límites, no paga.

La documentación actual de `videos.insert` consultada dice que los proyectos API no verificados **no están limitados automáticamente a privado**. Esto difiere de referencias antiguas: no debe asumirse que el proyecto concreto permitirá programar publicaciones sin probarlo. La verificación OAuth y posibles revisiones/auditorías siguen siendo independientes. No se ha validado ni solicitado ninguna con la cuenta real. [Auditorías/cuota](https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits).

`publishAt` solo corresponde a un vídeo privado nunca publicado; una fecha pasada puede publicarlo inmediatamente, motivo del bloqueo explícito. [Recurso video](https://developers.google.com/youtube/v3/docs/videos). Para **18 minutos**, comprobar funciones habilitadas para vídeos de más de quince minutos. [Ayuda de YouTube](https://support.google.com/youtube/answer/71673). YouTube Studio ofrece programación gratuita como alternativa oficial con selección de cuenta/canal y zona horaria; puede requerir pasos manuales y no se presenta como automatización de navegador ya implementada. [Programación en Studio](https://support.google.com/youtube/answer/1270709?hl=es).

Es técnicamente viable preparar esta integración dentro de las cuotas oficiales sin API de pago ni servidor contratado. **No demuestra que toda la fábrica sea gratuita e ilimitada**: siguen sin certificarse 160 imágenes gratuitas por ejecución, narraciones de 18 minutos/canal, transferencia permitida desde Google, ejecución permanente del ordenador ni disponibilidad de tareas ChatGPT sin suscripción. No se han generado contenidos nuevos para eludir esos bloqueos.

## Limpieza: exclusivamente simulación

La interfaz **Calcular sin borrar** muestra cada ruta, tamaño y SHA-256, espacio potencial, motivos de bloqueo y cero bytes liberados. Guarda `cleanup-simulations/ID.json` y un evento. No existe código de borrado definitivo en esta fase.

Condiciones preparadas para una futura activación aprobada:

1. Producción terminada, ningún trabajador de YouTube activo y manifiesto/recibo intactos.
2. Todos los vídeos requeridos, incluido cada Short, con ID/canal correctos, recibidos, procesados y programación futura exacta confirmada.
3. Evidencia de **YouTube real**, recién consultada, con antigüedad máxima de quince minutos. Una simulación o respuesta HTTP 2xx no sirve. Una subida privada sin fecha no sirve.
4. Solo rutas enumeradas por recibos de etapas de **ese** encargo y dentro de sus carpetas de derivados. Hash actual igual al registrado.
5. Excluir enlaces simbólicos, junctions Windows, enlaces duros, archivos referenciados por otros encargos, archivos cambiados y todo lo que no tenga atribución demostrable.
6. Conservar guiones/prompts/metadatos/validaciones/logs/base de datos, originales y fuentes. Se incluyen MP4 y proyectos/medios derivados verificables; **no se barre una carpeta por extensión ni se borran todos los segmentos temporales por intuición**. Ampliar la limpieza a más intermediarios requerirá registrar sus recibos primero.
7. Autorizar personalmente la política para la carpeta concreta, después de revisar la simulación y probarla con una subida real. No basta esta instrucción para activar borrado definitivo; el usuario lo ha condicionado expresamente a otra autorización.

En la muestra real, derivados candidatos: horizontal **11.121.642 B**, maestro limpio **10.695.148 B**, Short entregado **4.587.513 B**, copia de render de ese Short **4.587.513 B**. Total **30.991.816 B (29,56 MiB)**. **Liberado: 0 B**. Las fuentes y el audio Mako permanecen; no se extrapola esta cifra al vídeo de 18 minutos. Borrar originales o maestros puede impedir reconstruir su calidad inicial: YouTube no es una copia del archivo original.

## Reproducción de pruebas

```sh
python -m unittest discover -s tests -p youtube_factory_test.py -v
python -m unittest discover -s tests -p orchestrator_test.py -v
python -m unittest discover -s tests -p local_factory_test.py -v
node --test tests/*.test.cjs
python tools/windows_smoke.py /carpeta/dedicada/nueva
python tests/run-youtube-existing.py /fabrica-con-muestra-existente PROD_ID
CHROMIUM_EXECUTABLE=/ruta/chromium-aislado node tests/local-app-browser.cjs
CHROMIUM_EXECUTABLE=/ruta/chromium-aislado node tests/youtube-app-browser.cjs /fabrica-con-muestra-existente
```

El simulador usa IDs sintéticos y conserva su estado en un archivo de pruebas; su servidor no es YouTube. Las elecciones editoriales de esa simulación **no son aprobación de escucha humana**. La prueba de persistencia se leyó de nuevo desde otro proceso y desde la UI tras terminar el cliente. No se subieron fuentes privadas, credenciales ni cuentas al repositorio.

## Siguiente trabajo que sí requiere intervención

- Ejecutar el arranque local y su prueba en Windows, comprobar la carpeta elegida, fuentes FFmpeg y DPAPI allí.
- Crear/seleccionar el proyecto OAuth gratuito del usuario sin facturación y realizar personalmente cuatro consentimientos; confirmar el rol de cada ID observado.
- Revisar una entrega real y autorizar la **primera subida privada** concreta. Solo después comprobar con permiso separado la programación pública futura y las restricciones de cada canal.
- Definir las reglas/calendario automáticos, activar un trabajador aprobado y validar una entrega larga real; las pruebas sintéticas anteriores no sustituyen eso.
- Tras todo lo anterior, revisar el inventario y autorizar explícitamente la limpieza. Hasta entonces, **no borrar**.
