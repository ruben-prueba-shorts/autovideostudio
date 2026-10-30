# Validación de la fábrica — 30 de octubre de 2026

**La integración con material real NO está completada.** No se generó voz ni imagen ni se consumieron cuotas. Los resultados siguientes usan JPEG de prueba y un tono sintético; no certifican narración natural ni alineación acústica. Detalle reproducible en `FACTORY-RUNBOOK.md` y datos en `validation/factory-results.json`.

## Render local FFmpeg: pruebas ejecutadas

Imágenes únicas de 1920×1080; salida 1280×720, 30 fps constantes, H.264/yuv420p + AAC/48 kHz, subtítulos incrustados y faststart. Todas las salidas se decodificaron completas.

| Duración | Imágenes | Render y validación interna | Pico RSS por proceso FFmpeg | Tamaño MP4 | Resultado |
|---|---:|---:|---:|---:|---|
| 2 min | 18 | 72.8 s | 139.4 MiB | 10.6 MB | Pasa |
| 5 min | 44 | 169.6 s | 139.6 MiB | 26.1 MB | Pasa |
| 10 min | 89 | 340.7 s | 139.7 MiB | 52.8 MB | Pasa |
| 18 min | 160 | 610.9 s | 142.5 MiB | 95.0 MB | Pasa |

El tiempo incluye la comprobación interna de decodificación. La auditoría independiente añadió unos segundos; está registrada aparte. El pico es el máximo comunicado por **cada proceso FFmpeg**, no el total de RAM de Python, el generador de fixtures o el sistema. Las pruebas se solaparon con otras tareas; no son una comparativa controlada de rendimiento ni una predicción para el PC del usuario.

Comprobación independiente: se decodificó un punto central de **cada escena** en los cuatro vídeos largos (18/44/89/160 puntos) y se comparó su color de referencia para detectar cambios de orden. Error máximo RGB: 2. Se comprobó texto visible en el área de subtítulos del primer fotograma muestreado, y tono/RMS cerca del inicio y del final. Eso no equivale a verificar cada palabra de una narración real.

Prueba adicional de 30 s a **1920×1080/60 fps**: pasa H.264/AAC, duración y decodificación; 39.0 s y 253.3 MiB de pico por proceso FFmpeg. No se probó una exportación de 18 minutos con ese perfil.

## AutoVideo en Chromium aislado

| Línea temporal sintética | Imágenes | Carga/restauración | Pico de heap JavaScript |
|---|---:|---:|---:|
| 2 min | 18 | 2.0 s | 41.2 MiB |
| 5 min | 44 | 4.8 s | 142.6 MiB |
| 10 min | 89 | 9.7 s | 194.9 MiB |
| 18 min | 160 | 38.2 s | 512.3 MiB |

Para 160 imágenes se guardó un `.avfproject` de **177.561.863 bytes**, se cerró la pestaña y se reabrió el archivo: se compararon las huellas de las 160 imágenes originales y sus dimensiones de 1920×1080, el orden, el encargo y la duración. En esa prueba no había una narración larga cargada.

El heap JavaScript **no incluye** toda la memoria nativa de imágenes decodificadas, vídeo, WebAudio o GPU. No fue posible obtener un RSS fiable del navegador por la separación de procesos del entorno: no se inventa una cifra total ni se certifica estabilidad en otro equipo.

Exportación real del editor con audio sintético de 30 s: **pasa**, 29.977333 s de salida en unos 30.2 s, VP9/Opus. Su entrega y clip vertical también pasaron.
Exportación de 120 s bajo carga concurrente: **no pasa** el margen de 0,15 s; salida de 120.163833 s. Se conservó el vídeo para analizarlo y no se relajó el límite. No se continuó a un render de navegador de 18 minutos: la ruta local ofrece tiempos controlados y memoria acotada.

## Recuperación, cola y contratos

- 6 pruebas Node de encargos, lotes numerados, entregas y asociación por huellas: pasan.
- 4 pruebas Python con FFmpeg real: pasan. Cubren cuatro canales, rechazo de material real sin revisión, conversión de proyecto, paquetes inmutables, cola idempotente, leases, interrupción y reparación de un fragmento.
- Prueba UI del manifiesto: un hash incorrecto deja el lote intacto; el manifiesto correcto se importa, y el ID original del prompt/huella sobreviven guardar y reabrir.
- En una copia del trabajo de 18 min se corrompió un fragmento, se reparó y se provocó una interrupción después del checkpoint. La reanudación reutilizó los 160 fragmentos sin recodificarlos. La salida completa se decodificó y conservó 1080 s.
- La comparación SHA-256 del maestro recuperado y el original dio **idénticos**.
- Las pruebas de los dos editores bloquearon solicitudes externas y no observaron errores JavaScript de página ni peticiones a proveedores de generación.

## ClipFarming PR #2

Importación de maestro **H.264/AAC** generado por el render local, con JSON y cuatro cues: pasa en la interfaz real de ClipFarming. Exportación vertical: 720×1280, 30.002133 s, audio presente, en 30.5 s. El exportador estándar produjo VP9/Opus; la copia normalizada con FFmpeg a H.264/AAC y faststart pasa la auditoría (30,075632 s). Es un clip sintético, no el primer Short real solicitado.

## Límites para producción

- Faltan originales descargados de Viral DNA, su numeración real y el comportamiento de reintentos. Se observaron los prompts originales 102/110/97; no se ha certificado el lote exportado.
- Flash TTS 2.5 tiene nivel gratuito documentado y Run está habilitado sin clave en la cuenta observada. Falta autorización para una sola generación, disponibilidad efectiva de cuota, escucha, descarga del audio y sincronización real en español; después repetir en inglés. No se vincularán claves pagadas.
- El render local conserva imágenes, voz y bloques de subtítulos; no replica aún música/SFX, transiciones, movimientos de cámara o palabra activa.
- La carga estable de 160 imágenes y el render local sintético de 18 minutos no demuestran por sí solos una fábrica real desatendida ni una producción larga Full HD/60 fps.
- La cola parte de medios/alineación ya preparados. Faltan automatización de transferencia desde Google, generación por tramos autorizados, alineación y controles de calidad acústicos, catálogo de ideas, elección editorial de Shorts y servicio local que ejecute el ciclo completo.
- Nada se ha desplegado, fusionado o publicado. Ambos PR continúan en borrador.
