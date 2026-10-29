(function (root) {
  "use strict";
  const FORMAT = "video-factory-job/v1";
  function text(value, label, max) {
    if (typeof value !== "string" || !value.trim() || value.length > max) {
      throw new Error(label + " debe contener texto (máximo " + max + " caracteres).");
    }
    return value.trim();
  }
  function validateJob(data) {
    if (!data || typeof data !== "object" || Array.isArray(data) || data.format !== FORMAT) {
      throw new Error("Formato no compatible. Se espera video-factory-job/v1.");
    }
    const id = text(data.id, "id", 80);
    if (!/^[a-zA-Z0-9][a-zA-Z0-9_-]{2,79}$/.test(id)) {
      throw new Error("id no válido.");
    }
    const title = text(data.title, "title", 180);
    if (!["es", "en"].includes(data.language)) throw new Error("Idioma no válido (es/en).");
    if (!["life-ranges", "finance"].includes(data.niche)) throw new Error("Nicho no válido.");
    if (!["16:9", "9:16"].includes(data.aspectRatio)) throw new Error("Formato de pantalla no válido.");
    if (!Array.isArray(data.scenes) || data.scenes.length < 1 || data.scenes.length > 300) {
      throw new Error("Incluye entre 1 y 300 escenas.");
    }
    const scenes = data.scenes.map(function (scene, i) {
      if (!scene || typeof scene !== "object") throw new Error("Escena " + (i + 1) + " no válida.");
      return {
        narration: text(scene.narration, "Narración escena " + (i + 1), 4000),
        imagePrompt: text(scene.imagePrompt, "Prompt escena " + (i + 1), 3000).replace(/\s+/g, " ").replace(/^\d+[.)]\s*/, "")
      };
    });
    return {format: FORMAT, id: id, title: title, language: data.language,
      niche: data.niche, aspectRatio: data.aspectRatio, scenes: scenes};
  }
  function promptList(job) {
    return job.scenes.map(function (scene, i) {return (i + 1) + ". " + scene.imagePrompt;}).join("\n\n");
  }
  function applyJob(input) {
    const job = validateJob(input);
    if (!root.Studio || !root.Studio.setFormat || !root.Studio.saveDraftSoon) {
      throw new Error("Abre primero AutoVideo Studio.");
    }
    const el = function (id) {
      const node = root.document.getElementById(id);
      if (!node) throw new Error("Falta el campo " + id + " en esta versión.");
      return node;
    };
    const existing = root.Studio._test && root.Studio._test.snapshot ? root.Studio._test.snapshot() : null;
    if (existing && (existing.images.length || existing.scenes.length || existing.verified)) {
      throw new Error("Ya hay medios o escenas cargados. Guarda el proyecto y abre AutoVideo Studio en una pestaña nueva antes de importar otro encargo.");
    }
    if (el("scriptArea").value.trim() && !root.confirm("¿Sustituir el guion y los prompts actuales? Guarda antes el proyecto.")) {
      return false;
    }
    el("projectName").value = job.title;
    el("scriptArea").value = job.scenes.map(function (s) {return s.narration;}).join("\n\n");
    el("aiTopicInput").value = el("scriptArea").value;
    el("promptGenMode").value = "manual19";
    el("aiManualPrompts19").value = promptList(job);
    el("promptsArea").value = promptList(job);
    el("promptGenMode").dispatchEvent(new Event("change", {bubbles: true}));
    root.Studio.setFormat(job.aspectRatio);
    el("scriptArea").dispatchEvent(new Event("input", {bubbles: true}));
    root.Studio.saveDraftSoon();
    if (typeof root.switchTab === "function") root.switchTab(2);
    return true;
  }
  function boot() {
    const header = root.document.querySelector(".header-actions");
    if (!header || root.document.getElementById("factoryJobImportBtn")) return;
    const button = root.document.createElement("button");
    button.id = "factoryJobImportBtn";
    button.type = "button";
    button.className = "btn secondary-head";
    button.textContent = "Importar encargo";
    button.title = "Importa un guion y sus prompts desde video-factory-job/v1";
    const picker = root.document.createElement("input");
    picker.id = "factoryJobPicker";
    picker.type = "file";
    picker.accept = ".json,application/json";
    picker.hidden = true;
    button.addEventListener("click", function () {picker.click();});
    picker.addEventListener("change", async function () {
      const file = picker.files && picker.files[0];
      picker.value = "";
      if (!file) return;
      try {
        if (file.size > 2 * 1024 * 1024) throw new Error("El encargo no puede superar 2 MB.");
        const imported = applyJob(JSON.parse(await file.text()));
        if (imported) root.alert("Encargo importado. Comprueba el guion, después carga la voz y las imágenes generadas en Flow.");
      } catch (error) {
        root.alert("No se pudo importar el encargo: " + error.message);
      }
    });
    header.insertBefore(button, header.querySelector("#saveProjectBtn"));
    root.document.body.appendChild(picker);
  }
  const api = {validateJob: validateJob, promptList: promptList, applyJob: applyJob};
  root.VideoFactoryImport = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root.document) {
    if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", boot);
    else boot();
  }
})(typeof window !== "undefined" ? window : globalThis);
