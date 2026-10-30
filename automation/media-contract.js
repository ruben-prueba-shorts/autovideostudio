(function (root) {
  'use strict';
  const IMAGE = /\.(png|jpe?g|webp|gif)$/i;
  const FORMAT = 'autovideo-clipfarming/v1';
  function orderImages(files, count) {
    if (!Number.isInteger(count) || count < 1 || count > 300) throw new Error('Importa primero un encargo de 1–300 escenas.');
    const slots = new Map();
    for (const file of Array.from(files || [])) {
      if (!IMAGE.test(file.name)) continue;
      const match = /^(\d+)(?=[\s_.(-]|$)/.exec(file.name);
      if (!match) throw new Error('Nombre sin número inicial: ' + file.name + '. Usa Numerado en Viral DNA.');
      const n = Number(match[1]);
      if (!Number.isSafeInteger(n) || n < 1 || n > count) throw new Error('Imagen fuera del encargo: ' + file.name);
      if (slots.has(n)) throw new Error('Número de escena duplicado: ' + n + '. Conserva una imagen por escena.');
      slots.set(n, file);
    }
    const missing = Array.from({length: count}, (_, i) => i + 1).filter(n => !slots.has(n));
    if (missing.length) throw new Error('Faltan imágenes para las escenas: ' + missing.join(', '));
    return Array.from({length: count}, (_, i) => slots.get(i + 1));
  }
  function validateHandoff(value) {
    if (!value || value.format !== FORMAT) throw new Error('Entrega de ClipFarming no compatible.');
    const v = value.video;
    if (!v || typeof v.name !== 'string' || !v.name || v.name.length > 255 || !Number.isSafeInteger(v.size) || v.size <= 0 ||
        !Number.isFinite(v.duration) || v.duration <= 0 || !/^[a-f0-9]{64}$/.test(v.sha256)) throw new Error('Identidad de vídeo no válida.');
    function ranges(items, limit, label) {
      if (!Array.isArray(items) || items.length > limit) throw new Error(label + ' no válidos.');
      return items.map(item => {
        if (!item || !Number.isFinite(item.start) || !Number.isFinite(item.end) || item.start < 0 ||
            item.end <= item.start || item.end > v.duration + .001) throw new Error('Tiempos de ' + label + ' fuera del vídeo.');
        return item;
      });
    }
    const cues = ranges(value.cues, 100000, 'subtítulos').map(c => {
      if (typeof c.text !== 'string' || !c.text.trim() || c.text.length > 10000) throw new Error('Texto de subtítulo no válido.');
      return {start:c.start, end:c.end, text:c.text};
    }).sort((a,b) => a.start-b.start);
    const clips = ranges(value.clips, 250, 'clips').map(c => {
      if (c.end-c.start > 150 || typeof c.title !== 'string' || c.title.length > 140) throw new Error('Clip no válido (máximo 150 s).');
      return {start:c.start, end:c.end, title:c.title};
    });
    if (typeof value.subtitlesBurned !== 'boolean') throw new Error('Indica si el vídeo ya lleva subtítulos incrustados.');
    if (!['es','en'].includes(value.language)) throw new Error('Idioma no válido.');
    return {format:FORMAT, video:{name:v.name,size:v.size,duration:v.duration,sha256:v.sha256},
      subtitlesBurned:value.subtitlesBurned, language:value.language, jobId:typeof value.jobId === 'string' ? value.jobId.slice(0,80) : '', cues, clips};
  }
  async function digest(file) {
    // Cap allocation: this phase handles browser-side files up to 512 MiB.
    if (file.size > 512 * 1024 * 1024) throw new Error('La entrega admite vídeos de hasta 512 MB en esta versión.');
    const hash = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());
    return Array.from(new Uint8Array(hash), b => b.toString(16).padStart(2,'0')).join('');
  }
  const api = {FORMAT, IMAGE, orderImages, validateHandoff, digest};
  root.VideoFactoryMedia = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
