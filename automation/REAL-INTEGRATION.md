# Integración real — estado del 30 de octubre de 2026

Consulta también `FACTORY-RUNBOOK.md` y `FACTORY-VALIDATION.md` para el render local, la cola y las pruebas sintéticas de capacidad. Estas pruebas no sustituyen los cinco pasos con material real.

Los PR AutoVideo #3 y ClipFarming #2 siguen en borrador. No se fusionan ni despliegan. No se generan imágenes ni voces sin autorización de gasto.

## Observaciones reales

- Brave está conectado. El proyecto abierto de Flow contiene imágenes de fútbol ya generadas; se observó el prompt completo de una de ellas. No se pulsó generación.
- El menú de descarga de Flow distingue **1K Tamaño original** de **2K Resolución mejorada**. Solo se seleccionó el original. El evento de descarga no se recibió en 20 segundos; no se certifica el nombre final ni el archivo original descargado. No se solicitó mejora de resolución.
- Se pudieron empaquetar tres imágenes WebP observadas en la página mediante la herramienta del navegador. Son recursos de vista previa `s1600-rw`, no una exportación original certificada. Están en el entorno del navegador, no en el checkout de pruebas. No se importaron en AutoVideo ni se subieron al repositorio.
- AI Studio está autenticado. La vista History / My files no mostró archivos reutilizables; no se inspeccionaron carpetas personales ni se amplió acceso a Drive. Se seleccionó **Gemini 2.5 Flash Preview TTS**, disponible en el selector y con nivel gratuito en la documentación oficial. **Run queda habilitado sin clave seleccionada**. Abrir el selector de claves ofrece vincular una API pagada, pero eso no demuestra que sea obligatoria para ejecutar la interfaz gratuita. Se corrige así la conclusión demasiado amplia de la fase anterior. No se pulsó Run ni Preview, por lo que la cuota disponible de esta cuenta y la descarga del audio siguen sin probarse. El borrador con voz Charon, dirección en español y tres escenas queda preparado; falta autorización para una única generación gratuita, sin reintentos ni facturación.
- En la captura de Viral DNA proporcionada el 29 de octubre se ve **Numerado**, inicio **1**, carpeta nueva por ejecución y ejemplo `0001.mp4` (es una previsualización, no prueba del sufijo de imagen). La opción **Descargar lo generado** indica desplazar la galería hasta el final para descargar desde lo más antiguo. Hay reintentos al final. Falta comprobar el lote real, extensión, relación con prompts, selección de elementos anteriores y numeración de reintentos. El panel de la extensión no aparece en las pestañas controlables actuales.

**No dar por validada la numeración de Viral DNA con estas observaciones.** Una carpeta nueva evita mezclar archivos locales, pero no garantiza que la galería descargada sea exclusivamente el encargo. Tampoco se pueden recuperar números de prompt desde imágenes renumeradas solo por orden cronológico.

El ejemplo `real-smoke-job.json` conserva ahora **tres prompts originales observados en Flow**, con IDs de origen 102, 110 y 97, en ese orden para una narración nueva. La imagen del Mundial corresponde a la escena 1; la de fisioterapia, a la 2; la del trofeo, a la 3. La numeración del archivo de este nuevo encargo debe ser 0001/0002/0003, sin perder los IDs originales en `bindings.json`. El texto nuevo tiene 67 palabras y dura aproximadamente 30 segundos a ritmo moderado, pero aún no se ha generado ni medido el audio. Falta recuperar los originales y comprobar visualmente que son los archivos elegidos.

## Cinco pasos solicitados

1. Exportación/numérico de Viral DNA: configuración observada en captura y tres prompts originales identificados; lote real pendiente.
2. Narración AI Studio: archivo real pendiente. Se ha preparado Flash TTS 2.5 con Run habilitado sin clave. Hace falta autorizar una sola generación de cuota gratuita o aportar un audio ya generado con su guion exacto. No se vincularán claves pagadas ni se activará facturación.
3. Importación y sincronización: pendiente de ambos archivos reales y su guion exacto. No usar `verified:true` ni tiempos inventados para esta validación. Ejecutar sincronización local, revisar transcripción y medir inicio/fin de cada frase contra el audio.
4. MP4 real: pendiente. Se añadió y ejecutó un auditor offline sobre el vídeo sintético anterior y una copia recodificada; esto no sustituye una exportación con material real.
5. Clip vertical real: pendiente. El recorrido sintético entre editores aprobado en la fase anterior sigue siendo la referencia; no se repitió ni se presenta como prueba real.

## Auditor reproducible sin créditos

Requiere Node, FFmpeg y FFprobe instalados:

```sh
node tools/audit-mp4.cjs VIDEO.mp4 DURACION_ESPERADA horizontal
node tools/audit-mp4.cjs CLIP.mp4 DURACION_ESPERADA vertical
```

Comprueba contenedor MP4, una pista H.264, formato de píxel yuv420p, una pista AAC, duración esperada con tolerancia 0,15 s, orientación y `moov` antes de `mdat`. Decodifica íntegramente ambas pistas con FFmpeg. Código 0: pasa; 1: no cumple el perfil; 2: error de archivo/herramienta. Las comprobaciones opcionales no suministradas figuran como `null`. No mide inteligibilidad, sincronía labial/narrativa, sonoridad ni calidad visual. No es una prueba de aceptación del servidor de YouTube.

Referencia oficial del perfil recomendado: https://support.google.com/youtube/answer/1722171?hl=es

Para normalizar una copia local (ejemplo, no integración automática en la web):

```sh
ffmpeg -i ORIGINAL.mp4 -vf scale=in_range=auto:out_range=tv -c:v libx264 -pix_fmt yuv420p -color_range tv -crf 18 -c:a aac -b:a 192k -ar 48000 -movflags +faststart NORMALIZADO.mp4
```

No sobrescribir el original. Tras recodificar, preparar de nuevo el JSON de entrega seleccionando el archivo final: cambian tamaño, hash y posiblemente duración. Revisar tolerancia antes de entregar a ClipFarming.

Resultado observado: original sintético VP9/Opus no cumple este perfil H.264/AAC; no implica que YouTube rechace VP9/Opus. Copia normalizada: H.264/yuv420p, 1280×720, AAC estéreo 48 kHz, duración 6,488148 s frente a 6,4 s esperados, faststart y decodificación completa correctos. Prueba negativa con 20 s esperados rechazada. No se publicó ninguno. La cadencia variable del original se conserva y requiere revisión en la exportación real.

## Para ejecución completamente desatendida

- Obtener y validar una salida real de Viral DNA con identificador estable de encargo y escena, especialmente al reintentar; un número de descarga cronológico no basta.
- Puente de archivos entre el equipo que ejecuta Flow y el proceso de montaje, con confirmación de escritura completa, manifiesto de hashes, detección de duplicados y recuperación tras interrupciones.
- Adquirir la narración y el guion exacto; alinear palabras y escenas con reconocimiento local, con controles de confianza que detengan el trabajo ante desviaciones. Validar realmente español e inglés.
- Ejecutor persistente con cola para cuatro canales, estados de cada trabajo, reintentos idempotentes, límites de gasto aprobados y registro de errores; actualmente los selectores requieren intervención.
- Render estable con audio, conversión local automática al perfil final cuando sea necesaria y auditoría antes/después de los cortes. La exportación sin audio sigue teniendo una limitación documentada.
- Transferir a ClipFarming el archivo final y el JSON coherente, evaluar encuadre y subtítulos y exportar verticales. Decidir cómo aprobar fallos visuales/narrativos.
- La publicación y programación requieren otra fase expresamente autorizada; no forman parte de esta prueba.
