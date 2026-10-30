# Encargos, imágenes de Flow y entrega a ClipFarming

Esta fase amplía el importador `video-factory-job/v1` del PR #1. No ejecuta Google Flow, Viral DNA, Gemini, publicación en YouTube ni despliegues.

## Recorrido

1. En un proyecto vacío, pulsa **Importar encargo** y elige el JSON (ejemplo: `example-job.json`). Admite `finance` / `life-ranges`, idioma `es` / `en` y formato `16:9` / `9:16`.
2. En **Imágenes**, pulsa **Prompts para Flow**. El TXT contiene exactamente un prompt por línea, en el orden del encargo. Cada narración del encargo se conserva como una escena, aunque contenga varias frases.
3. En Viral DNA, importa ese TXT y usa cantidad **x1**, nombre **Numerado**, inicio **1**, una carpeta nueva para ese encargo. La generación es una acción independiente del usuario.
4. Descarga el lote terminado. Pulsa **Carpeta de Flow** o **Importar imágenes Flow** en AutoVideo. También se aplica la comprobación al importador normal si hay un encargo activo.
5. Se ordenan los números, no el orden en el que seleccionaste los archivos. `0001.png` corresponde al primer prompt y narración. Se aceptan PNG, JPG, WebP y GIF; los GIF se usan como imagen fija.
6. Un lote con números duplicados, fuera del rango o escenas ausentes se rechaza completo. Las imágenes deben mantener el número de su prompt original, también tras reintentos en Viral DNA. No es posible deducir una renumeración incorrecta únicamente a partir del contenido visual.
7. Carga tu audio, sincroniza, revisa y guarda el `.avfproject`. Los encargos se configuran inicialmente con audio externo y sincronización local. El ajuste automático de imágenes por similitud se desactiva para conservar la relación numerada y evitar consultas de IA de texto.

La selección de archivos/carpeta requiere un gesto del usuario. Después la asociación es automática. Esta versión no vigila la carpeta Descargas ni controla la extensión.

## Persistencia

Las imágenes se leen y decodifican antes de incorporarlas al proyecto. Sus datos se incluyen en el archivo y en el borrador, en lugar de guardar direcciones `blob:` ligadas a una pestaña. Se conserva el archivo PNG/JPEG/WebP sin reducir resolución ni volver a comprimirlo. Un error de lectura no deja medio lote cargado.

El encargo, idioma, nicho, prompts y números de escena se conservan al guardar y abrir. Si el usuario cambia el guion o los prompts, el lote numerado exige un encargo actualizado. Al guardar un proyecto editado libremente se omite la asociación obsoleta al encargo.

Los proyectos antiguos que solo contienen referencias `blob:` ya caducadas no contienen los bytes de las imágenes: es necesario volver a importar los originales. Los proyectos anteriores con imágenes incrustadas siguen siendo compatibles.

Límites: 30 MiB por imagen, 300 MiB por lote, hasta 300 escenas por encargo; el importador general conserva su límite de 3000 imágenes. Las imágenes decodificadas y el JSON necesitan memoria, especialmente a gran resolución.

## Entrega a ClipFarming

1. Exporta el vídeo completo de AutoVideo. Para volver a encuadrar y añadir subtítulos verticales, exporta ese original con subtítulos desactivados.
2. Sin editar el proyecto entre medias, abre **Clips → Preparar para ClipFarming** y selecciona el vídeo completo recién exportado.
3. Se descarga `<vídeo>.clipfarming.json` con idioma, identificador del encargo, subtítulos con tiempos absolutos y cortes ya preparados que duren como máximo 150 segundos.
4. En la versión de ClipFarming con el importador correspondiente, pulsa **Importar de AutoVideo** y selecciona el vídeo y el JSON juntos.
5. ClipFarming comprueba nombre, tamaño, duración y SHA-256 antes de importarlos. Arranca en modo local, con el consentimiento para enviar a Google desmarcado. Puedes usar los cortes recibidos, crear cortes manuales o analizar pausas localmente.

La huella garantiza que ClipFarming recibe el mismo vídeo seleccionado al preparar la entrega. No demuestra por sí sola qué proyecto generó ese vídeo. La duración se comprueba con una tolerancia de 0,15 s al preparar la entrega y de 0,05 s al recibirla.

La entrega contiene `subtitlesBurned`: si el original ya tiene subtítulos, ClipFarming evita añadirlos dos veces. Los subtítulos incrustados no se pueden retirar del vídeo. El usuario debe revisar encuadre, principio y final de cada clip.

Esta fase admite vídeos de hasta 512 MiB para el cálculo de huella en el navegador. El JSON tiene un límite de 20 MiB en ClipFarming. Los archivos no se envían a ningún servidor mediante esta integración.

## Pruebas reproducibles

Requiere Node.js y Playwright 1.62.1. Instalar dependencias y Chromium en el equipo de pruebas:

```sh
npm install
npx playwright install chromium
npm test
CLIPFARMING_DIR=/ruta/al/checkout/clipfarming npm run test:browser
```

Sin `CLIPFARMING_DIR` se ejecutan las pruebas de AutoVideo y se informa explícitamente de que se omite la prueba entre repositorios. `CHROMIUM_EXECUTABLE` permite usar un Chromium ya instalado. `HANDOFF_ONLY=1` ejecuta solo el recorrido de entrega durante depuración.

El navegador de pruebas se crea aislado y bloquea todas las solicitudes fuera del servidor local. Las imágenes y el audio son sintéticos. El resultado queda en `.test-artifacts/`, ignorado por Git. La prueba de vídeo usa un proyecto con tiempos conocidos y un tono generado localmente; no certifica la sincronización de una voz real de AI Studio.

Consulta `VALIDATION.md` para los resultados observados de esta fase.
