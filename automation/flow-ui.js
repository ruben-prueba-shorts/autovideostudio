(function () {
  'use strict';
  function boot() {
    const imagesTab=document.getElementById('tab3');
    if (!imagesTab) return;
    const panel=document.createElement('div');panel.className='card';
    const heading=document.createElement('h2');heading.textContent='Imágenes de Flow';panel.appendChild(heading);
    const actions=document.createElement('div');actions.className='button-row';panel.appendChild(actions);imagesTab.prepend(panel);
    function button(id,label,action) {
      const b=document.createElement('button');b.id=id;b.type='button';b.className='btn secondary-head';b.textContent=label;
      b.addEventListener('click',action);actions.appendChild(b);return b;
    }
    function picker(id,accept,multiple,callback) {
      const p=document.createElement('input');p.id=id;p.type='file';p.accept=accept;p.multiple=multiple;p.hidden=true;
      p.addEventListener('change',async()=>{const files=Array.from(p.files);p.value='';if(files.length)await callback(files);});
      document.body.appendChild(p);return p;
    }
    function requireJob() {
      const job=window.VideoFactoryImport.matchingJob();
      if (!job) throw new Error('Importa un encargo. Si has editado sus escenas o prompts, importa el encargo actualizado en un proyecto vacío.');
      return job;
    }
    button('factoryFlowPromptsBtn','Prompts para Flow',()=>{
      try {
        const job=requireJob(), text=job.scenes.map(s=>s.imagePrompt).join('\n');
        const a=document.createElement('a'),url=URL.createObjectURL(new Blob([text],{type:'text/plain;charset=utf-8'}));
        a.href=url;a.download=job.id+'_flow.txt';a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);
      } catch(e) {alert(e.message);}
    });
    const images=picker('factoryImagesPicker','.png,.jpg,.jpeg,.webp,.gif,.json',true,files=>Studio.importImages(files,true));
    button('factoryImagesBtn','Importar imágenes Flow',()=>{try{requireJob();images.click();}catch(e){alert(e.message);}});
    const folder=picker('factoryFolderPicker','',true,files=>Studio.importImages(files,true));folder.setAttribute('webkitdirectory','');
    button('factoryFolderBtn','Carpeta de Flow',()=>{try{requireJob();folder.click();}catch(e){alert(e.message);}});
    const master=picker('factoryMasterPicker','.mp4,.webm,video/mp4,video/webm',false,files=>Studio.prepareClipHandoff(files[0]));
    const handoff=button('factoryHandoffBtn','Preparar para ClipFarming',()=>master.click());
    const delivery=document.createElement('div');delivery.className='card';delivery.appendChild(handoff);document.getElementById('tab5')?.appendChild(delivery);
    const note=document.createElement('p');note.className='style-hint';note.id='factoryFlowHelp';
    note.textContent='Flow: un prompt por línea, cantidad x1 y archivos numerados desde 1. Importa un único lote completo. Si incluyes bindings.json, se comprobarán las huellas de imágenes, prompts y narraciones. Para ClipFarming, selecciona el vídeo completo ya exportado.';
    panel.appendChild(note);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();
