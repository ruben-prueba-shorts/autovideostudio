# Primera integración real — 30 de octubre de 2026

**Se ha producido el vídeo real corto y un Short vertical.** Tres imágenes existentes de Flow, una sola narración autorizada en AI Studio, montaje/alineación/exportación en AutoVideo PR #3 y recepción/exportación vertical en ClipFarming PR #2. Se ejecutaron los editores de las ramas en Chromium aislado local; no se modificaron las webs públicas, no se fusionó nada y no se publicó en YouTube.

Medidas, huellas y límites: `validation/real-30-results.json`. Las pruebas de 2/5/10/18 minutos de `FACTORY-VALIDATION.md` pertenecen a la fase anterior y usan material sintético. No se repitieron en esta fase.

## Imágenes recuperadas sin generar

Se abrió cada recurso existente en Flow y su panel de información. Se comprobó el prompt completo y el título; después se descargaron los bytes del JPEG completo observado en la imagen de solo lectura. No se volvió a generar, mejorar ni recodificar ninguna imagen. Los tres archivos son de **1376 × 768**.

| Escena nueva | Prompt de origen | Contenido contrastado visualmente | Archivo del nuevo lote |
|---|---:|---|---|
| 1 | 102 | Futbolista en un estadio, televisores y comentaristas de distintos países | `0001.jpg` |
| 2 | 110 | Futbolista en camilla, médico, pierna y panel de cargas de entrenamiento | `0002.jpg` |
| 3 | 97 | Futbolista levantando un trofeo con compañeros y confeti | `0003.jpg` |

El prompt exacto está en `real-smoke-job.json`. `tools/bind-assets.cjs` produjo una carpeta nueva con `bindings.json`: conserva los IDs 102/110/97 independientemente del orden nuevo 1/2/3 y vincula mediante SHA-256 los bytes, el prompt y la narración. No se dedujo la relación a partir del orden cronológico.

**Límite de Viral DNA:** su panel no está expuesto como pestaña controlable. La configuración observada anteriormente mostraba numeración desde 1, carpeta por ejecución y reintentos al final, pero no se ha certificado su exportación por lotes ni la asociación automática después de reintentos. Las descargas previas de miniaturas producían nombres genéricos `unnamed.webp`; no preservaban los IDs. La recuperación actual usa los recursos completos de Flow, no demuestra el nombre que asignaría Viral DNA. Las URL de recursos no se publican, no se consideran estables entre sesiones y no se guardan como enlaces permanentes.

No hace falta que el usuario aporte ahora estas tres imágenes: ya están recuperadas. Para lotes futuros, guardar una carpeta nueva con imágenes y un manifiesto de escena/prompt; si Viral DNA solo numera por cronología, revisar la selección antes de crear `bindings.json`.

## Voz y coste

Se eligieron **Mako** y **Gemini 3.8 Flash TTS** (`gemini-3.8-flash-tts`), ambos disponibles en la interfaz observada. Se corrigió la preparación antigua de 2.5/Charon: no se usó Charon.

Mako es la referencia del usuario y aparece descrita como voz de tono grave y expresivo. Encaja con la energía del fútbol; se dirigió como documental cercano, sin exageración publicitaria. La ficha oficial de Flash TTS 3.8 destaca fidelidad de voz, expresividad y estabilidad para formatos largos. Esto justifica la selección inicial; **no es una comparación acústica A/B** con otras voces o modelos, que habría necesitado generaciones adicionales.

Dirección exacta:

> Español de España. Narración documental natural y expresiva, cercana y clara. Ritmo moderado, pausas breves, sin tono publicitario ni exageración.

Se utilizó el guion de 67 palabras de `real-smoke-narration.txt`, sin reformularlo. Resultado: WAV PCM16, mono, 24 kHz, **25,8 segundos**, 1.238.444 bytes. Es aproximadamente la prueba de 30 segundos solicitada; no se ralentizó ni se añadió silencio para aparentar una duración exacta.

