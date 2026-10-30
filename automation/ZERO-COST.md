# Política de coste cero y conexiones pendientes

Objetivo: **ningún pago por servicios, generación, almacenamiento o automatización**. El ejecutor solo procesa archivos locales. No hay clientes HTTP de generación ni subida, claves de pago, conexión de tarjetas o forma de habilitar facturación desde él. Consume recursos del equipo existente; no se promete electricidad o hardware sin coste físico.

La política fija presupuesto económico 0, cuota nueva de generación 0 y subida/publicación desactivadas. Cambiar un JSON de entrada no habilita servicios pagados. La generación única anterior Mako ya se utilizó y no se repitió en esta fase.

| Componente | Qué está comprobado | Límite para garantizar 0 € |
|---|---|---|
| Python, Node, FFmpeg y SQLite locales | Montaje, cola, Shorts y carpeta completa con archivos existentes/sintéticos | Requieren equipo, herramientas instaladas y disco suficiente; probar rendimiento en Windows |
| ChatGPT y tarea semanal | Tarea existente activa, domingos 10:00 Europe/Madrid, con instrucción de solo fuentes sin coste/créditos | No se ha probado una tarea equivalente en una cuenta sin suscripción ni ejecución continua sobre el PC; no se usa una API pagada |
| vidIQ | La consulta de canales respondió con `_credits.used=0` y lista vacía | Las herramientas de búsqueda/outliers/transcripción consultadas indican 5 créditos por llamada. No se ejecutaron. No se supone que los créditos sean gratuitos ni se necesita comprar un plan |
| Flow + Viral DNA | Tres imágenes existentes recuperadas y asociadas por hash/prompts | No está verificada capacidad gratuita de 160 imágenes por vídeo ni la automatización del panel de la extensión. La consulta pública de ayuda devolvió 429; no se reintentó para eludir el límite. Google One/Plus de pago no se contabiliza como opción gratis |
| AI Studio | Mako/Flash TTS 3.8 funcionó una vez por la interfaz sin clave seleccionada; se conservó WAV real | La tarifa oficial mostraba Free Tier para ese modelo. Eso no acredita cuota larga disponible ni API gratis equivalente a la interfaz. No se hicieron nuevas generaciones o previsualizaciones |
| Kokoro local | Model card oficial: pesos Apache-2.0, modelo de 82 M; voces inglesas y españolas documentadas | Candidato para evaluación local. No instalado, no generado ni comparado acústicamente con Mako en esta fase. La propia lista de voces advierte variación de calidad según idioma |
| Piper local | Proyecto de voz local y documentación de modelos disponibles | Alternativa a evaluar, con licencia de software y de cada voz por revisar. No se garantiza expresividad comparable a Mako |
| SDXL/FLUX y otros modelos de imagen locales | Candidatos para ejecución en el equipo, sin tarifa por llamada a un servicio | Falta comprobar licencia de los pesos elegidos, instalación compatible con AMD/Windows, calidad y coherencia del personaje. No se descargó ni generó un lote de 160 imágenes para afirmar equivalencia con Flow |
| YouTube oficial | Preparación local de archivos/metadatos con privacidad privada explícita | No hay canales OAuth vinculados a este ejecutor ni se subió nada. Antes de autorizar una subida, verificar cuotas y configuración de la cuenta/proyecto |

**No está demostrada todavía una fábrica integral desatendida de cuatro canales con calidad equivalente y coste 0 €.** El procesamiento local ya funciona sin tarifas de servicios. Investigación recurrente, generación de nuevas imágenes/voces de calidad y el puente al PC conservan límites que deben resolverse y probarse. Si no hay cuota gratuita autorizada, el encargo espera: no cambia de cuenta para saltar límites ni contrata otra opción.

## Condiciones y automatización de Google

Los términos de Gemini distinguen servicios no pagados y pagados, y contienen restricciones sobre uso, datos y clientes API. No se interpreta una página accesible como autorización para cualquier automatización ni se usan endpoints internos de Google. El acceso previo a Flow/AI Studio por navegador no constituye una API pública estable.

La automatización del envío a Viral DNA y la descarga por lote queda desactivada hasta disponer de una superficie admitida, condiciones compatibles y autorización concreta de cuota. `prompts-numbered.txt`, `bindings.json` y la bandeja de archivos están preparados para incorporarla sin cambiar el montaje. Las referencias visuales por canal son opcionales y pueden incorporarse después.

Fuentes primarias consultadas:

- https://ai.google.dev/gemini-api/docs/pricing
- https://ai.google.dev/gemini-api/terms
- https://huggingface.co/hexgrad/Kokoro-82M
- https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md
- https://github.com/OHF-Voice/piper1-gpl
- https://support.google.com/flow/

## Preparación de YouTube sin subir nada

`youtube-preparation.json` contiene el perfil del canal, MP4 y metadatos, con `privacyStatus: private`, sin fecha de publicación y con `uploadEnabled: false`. No se incluye un cliente que pueda enviar bytes. Se mantiene pendiente canal exacto, autorización OAuth oficial y decisiones sobre audiencia/contenido sintético.

La documentación de `videos.insert` consultada indica **100 llamadas de subida al día** en el cupo correspondiente y una unidad de ese cupo por llamada. Son unidades de cuota, no se han tratado como euros ni como autorización de generación. No se hizo una solicitud de subida para comprobarlo en la cuenta del usuario.

Debe usarse OAuth para la cuenta/canal correcto, con el ámbito mínimo de subida y tokens guardados solo en el PC. Los cuatro perfiles lógicos no equivalen a cuatro canales de YouTube autorizados. La consulta de vidIQ no devolvió canales asociados; no se adivinaron IDs ni se conectó otra cuenta automáticamente.

Es esencial fijar **privado explícitamente**: la documentación advierte que omitir el campo puede dejar privacidad pública. El código comprueba esa preparación, pero no afirma haber creado borradores o vídeos privados reales. La siguiente fase de subida requiere autorización del usuario sobre canal, archivo y metadatos.

- https://developers.google.com/youtube/v3/docs/videos/insert
- https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits
- https://developers.google.com/youtube/v3/guides/auth/installed-apps
