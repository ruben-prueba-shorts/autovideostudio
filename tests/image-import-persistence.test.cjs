// Ejecutar: node tests/image-import-persistence.test.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const begin = source.indexOf('let activeImageImports = 0;');
const end = source.indexOf('function clearAllImages()', begin);
assert.ok(begin >= 0 && end > begin, 'No se encuentra el importador de imágenes');
const importer = source.slice(begin, end);
assert.match(source, /async function saveDraft\(\)\{if\(isExportingVideo\|\|activeImageImports\)return;/);
assert.match(source, /async function saveProject\(\)\{if\(activeImageImports\)throw new Error/);
class FakeReader {
  readAsDataURL(file) {
    this.result = file.data;
    queueMicrotask(() => this.onload());
  }
}
function harness() {
  let draftCalls = 0;
  const alerts = [];
  const app = {readImageHint: async () => '', Studio: {saveDraftSoon: () => draftCalls++}};
  const create = new Function('FileReader', 'window', 'loadImageCrossOrigin', 'renderMediaGrid',
    'renderSceneListUI', 'renderCurrentFrame', 'alert',
    'let loadedImages=[], scenes=[];\n' + importer +
    '\nreturn {run: handleImagesUpload, images: () => loadedImages, pending: () => activeImageImports};');
  const api = create(FakeReader, app,
    async url => {
      if (url.includes('invalid')) throw Error('Archivo dañado');
      return {dataUrl: url, imgObj: {naturalWidth: 100}};
    },
    () => {}, () => {}, () => {}, message => alerts.push(message));
  return {...api, draftCalls: () => draftCalls, alerts};
}
(async () => {
  const h = harness();
  await h.run([
    {name: 'scene_10.png', data: 'data:image/png;base64,QUJD'},
    {name: 'scene_2.png', data: 'data:image/png;base64,REVG'}
  ]);
  assert.deepEqual(h.images().map(x => x.name), ['scene_2.png', 'scene_10.png']);
  assert.ok(h.images().every(x => x.url.startsWith('data:image/') && !x.isPending));
  assert.equal(h.pending(), 0);
  assert.equal(h.draftCalls(), 1);

  await h.run([
    {name: 'broken.png', data: 'data:image/png;base64,invalid'},
    {name: 'scene_11.png', data: 'data:image/png;base64,R0hJ'}
  ]);
  assert.equal(h.images().length, 3, 'El archivo roto no se conserva');
  assert.equal(h.pending(), 0);
  assert.equal(h.alerts.length, 1);
  assert.equal(h.draftCalls(), 2);
  process.stdout.write('OK: imágenes persistentes, orden estable y errores recuperables.\n');
})().catch(err => {console.error(err); process.exitCode = 1;});