**Una sola pulsación de Run. Cero reintentos y cero previsualizaciones generativas adicionales.** El registro de esa autorización queda agotado. El control de descarga no entregó un archivo accesible al montaje; se recuperó el WAV que ya alimentaba el reproductor a partir de su recurso DOM. Recuperar esos bytes no llamó al modelo otra vez.

Base comprobada de gratuidad: la tarifa oficial del modelo indicaba entrada y salida gratuitas en Free Tier; AI Studio ejecutó con **No API key selected**, sin activar facturación ni vincular una clave de pago. Coste incremental de generación por esta ruta: **0 €**, una cuota gratuita utilizada. No se inspeccionaron facturas ni se afirma una auditoría contable de la cuenta. Esta prueba tampoco acredita cuota gratuita suficiente para cuatro canales a escala.

Fuentes oficiales consultadas:

- https://ai.google.dev/gemini-api/docs/pricing
- https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash-tts
- https://ai.google.dev/gemini-api/docs/google-ai-plans

`channel-profiles.json` propone Mako/3.8 para los cuatro canales, con dirección documental para rangos y contenida/precisa con cifras para finanzas, en ES/EN. **Solo la muestra de fútbol en español fue generada y analizada.** Los otros perfiles y la aprobación subjetiva de naturalidad por el usuario siguen pendientes; no se presentan como voces ya comparadas o validadas.

## Montaje y verificaciones reales

1. Importación del encargo `football_real_smoke_001` y carpeta numerada con bindings en AutoVideo. El importador heredado de PR #1 funcionó con los medios reales de PR #3.
2. Carga del WAV y sincronización **local** mediante Whisper base: **67 de 67 palabras reconocidas**, sin tiempos reconstruidos. No se envió el audio a una API ni se consumió cuota para reconocerlo.
3. Tres escenas, índices de imagen 0/1/2, con límites reconocidos **0–7,12 / 7,12–16,36 / 16,36–25,8 s** y 25 bloques de subtítulos.
4. Guardar `.avfproject`, cerrar el contexto del navegador y abrirlo en almacenamiento nuevo: imágenes decodificadas y comparadas, audio de 25,8 s y tiempos/asociaciones conservados.
5. Exportación real de AutoVideo: maestro limpio para reencuadrar y versión horizontal con subtítulos blancos incrustados. Se eligieron **cortes directos** para inspeccionar la sincronía sin la mezcla temporal de un fundido. Se conservó internamente una primera exportación con fundidos como evidencia, no como otra generación de voz.
6. El Chromium de prueba grabó VP9/Opus. `tools/finalize-mp4.cjs` normalizó copias a H.264/AAC y las auditó; no se afirma que el exportador web produzca H.264 de forma nativa en todos los navegadores.
7. Se volvió a preparar la entrega **con el MP4 limpio final**, comprobando tamaño, duración y SHA-256. ClipFarming importó vídeo y JSON, identificador, modo local y los 25 cues. Se eligió el intervalo completo de esta muestra como un Short; no se probó selección editorial automática desde un vídeo largo.
8. ClipFarming exportó 720 × 1280, imagen completa centrada sobre fondo difuminado y subtítulos colocados para vertical. Su copia final también se normalizó/auditó a H.264/AAC.
9. Inspección independiente: FFprobe, faststart, 30 fps, yuv420p y decodificación íntegra de ambas pistas. Comparación de imágenes y audio en tres puntos del vídeo, muestreo de un fotograma por cue y revisión de las discrepancias OCR. La correlación de audio incluye el inicio temporal de la pista, no solo las muestras PCM.

**Alcance de la aceptación:** se comprueba integridad, contenido, orden, duración, alineación automática y presentación. No se hizo una prueba de subida a YouTube ni una comparación subjetiva de naturalidad por un oyente. Esa aprobación editorial queda pendiente. Ningún indicador `verified` fue fabricado para esta prueba; surgió de ejecutar el reconocimiento real del editor.

| Archivo final | Medida real | Perfil | Auditoría |
|---|---|---|---|
| Maestro limpio para ClipFarming | 25,800146 s, 1280×720 | H.264/AAC, 30 fps | Pasa |
| Vídeo horizontal subtitulado | 25,819938 s, 1280×720 | H.264/AAC, 30 fps | Pasa |
| Short vertical subtitulado | 25,746917 s, 720×1280 | H.264/AAC, 30 fps | Pasa |

