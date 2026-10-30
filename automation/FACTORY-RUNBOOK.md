# Fábrica local: medios existentes → montaje → revisión

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

1. Abrir Text-to-speech y seleccionar **Gemini 2.5 Flash Preview TTS** (no inferir que cualquier modelo TTS es gratuito).
2. Seleccionar voz y dirección constantes según `channel-profiles.json`. Son propuestas aún sin validación acústica: Charon para rangos y Orus para finanzas, con variantes ES/EN.
3. Pegar el guion exacto. La cuota depende de la cuenta/modelo; Run habilitado sin clave es una observación de interfaz, no garantía de generación disponible.
4. **Antes de Run o de una previsualización que genere audio**, obtener autorización específica para consumir cuota. Nunca activar facturación ni vincular una clave pagada. Ante error de cuota, detener, conservar trabajo y registrar el motivo.
5. Descargar el resultado existente mediante su control de descarga y verificar archivo/duración. Ese control y su formato aún no se han observado con una generación real en esta fase; no se inventa que la descarga está resuelta.

Google documenta nivel gratuito para Flash TTS 2.5: https://ai.google.dev/gemini-api/docs/pricing#gemini-2.5-flash-preview-tts . Pro TTS y los modelos nuevos tienen condiciones distintas. No se garantiza capacidad gratuita para cuatro canales a escala.

Para 18 minutos, preparar tramos de texto razonables (p.ej. 45–90 s), misma voz/dirección y guion sin reformular. Concatenar audio sin volver a sintetizar escenas completadas y alinear después. El troceado, generación, concatenación automática y medición acústica con voces reales siguen pendientes. No se han consumido cuotas para probarlos.

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
