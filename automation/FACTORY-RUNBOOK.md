# Fábrica local: medios existentes → montaje → revisión

El orquestador central implementado añade selección «Haz el vídeo 3», informes versionados, etapas persistentes, bandeja automática, Shorts y entrega organizada. Consultar `ORCHESTRATOR.md`, `ZERO-COST.md` y `validation/orchestrator-results.json`. Este documento conserva las instrucciones del motor y de la prueba anterior; no hay que repetir las pruebas largas ya completadas.

Continúa AutoVideo PR #3 y ClipFarming PR #2. No hay generación, facturación, despliegue ni publicación en estos ejecutables. El objetivo «Vídeo 1 desde una idea» aún requiere guion, medios y alineación; la selección por catálogo implementada aquí parte de un paquete de medios ya terminado.

## Requisitos

- Node >=20 para las herramientas de asociación y los contratos.
- Python >=3.10, FFmpeg/FFprobe con libx264 y libass para renderizar. El render usa biblioteca estándar de Python.
- Pruebas de navegador: `npm ci`, `npx playwright install chromium`. Se puede indicar `CHROMIUM_EXECUTABLE` para un binario existente.
- Solo las pruebas de carga y la inspección de fotogramas usan Pillow; versión observada: 12.3.0.
- Instalación opcional para esas pruebas: `python3 -m pip install -r requirements-test.txt`.
- Proyectos, audios, imágenes, SQLite y exportaciones permanecen fuera de Git. No introducir claves en ningún JSON.

## 1. Asociar archivos existentes sin depender del orden de descarga

`tools/bind-assets.cjs` crea una **carpeta nueva** con imágenes numeradas y `bindings.json`. La selección es una revisión explícita; el programa no reconoce el contenido visual ni demuestra su origen en Google. Sí evita cambios posteriores de archivo, prompt, narración y número de escena.

Esquema de `selection.json`, situado dentro de la carpeta de activos del encargo:

```json
{
  "format": "video-factory-selection/v1",
  "jobId": "football_real_smoke_001",
  "reviewed": true,
  "scenes": [{
    "sceneIndex": 1,
    "path": "imagen-original.png",
    "sha256": "HUELLA_SHA256_REAL_DEL_ARCHIVO",
    "prompt": "PROMPT_EXACTO_DEL_ENCARGO_NORMALIZADO",
    "sourcePromptId": "102"
  }]
}
```

Incluir una entrada por escena. Las rutas y enlaces simbólicos no pueden salir de esa carpeta. Debe haberse revisado la selección antes de marcarla. Para reutilizar las tres imágenes observadas, los IDs originales son 102, 110, 97; los nuevos números de archivo son 0001, 0002, 0003. Conservar los originales.

```sh
node tools/bind-assets.cjs automation/real-smoke-job.json /ruta/activos/selection.json /ruta/activos/lote-nuevo
```

En AutoVideo, importar el encargo y después **Carpeta de Flow**, incluyendo `bindings.json`. El importador verifica SHA-256 de imagen, prompt y narración antes de incorporar el lote. Rechaza todo el lote si algo difiere. Se guardan el ID del prompt de origen y la huella del manifiesto en `.avfproject`.

Sin `bindings.json`, se conserva el importador numerado anterior: verifica nombres y cantidad, pero **no certifica** la correspondencia semántica con los prompts. No mezclar generaciones/reintentos sin revisar.

## 2. Voz principal: AI Studio gratuito, sin API pagada

1. Abrir Text-to-speech y comprobar el modelo y la tarifa gratuita actuales. En la prueba real se usó **Gemini 3.8 Flash TTS** (`gemini-3.8-flash-tts`) y **Mako**, disponibles en el selector de esta cuenta.
2. Mantener la dirección de `channel-profiles.json`. Solo se ha generado una muestra española de fútbol; los otros tres perfiles son propuestas sin prueba acústica. No seleccionar Charon por defecto.
3. Pegar el guion exacto. Run habilitado sin clave es una observación de interfaz, no garantía de cuota disponible ni de coste por sí sola.
4. **Antes de Run o de una previsualización que genere audio**, obtener autorización específica para consumir cuota y comprobar la tarifa gratuita. La autorización de esta fase fue **una sola generación gratuita**, ya consumida: no volver a pulsar Run/Preview ni reintentar por un fallo de descarga. Nunca activar facturación ni vincular una clave pagada.
5. Recuperar el resultado existente y comprobar hash, duración y formato. Esta vez el control Download no produjo un archivo accesible al proceso de montaje. Se recuperaron los bytes del WAV que ya alimentaba el reproductor (`audio.currentSrc`), sin generar otra voz. No se garantiza que todas las versiones de AI Studio mantengan este mecanismo.

