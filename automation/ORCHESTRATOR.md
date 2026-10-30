# Orquestador local — estado del 30 de octubre de 2026

El núcleo está implementado en `tools/factory_orchestrator.py`, con interfaz local en `tools/factory_local_app.py`. Usa Python estándar, Node y FFmpeg/FFprobe. No necesita hosting, almacenamiento contratado ni una API de ChatGPT. La extensión posterior de YouTube incluye un cliente oficial opcional **desactivado**, preparación Windows y limpieza **solo simulada**: estado y pruebas actuales en [WINDOWS-YOUTUBE.md](WINDOWS-YOUTUBE.md). No se añadió un generador ni se autorizó subir/borrar.

**Funciona con guion y medios ya preparados; todavía no produce todo desde una idea sin intervención.** El trabajo de autoría de ChatGPT, las generaciones y su transferencia desde las interfaces de Google no se sustituyen por respuestas ficticias. Se emiten solicitudes de archivos y el encargo espera.

## Recorrido ejecutado, conectado de principio a fin

Un catálogo de diez entradas **de prueba**, identificado explícitamente como sintético, contiene la reutilización de la muestra de fútbol. No se presenta como un nuevo radar viral. Al seleccionar **«Haz el vídeo 3»**, el sistema:

1. Recuperó exactamente la entrada 3 y creó un encargo SQLite sin duplicados.
2. Incorporó el guion existente y sus metadatos.
3. Detectó `inbox/.../production.ready.json`, comprobó las huellas y copió una instantánea de los archivos completos.
4. Reutilizó el maestro limpio y el horizontal subtitulado de la prueba real Mako/Flow, sin cambiar el vídeo largo ni generar otra voz o imagen.
5. Seleccionó y exportó un Short mediante los selectores compartidos de ClipFarming y FFmpeg local, sin mantener la página abierta durante el render.
6. Auditó H.264/yuv420p, AAC a 48 kHz, duración, orientación, faststart y decodificación completa.
7. Publicó una carpeta de entrega con **23 archivos más `validation.json`**, por temática, idioma, informe y encargo.

Resultado: estado **review**, unos **13,0 s** en este entorno. Horizontal conservado: **25,819938 s**, 1280×720. Nuevo Short local: **25,807479 s**, 720×1280. No se generó una narración nueva. Se compararon tres ventanas de audio de cuatro segundos: retraso estable de unos **54,9 ms**, correlación mínima **0,9897**, sin deriva detectada en la muestra. Se comprobaron imágenes 102/110/97 en tres puntos del Short. No equivale a una escucha humana o a comprobar todos los fotogramas.

El maestro y su JSON entregados se importaron después en la interfaz real de ClipFarming de la rama; el proyecto editable se reabrió y restauró sus **25 cues** y cortes. No se volvió a renderizar esa prueba UI ni se hizo una solicitud externa.

Medidas y límites: `validation/orchestrator-results.json`. Las pruebas anteriores de 18 minutos/160 imágenes sintéticas siguen en `FACTORY-VALIDATION.md`: **no se repitieron** ni se convierten en una prueba larga con voz real.

## Cola, recuperación e integridad

- Tablas de producciones, informes, etapas y eventos en la misma base SQLite que la cola de render ya existente. El render usa `local_factory.enqueue/work_once`, con reclamación por ID para no procesar otro encargo por error.
- Etapas: brief → script → media → assembly → shorts → package. Estados: queued, running, blocked, failed y review. No existe un estado automático «publicado».
- Informes inmutables con ID y hash; elección con número e informe explícito. Repetir la misma elección y configuración devuelve el encargo existente. Si no está el informe, no se inventa «vídeo 3».
- Instantáneas con hashes de archivos, guion, imágenes y prompts, utilizando los contratos existentes del importador AutoVideo y la entrega a ClipFarming. No se adivina asociación por cronología de descargas.
- Lease y heartbeat; un trabajador activo no se reclama dos veces. Interrupciones y fallos quedan registrados. Reintentos explícitos, limitados a tres fallos; no reintentan generación.
- Recibos por etapa con hashes: al reanudar se verifican y se reutilizan resultados terminados. Una prueba interrumpió después del montaje; al reintentar conservó **hash y fecha de modificación del maestro**, sin repetir su render.
- La bandeja solo lee sobres `production.ready.json` dentro de su carpeta dedicada. El productor escribe primero los archivos y el sobre al final mediante renombrado atómico. Archivos parciales o cambiados se rechazan; no lanzan un generador alternativo.
- El destino debe ser una carpeta nueva/vacía o una carpeta ya creada por la fábrica. Se rechazan escapes de ruta y enlaces que salgan de ella. No se sustituyen archivos personales ni entregas diferentes.