La comparación de forma de onda, incluyendo el inicio temporal de la pista, mide un retraso estable de **55,5 ms** en el horizontal y **71,4 ms** en el Short respecto al WAV. Las tres ventanas de cuatro segundos —inicio, mitad y final— dan el mismo desfase: no se detectó deriva acumulada en esta muestra. Correlación mínima: 0,990 en horizontal y 0,996 en vertical. La última palabra reconocida termina antes del final de ambas salidas.

El OCR leyó exactamente **25/25 bloques** del Short y **18/25** del horizontal tras normalizar mayúsculas/acentos/puntuación. Se revisaron visualmente las siete discrepancias horizontales (cues 2, 7, 10, 18, 21, 22 y 24): texto completo y correcto, con errores del OCR sobre el dibujo. No se convierten esos errores de OCR en supuestos aciertos automáticos. Los dos cambios de imagen se localizaron aproximadamente en **7,02 y 16,26 s**, muestreados cada 40 ms: unos 0,10 s antes de sus límites ASR, coherentes con el adelanto visual configurado. La calibración y escucha editorial final por el usuario siguen pendientes.

Pasaron además **6 pruebas Node de AutoVideo, 4 Python de la fábrica y 2 Node de ClipFarming**, sin errores de página en el recorrido real. El normalizador rechazó sobrescribir una salida existente y su cálculo de hashes por bloques produjo el mismo MP4 que el cálculo anterior. No se repitieron las pruebas largas sintéticas.

## Reproducibilidad y fallos encontrados

`tests/real-integration-browser.cjs` ejecuta las etapas `align`, `render`, `handoff` y `clip` con los archivos ya existentes. `tests/inspect-real.py` mide conservación del audio, compara imágenes y registra los resultados OCR. Requisitos y comandos en `FACTORY-RUNBOOK.md`.

- Chromium no accedía directamente al CDN del motor local. Se recuperaron dependencias públicas mediante HTTPS normal y caché local, con dominios y tamaño limitados, sin modificar TLS ni subir el audio.
- Los eventos de descarga de AI Studio/Flow no dieron archivos accesibles al proceso de montaje. Recuperar el recurso existente evitó repetir generaciones. No se certifica aún un adaptador de transferencia estable en el PC del usuario.
- El navegador personal rechazó un sondeo con URL `data:` por su política de protocolos. No se repitió ni se intentó eludir; el montaje se realizó en el entorno de pruebas aislado del checkout, con archivos recuperados.
- El normalizador rechaza una salida ya existente. Se probó este rechazo y se verificó que conserva el archivo original. No se relajan los 0,15 s de tolerancia para hacer pasar una exportación.

## Para vídeos largos y ejecución desatendida

Ya existen cola SQLite de cuatro canales, paquetes con hashes, checkpoints y recuperación de render FFmpeg. La fase anterior pasó 18 minutos/160 imágenes **sintéticas** a 720p30 y guardar/reabrir 160 imágenes. Eso no acredita todavía 18 minutos de narración real, inglés, sincronía de 160 escenas o exportación larga Full HD/60 fps.

Falta estabilizar la transferencia de Flow/Viral DNA con IDs de escena y reintentos; obtener voces por tramos con presupuesto autorizado y sin regenerar tramos completos; probar alineación extensa en ambos idiomas; medir memoria total/tiempo en el equipo de producción; conectar el ejecutor de la cola con esas adquisiciones y su revisión; y seleccionar Shorts editoriales automáticamente. El puente `.avfproject` → FFmpeg exige revisión explícita de la alineación real: no se ha marcado una escucha humana inexistente para saltarlo.

Para seguir sin gasto se pueden reutilizar exactamente estos archivos en pruebas del código y de recuperación. Para nuevas voces —incluidas pruebas inglesas o narración larga— se necesita otra autorización específica. Antes de fijar el perfil del canal, el usuario debe escuchar el vídeo y valorar naturalidad, acento y ritmo. No hace falta una contraseña ni una clave API.