Google documentó entrada y salida gratuitas para Flash TTS 3.8 en la fecha de prueba: https://ai.google.dev/gemini-api/docs/pricing . Se ejecutó sin clave seleccionada, no se activó facturación ni se vinculó una clave de pago. Resultado real: WAV PCM16 mono de 24 kHz y 25,8 s. Esto acredita la ruta gratuita usada, no una auditoría de la factura ni capacidad gratuita ilimitada para cuatro canales.

Para 18 minutos, preparar tramos de texto razonables (p.ej. 45–90 s), misma voz/dirección y guion sin reformular. Concatenar audio sin volver a sintetizar escenas completadas y alinear después. El troceado, generación, concatenación automática y medición acústica con voces reales siguen pendientes. La muestra corta no valida todavía ese proceso por tramos ni una narración larga.

## 3. AutoVideo y alternativa FFmpeg

Cargar voz e imágenes en AutoVideo, ejecutar sincronización **local**, revisar las palabras y límites de escena y guardar el `.avfproject`. No convertir tiempos estimados en verificados para una producción real.

Si el navegador no es la opción adecuada para el render largo, extraer el proyecto sincronizado a una carpeta nueva:

```sh
python3 tools/project_to_bundle.py mi-video.avfproject inbox/mi-video --channel life-ranges-es --reviewed-alignment
```

Para material real exige tiempos reconocidos, proyecto verificado y revisión humana explícita. Es un control del proceso, no una nueva comprobación acústica independiente. Conserva bytes originales, guion, prompts, números de escena y las marcas de palabra para crear bloques de subtítulos. No incluye todavía SFX, música de fondo, movimientos de cámara, transiciones o resaltado de palabra activa del editor; renderiza cortes estáticos y bloques de texto con borde y sin caja opaca.

```sh
python3 tools/local_factory.py scan factory.sqlite inbox
python3 tools/local_factory.py list factory.sqlite
python3 tools/local_factory.py work factory.sqlite exports --height 720 --fps 30 --burn-subtitles
```

La cola es SQLite persistente, compartida por los cuatro perfiles. Reclama un trabajo mediante transacción y lease con heartbeat. Termina en **review**, nunca en «publicado». No hay daemon activo ni generación automática. `scan` solo examina `*/render.ready.json` dentro de la carpeta indicada; no busca en carpetas personales. El productor debe escribir el manifiesto ready al final mediante renombrado atómico y mantener inmutables sus activos.

Los fallos quedan registrados. Para reanudar:

```sh
python3 tools/local_factory.py retry factory.sqlite IDENTIFICADOR
python3 tools/local_factory.py work factory.sqlite exports --height 720 --fps 30 --burn-subtitles
```

Máximo tres intentos; reintento explícito, no infinito. Un worker perdido caduca tras 120 s sin heartbeat y requiere reintento. Cada fragmento completado lleva huella y número de fotogramas. Un fragmento ausente o dañado se regenera; los intactos se reutilizan. Un manifiesto o activo cambiado se rechaza. Se pueden acumular fragmentos de un trabajo fallido: no se eliminan originales ni carpetas ajenas. El render final usa H.264/yuv420p, AAC a 48 kHz y faststart, comprueba duración y decodifica ambas pistas antes de finalizar.

Para renderizar otra variante (por ejemplo, maestro limpio para reencuadrar):

```sh
python3 tools/local_factory.py render inbox/mi-video/render.ready.json exports --height 1080 --fps 60
```

Sin `--burn-subtitles` el MP4 queda limpio; `captions.ass` y los cues del JSON acompañan al vídeo. Las variantes tienen directorios distintos según el contenido/configuración. La opción 1080p60 no equivale a certificar una exportación de 18 minutos con ese perfil; consultar las pruebas ejecutadas.

Catálogo de paquetes ya listos, guardado dentro del proyecto:

```json
{"Vídeo 1":{"manifest":"inbox/mi-video/render.ready.json"}}
```

```sh
python3 tools/local_factory.py select factory.sqlite catalog.json 'Vídeo 1'
```

Seleccionar de nuevo el mismo paquete no duplica trabajos. Esto no genera todavía el guion ni solicita imágenes/voz desde una idea.

## 4. Entrega y revisión

Cada render crea `master.mp4`, `master.clipfarming.json`, `captions.ass`, `checkpoint.json` y `result.json`. Importar vídeo + JSON juntos en ClipFarming PR #2. Los cortes deben estar definidos en el paquete o elegirse en el editor. La selección editorial autónoma de Shorts sigue pendiente.