El contrato valida estructura e integridad, **no demuestra por sí solo que un enlace sea real, que las métricas sean actuales o que una imagen represente semánticamente su prompt**. Esas comprobaciones deben proceder del trabajo de investigación/revisión, conservando su evidencia.

## ChatGPT como cerebro

La tarea semanal existente continúa los **domingos a las 10:00, Europe/Madrid**. Su instrucción se actualizó para exactamente diez ideas, cuatro perfiles, datos observados separados de inferencias, ID de informe y JSON compatible. Prohíbe operaciones de vidIQ con créditos o coste desconocido. No se creó otra tarea ni se ejecutó ahora para rellenar referencias ficticias. En la consulta de estado no había un resultado semanal registrado que importar.

ChatGPT debe recuperar el informe identificado, investigar las referencias accesibles y suministrar un guion original `video-factory-job/v1` y metadatos. El brief conserva gancho, ritmo, punto de vista, formalidad, humor, suspense, transiciones y cierre como elementos a analizar; no autoriza copiar. A 18 minutos, el objetivo orientativo es unas 2.484 palabras ES o 2.610 EN. La duración final se mide con el audio, no con ese cálculo.

El valor inicial es **160 escenas**, configurable hasta el límite actual de 300 del importador. A 18 minutos y 160 escenas corresponden 6,75 s de media por imagen; no se obliga a que cada escena dure lo mismo. Más de 160 escenas aún requiere su validación de capacidad correspondiente.

La interfaz local permite incorporar informes/guiones pegando JSON y elegir «Haz el vídeo 3». Está preparada para interacción del asistente con el navegador **cuando el componente se ejecute en el PC del usuario**. No invoca ChatGPT por una API pagada ni utiliza endpoints ocultos de su web. Todavía no hay un enlace continuo probado entre el resultado del domingo y la carpeta del PC.

## Imágenes, voz y referencias

Se exportan prompts numerados con el importador existente. `media.request.json` fija guion, escena, voz y referencia opcional. La referencia puede incorporarse después por canal; se copia y valida su hash y se fija para nuevas selecciones, sin cambiar los encargos anteriores. Su ausencia no bloquea el brief ni la autoría.

Los perfiles siguen proponiendo **Mako / Gemini 3.8 Flash TTS**, con dirección por idioma/temática. Solo la muestra española anterior está generada. La autorización de una voz está agotada: **cuota autorizada nueva = 0**. Abrir una interfaz gratuita no permite asumir API gratis o capacidad suficiente para 18 minutos/cuatro canales. No se ha certificado el envío automático a la extensión Viral DNA ni su numeración después de reintentos.

Alternativas y limitaciones económicas en `ZERO-COST.md`; ninguna alternativa se activa de forma oculta cuando falla Google.

## Shorts con sentido narrativo

El modo de respaldo reutiliza **el mismo código de heurísticas locales de ClipFarming** (`automation/local-cuts.js`), separado del HTML. Emplea pausas/puntuación y señales textuales; no es un modelo que comprenda toda la historia ni una predicción de viralidad.

ChatGPT puede preparar junto al guion un plan editorial, guardado en los metadatos:

```json
{
  "title": "Título original",
  "description": "Descripción original",
  "tags": ["tema"],
  "editorialShorts": [
    {"firstScene": 12, "lastScene": 19, "title": "Una microhistoria completa", "reason": "Gancho, contexto y cierre están en estas escenas"}
  ]
}
```

