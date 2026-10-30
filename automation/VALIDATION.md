# Validación de la fase — 30 de octubre de 2026

Base de AutoVideo: PR #1, commit `201b8816e728ffdb9a24f0bd6d0a3b3fa79e9404`.
Base de ClipFarming: `cb33863f9bb2bfa2ae7cfa629428864ed81fae3c`.

## Ejecutado y aprobado

- 5 pruebas de contrato de AutoVideo y 2 de ClipFarming (`node --test`). Incluyen los cuatro pares nicho/idioma, encargos inválidos, normalización de saltos de línea, orden numérico, imágenes ausentes/duplicadas/fuera de rango y validación de tiempos e identidad del vídeo.
- Prueba real con Playwright 1.62.1 y Chromium 153 aislado, sirviendo únicamente los dos checkouts locales. Todas las solicitudes fuera del servidor local se bloquearon; no hubo solicitudes a los proveedores de generación/transcripción ni errores JavaScript de página.
- Importación de los cuatro perfiles mediante el selector de archivos de la interfaz del PR #1. Comprobación de audio externo y sincronización local como valores iniciales.
- Descarga real del TXT de Flow y comparación de cada línea con el prompt de su escena.
- Lote de 12 PNG seleccionado fuera de orden (incluyendo 1, 2, 10, 11 y 12). Verificación de nombres, prompts, narraciones y orden de imágenes. Un lote incompleto deja el proyecto intacto.
- Guardado real de un `.avfproject`, cierre de Chromium, lanzamiento de otro navegador con almacenamiento vacío y apertura del archivo guardado. Las 12 imágenes se decodifican y conservan sus datos; se compararon píxeles de las dos imágenes de referencia y los datos de todas ellas.
- Recuperación del borrador desde IndexedDB en otra pestaña.
- Importación desde un selector de carpeta y conservación de una escena con varias frases.
- Importación general sin encargo, guardado y reapertura. Un lote con un PNG corrupto no incorpora parcialmente sus imágenes.
- Comprobación de que el ajuste por similitud no cambia la asociación numerada del encargo.
- Renderización real de un MP4 de unos 6,4 s a 1280 × 720 con imágenes de prueba y un tono sintético de 24 kHz. El proyecto de prueba tiene tiempos conocidos; se marca como proyecto ya sincronizado para probar el render y la transferencia sin usar reconocimiento de voz.
- Generación del JSON de entrega. ClipFarming rechaza una huella incorrecta, importa el mismo MP4 y sus cuatro bloques de subtítulos, mantiene el identificador del encargo y selecciona modo local.
- Exportación real de un clip vertical de unos 6,4 s a 720 × 1280 en ClipFarming. FFprobe confirmó pistas de vídeo VP9 y audio Opus en los MP4 producidos por este Chromium. FFmpeg confirmó la imagen roja en el segundo 1 y la azul en el segundo 5, tanto en el original como en el clip.
- Comprobación de sintaxis JavaScript y `git diff --check`.

## Límites observados y pendientes

- Los PNG, el audio y los vídeos usados son sintéticos. No se generaron imágenes en Flow ni voces en AI Studio, no se llamó a Gemini y no se publicó contenido.
- No se certificó la alineación acústica de una narración real ni el reconocimiento local de Whisper. Tampoco se probó el exportador acelerado WebCodecs/FFmpeg WASM: la prueba usa los motores compatibles MediaRecorder de ambas aplicaciones.
- Este Chromium produjo VP9/Opus dentro de MP4; no se certificó H.264/AAC ni se comprobó una subida a YouTube.
- Una prueba preliminar sin ninguna pista de voz produjo un vídeo demasiado corto en este navegador. La comprobación de duración de la entrega lo rechazó correctamente. El recorrido aprobado usa una pista de audio. La exportación de proyectos sin audio queda como limitación del motor existente a revisar por separado.
- Falta una prueba con un lote real descargado de Viral DNA, especialmente su numeración tras reintentos. El importador valida números y cantidad; no interpreta el contenido visual para deducir a qué prompt pertenecía una imagen renumerada.
- No se hicieron pruebas de carga con cientos de imágenes de alta resolución, vídeos grandes, GIF animados, ni variantes JPEG/WebP reales de Flow.
- La selección de carpeta y la entrega del MP4/JSON siguen requiriendo intervención del usuario. No se ha creado un vigilante de carpetas, una cola de ejecución de los cuatro canales ni un publicador de YouTube.
- Las imágenes de proyectos antiguos que solo guardaron direcciones `blob:` caducadas no se pueden reconstruir sin sus archivos originales.

No se modificaron las ramas `main` ni se ejecutaron despliegues. Los cambios se entregan mediante PR en borrador.