Si ya se incrustaron subtítulos, ClipFarming evita duplicarlos; revisar que el encuadre vertical no los recorte. Para máxima libertad usar maestro limpio y cues. El exportador estándar de este Chromium produjo VP9/Opus; si se requiere H.264/AAC, normalizar una copia con FFmpeg según `REAL-INTEGRATION.md` y volver a auditar. No cambiar un vídeo manteniendo un JSON con hash antiguo.

```sh
node tools/audit-mp4.cjs master.mp4 DURACION horizontal
node tools/audit-mp4.cjs short-final.mp4 DURACION vertical
```

Escuchar el audio y revisar encuadre, texto y sincronía sigue siendo obligatorio antes de aprobar una producción. Ninguna herramienta de esta fase publica en YouTube.

## Pruebas reproducibles

```sh
npm test
npm run test:local
CLIPFARMING_DIR=/ruta/clipfarming npm run test:browser
python3 tests/stress_factory.py .test-artifacts/stress
python3 tests/inspect-synthetic.py .test-artifacts/stress/results.json
python3 tests/stress_factory.py .test-artifacts/browser-fixtures --stages 1080 --prepare-only
node tests/load-browser.cjs
CLIPFARMING_DIR=/ruta/clipfarming node tests/offline-handoff-browser.cjs /ruta/render/master.mp4
```

Las pruebas de carga usan ruido/etiquetas y un tono, nunca narración real. `SYNTHETIC_RENDER_SECONDS=30` o `120` junto a `HANDOFF_ONLY=1` ejecutan los recorridos sintéticos ampliados de `tests/browser.cjs`; requieren también FFprobe. Los navegadores aislados bloquean solicitudes externas. Las cifras medidas pertenecen al entorno de pruebas, no al PC del usuario.

## Recorrido real reproducible con los mismos archivos (sin generar)

La prueba optativa vive en `tests/real-integration-browser.cjs`; no forma parte de `npm test`, no pulsa Run y no contiene claves ni archivos personales. Necesita una carpeta con `numbered/0001.jpg`, `0002.jpg`, `0003.jpg`, `bindings.json` dentro de `numbered/`, y `mako-gemini-3.8.wav` junto a la carpeta. El encargo es `automation/real-smoke-job.json`. Ver detalles y límites en `REAL-INTEGRATION.md`.

```sh
node tests/real-integration-browser.cjs align /ruta/prueba-real
node tests/real-integration-browser.cjs render /ruta/prueba-real
node tools/finalize-mp4.cjs /ruta/prueba-real/autovideo-browser.mp4 /ruta/prueba-real/master-h264.mp4 25.8 horizontal
node tools/finalize-mp4.cjs /ruta/prueba-real/autovideo-captioned-browser.mp4 /ruta/prueba-real/video-real-horizontal.mp4 25.8 horizontal
node tests/real-integration-browser.cjs handoff /ruta/prueba-real
node tests/real-integration-browser.cjs clip /ruta/prueba-real
```

Normalizar el Short con su duración real (el límite de corte está en `clip-settings.json`), después ejecutar `python3 tests/inspect-real.py /ruta/prueba-real`. Dependencias opcionales: `requirements-inspection.txt`, FFmpeg, FFprobe y Tesseract con inglés. La inspección compara la voz en tres ventanas, clasifica las tres imágenes y muestrea un fotograma por cue. El OCR puede fallar sobre dibujos detallados: conservar los resultados y revisar visualmente sus discrepancias. La correlación suma el inicio de la pista de audio al desfase de muestras; omitirlo daría una medida incorrecta de sincronía absoluta.

`finalize-mp4.cjs` produce H.264/yuv420p, AAC a 48 kHz, 30 fps y faststart, preserva el original, rechaza sobrescrituras y publica la copia solo después de la auditoría. Deja un recibo `.audit.json` con huellas y medidas. No arregla un montaje desincronizado ni sustituye la revisión editorial; no usar su normalización para ocultar un fallo de duración. Se debe preparar el JSON de entrega **después** de normalizar el maestro.

En el entorno de pruebas, Chromium no descargaba directamente las dependencias ASR. `tools/cache-public-model.py` usa GET HTTPS normal a los CDN/modelos públicos aprobados y conserva una caché local; no envía el audio, no consulta una API de inferencia y no altera TLS. El resto de solicitudes externas se bloquean en el navegador aislado. El helper limita descargas y sigue redirecciones solo a los mismos dominios de modelos/CDN aprobados.