Se convierte a segundos usando la alineación ya preparada, sin inventar tiempos. Se comprueba identidad del proyecto, orden, duración máxima de 150 s y ausencia de solapamientos. Si no cabe, se detiene para corregir el plan. La prueba sintética conectada produjo **tres Shorts de escenas completas** con auditoría correcta. La revisión editorial sigue marcada como pendiente en todas las entregas.

## Carpeta final y ordenador del usuario

La entrega incluye long.mp4, master-clean.mp4, Shorts MP4 separados, miniatura JPEG extraída del vídeo, título, descripción, etiquetas, guion, prompts, audio/imágenes originales, proyectos disponibles, JSON de entrega, preparación de YouTube e informe con hashes.

La miniatura es un fotograma, **no una miniatura diseñada ni evaluada por CTR**. En modo de medios existentes se conserva el `.avfproject` original; en modo de paquete de render se conserva ese paquete y el proyecto de ClipFarming. No se simula una escucha humana o una alineación que no exista.

Se probó escritura, organización, integridad y reapertura en el **entorno local de desarrollo**. **No se ha probado escritura en una carpeta del Windows del usuario.** El navegador conectado permite interacción/descargas, pero no proporciona acceso arbitrario al disco Windows desde el proceso de desarrollo.

Para probarlo allí hay que iniciar el componente local con Python, Node y FFmpeg/FFprobe instalados, poner ambos checkouts de desarrollo juntos y elegir una carpeta dedicada con permiso de escritura del usuario. No requiere administrador, hosting ni abrir el servidor a Internet. El servidor se vincula solo a 127.0.0.1; valida Host/Origin, formularios CSRF y no carga recursos externos. Cerrar una pestaña no detiene el proceso local; cerrar la aplicación o apagar/suspender el PC puede interrumpirlo y requerir reanudación.

## Uso

```powershell
py -3 tools\factory_local_app.py --doctor
tools\start-factory.cmd "D:\Videos\Fabrica"
```

La ruta es un **ejemplo para elegir**, no una carpeta a la que ya se haya escrito. Usar una carpeta nueva. El HTML se abre en la dirección local que muestre el proceso. La aplicación no se instala ni arranca sola en Windows.

CLI equivalente:

```sh
python tools/factory_orchestrator.py init /ruta/fabrica-nueva
python tools/factory_orchestrator.py import-report /ruta/fabrica-nueva radar.json
python tools/factory_orchestrator.py select /ruta/fabrica-nueva radar-2026-11-01-v1 'Haz el vídeo 3'
python tools/factory_orchestrator.py attach-script /ruta/fabrica-nueva ID job.json metadata.json
python tools/factory_orchestrator.py attach-media /ruta/fabrica-nueva ID assets.ready.json
python tools/factory_orchestrator.py work /ruta/fabrica-nueva --watch
```

`--watch` recibe sobres de bandeja y procesa trabajos listos; no completa guiones o generaciones ausentes. Para recuperación: `retry ROOT ID`, y opcionalmente `--reset-from ETAPA` cuando haya que reparar un resultado propio cambiado. No usarlo para sobreescribir una entrega personal alterada.

## Pruebas reproducibles

```sh
python -m unittest discover -s tests -p orchestrator_test.py -v
node tests/local-app-browser.cjs
python tests/run-orchestrator-existing.py /ruta/medios-prueba-real /ruta/fabrica-prueba
node tests/delivery-browser.cjs /ruta/entrega
```

`CHROMIUM_EXECUTABLE` permite elegir un Chromium aislado existente. Estas pruebas no controlan Brave personal ni generan contenido en Google. Pasaron **11 pruebas Python del orquestador, 4 Python del motor anterior, 6 Node de AutoVideo y 4 Node de ClipFarming**, más las dos comprobaciones UI indicadas. Las pruebas nuevas se revalidaron tras recuperar el entorno temporal; no se repitió la carga de 18 minutos.
