const $ = (id) => document.getElementById(id);
const state = { samples: [], active: null, experiments: null, selected: 0, stage: 'detections', drawing: false,
  busy: false, apiKey: '', model: 'gpt-4.1', serverKey: false, discovery: null, examples: [], exampleStrategies: null };
let renderVersion = 0, drag = null, toastTimer;
const escape = (value) => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const percent = (v) => v == null ? '—' : `${Math.round(v * 100)}%`;
const activeSample = () => state.samples.find(s => s.id === state.active);
const selectedStrategy = () => state.experiments?.strategies[state.selected];

function notify(message, error = false) {
  $('notification').textContent = message;
  $('notification').className = `notification${error ? ' error' : ''}`;
  $('notification').hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => $('notification').hidden = true, error ? 12000 : 5500);
}
function measurements() {
  return { fields: [...document.querySelectorAll('input[name="measure"]:checked')].map(i => i.value),
    pixels_per_unit: Number($('scale').value || 0), unit: $('unit').value };
}
function brief() {
  return { samples: state.samples, description: $('description').value.trim(), context: $('context').value.trim(),
    answers: (state.discovery ? `Earlier analysis: ${JSON.stringify(state.discovery)}\nUser answers: ` : '') + $('answers').value.trim(),
    measurements: measurements(), model: state.model };
}
async function api(path, payload, binary = false) {
  const result = await fetch(`/api/${path}`, { method: 'POST', headers: {'Content-Type': 'application/json', ...(state.apiKey ? {'X-OpenAI-Key': state.apiKey} : {})}, body: JSON.stringify(payload) });
  if (!result.ok) {
    let message = `Request failed (${result.status}).`;
    try { const data = await result.json(); message = typeof data.detail === 'string' ? data.detail : data.detail?.map(d => `${d.loc.slice(1).join('.')}: ${d.msg}`).join('; ') || message; } catch {}
    throw new Error(message);
  }
  return binary ? result.blob() : result.json();
}
function updateButtons() {
  const hasImages = state.samples.length > 0;
  const busy = state.busy;
  $('export-button').disabled = busy || !selectedStrategy();
  $('analyze-button').disabled = busy || !hasImages;
  $('plan-button').disabled = busy || !hasImages || !state.discovery;
  $('review-button').disabled = busy || !selectedStrategy();
  $('baseline-button').disabled = busy || !hasImages;
  $('label-button').disabled = busy || !hasImages;
  $('clear-boxes').disabled = busy || !hasImages;
  document.querySelectorAll('.left-panel input,.left-panel textarea,.left-panel select,#answers,#split,#labeled,#remove-image,#upload-button,#example-select,#rerun-button,#parameters-json,.sample-card,.strategy-card').forEach(el => el.disabled = busy);
}
async function task(label, action) {
  if (state.busy) return;
  state.busy = true; document.body.classList.add('busy'); $('project-status').textContent = label; $('footer-status').textContent = label; updateButtons();
  try { await action(); }
  catch (error) { notify(error.message, true); }
  finally { state.busy = false; document.body.classList.remove('busy'); $('project-status').textContent = selectedStrategy() ? 'Experiment ready' : state.samples.length ? 'Examples ready' : 'New experiment'; $('footer-status').textContent = 'Detectors run locally. AI actions use your OpenAI account.'; updateButtons(); }
}
function invalidate(reason = '') {
  state.experiments = null; state.selected = 0;
  renderResults(); updateButtons(); renderViewer();
  if (reason) $('results-help').textContent = reason;
}
function addMessage(label, text, list = [], extra = '') {
  const div = document.createElement('div'); div.className = `assistant-message${label === 'YOU' ? ' user' : ''}`;
  div.innerHTML = `<span class="message-label">${escape(label)}</span><p>${escape(text).replace(/\n/g, '<br>')}</p>${list.length ? `<ul>${list.map(x => `<li>${escape(x)}</li>`).join('')}</ul>` : ''}${extra ? `<div class="callout">${escape(extra)}</div>` : ''}`;
  $('conversation').append(div); $('conversation').scrollTop = $('conversation').scrollHeight;
}
function checkAi() {
  if (!state.samples.some(s => s.split === 'train')) throw new Error('Add at least one training image.');
  if ($('description').value.trim().length < 3) throw new Error('Describe the object you want to detect.');
  if (!state.apiKey && !state.serverKey) { $('settings-dialog').showModal(); throw new Error('Add your OpenAI API key in Settings to analyze images.'); }
}
function setStep(index) { document.querySelectorAll('.steps>span').forEach((el, i) => el.classList.toggle('current', i === index)); }

async function readFile(file) {
  if (!['image/png','image/jpeg','image/webp'].includes(file.type)) throw new Error(`${file.name}: use PNG, JPG, or WebP.`);
  if (file.size > 8_000_000) throw new Error(`${file.name}: image exceeds 8 MB.`);
  const data = await new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = () => reject(new Error('Cannot read image')); reader.readAsDataURL(file); });
  const im = await loadImage(data);
  if (im.naturalWidth * im.naturalHeight > 24_000_000) throw new Error(`${file.name}: image exceeds 24 megapixels.`);
  return { id: crypto.randomUUID(), name: file.name.slice(0,200), data, split: 'train', labeled: false, boxes: [] };
}
async function addFiles(files) {
  if (state.busy) return;
  await task('Importing images…', async () => {
    const available = 12 - state.samples.length;
    if (files.length > available) notify(`Only the first ${available} images will be added. The limit is 12.`);
    for (const file of [...files].slice(0, available)) {
      try { const sample = await readFile(file); state.samples.push(sample); state.active = sample.id; } catch (error) { notify(error.message, true); }
    }
    state.exampleStrategies = null; state.discovery = null; invalidate(); renderSamples(); setStep(0);
  });
}
function renderSamples() {
  $('image-count').textContent = `${state.samples.length} / 12`;
  $('sample-list').innerHTML = state.samples.map(s => `<button class="sample-card ${state.active === s.id ? 'active' : ''}" data-id="${escape(s.id)}"><img src="${s.data}" alt=""><div><strong>${escape(s.name)}</strong><small>${s.split === 'train' ? 'Training' : 'Validation'} · ${s.labeled ? `${s.boxes.length} target${s.boxes.length === 1 ? '' : 's'}` : 'Unlabeled'}</small></div><span class="sample-tag">${s.labeled ? '✓' : '○'}</span></button>`).join('');
  document.querySelectorAll('.sample-card').forEach(button => button.onclick = () => { if (state.busy) return; state.active = button.dataset.id; renderSamples(); renderViewer(); renderDetail(); });
  updateButtons(); renderViewer();
}
function loadImage(src) { return new Promise((resolve, reject) => { const image = new Image(); image.onload = () => resolve(image); image.onerror = () => reject(new Error('This image could not be displayed.')); image.src = src; }); }
async function renderViewer() {
  const version = ++renderVersion;
  const sample = activeSample();
  $('empty-view').hidden = !!sample; $('image-view').hidden = !sample; $('image-controls').hidden = !sample;
  if (!sample) { $('viewer-title').textContent = 'Image workspace'; $('viewer-meta').textContent = 'Select an image to inspect or label'; $('image-size').textContent = ''; return; }
  $('viewer-title').textContent = sample.name;
  $('split').value = sample.split; $('labeled').checked = sample.labeled;
  $('box-count').textContent = `(${sample.boxes.length})`;
  $('label-button').classList.toggle('active', state.drawing);
  $('label-button').textContent = state.drawing ? 'Done labeling' : 'Draw target boxes';
  const result = selectedStrategy()?.results.find(r => r.sample_id === sample.id);
  const source = !state.drawing && result ? result.stages[state.stage] : sample.data;
  const image = await loadImage(source);
  if (version !== renderVersion) return;
  const canvas = $('image-canvas'); canvas.width = image.naturalWidth; canvas.height = image.naturalHeight;
  const ctx = canvas.getContext('2d'); ctx.drawImage(image, 0, 0);
  if (state.drawing || !result || state.stage === 'input') drawBoxes(ctx, sample.boxes);
  canvas.style.cursor = state.drawing ? 'crosshair' : 'default';
  $('viewer-meta').textContent = state.drawing ? 'Drag a box around each target object' : result ? `${selectedStrategy().strategy.name} · ${state.stage}` : 'Original image';
  $('image-size').textContent = `${image.naturalWidth} × ${image.naturalHeight}${result && !state.drawing ? ' preview' : ' px'}`;
  $('viewer-hint').textContent = state.drawing ? 'Label every target, then check “All targets labeled”. Boxes use the original image coordinates.' : 'Empty labeled images test false positives. Held-out images are excluded from AI planning and tuning.';
}
function drawBoxes(ctx, boxes) {
  const w = ctx.canvas.width, h = ctx.canvas.height;
  ctx.lineWidth = Math.max(2, w / 300); ctx.strokeStyle = '#ad942e'; ctx.fillStyle = '#f0d35b20';
  boxes.forEach(b => { ctx.fillRect(b.x*w,b.y*h,b.width*w,b.height*h); ctx.strokeRect(b.x*w,b.y*h,b.width*w,b.height*h); });
}
function point(event) {
  const r = $('image-canvas').getBoundingClientRect();
  return {x: Math.max(0, Math.min(1, (event.clientX-r.left)/r.width)), y: Math.max(0, Math.min(1, (event.clientY-r.top)/r.height))};
}
$('image-canvas').addEventListener('pointerdown', event => {
  if (!state.drawing || state.busy || !activeSample()) return;
  drag = {start: point(event), image: $('image-canvas').getContext('2d').getImageData(0, 0, $('image-canvas').width, $('image-canvas').height)};
  $('image-canvas').setPointerCapture(event.pointerId);
});
function draggedBox(p) { return {x: Math.min(drag.start.x, p.x), y: Math.min(drag.start.y,p.y), width: Math.abs(drag.start.x-p.x), height: Math.abs(drag.start.y-p.y)}; }
$('image-canvas').addEventListener('pointermove', event => {
  if (!drag) return; const ctx = $('image-canvas').getContext('2d'); ctx.putImageData(drag.image, 0, 0); drawBoxes(ctx, [draggedBox(point(event))]);
});
$('image-canvas').addEventListener('pointerup', event => {
  if (!drag) return;
  const box = draggedBox(point(event)); drag = null;
  if (box.width > .005 && box.height > .005 && activeSample().boxes.length < 150) activeSample().boxes.push(box);
  invalidate('Labels changed. Rerun the experiments to update scores.'); renderSamples();
});
$('image-canvas').addEventListener('pointercancel', () => { drag = null; renderViewer(); });

function renderResults() {
  const list = state.experiments?.strategies || [];
  $('results-empty').hidden = !!list.length; $('result-detail').hidden = !list.length; $('stage-tabs').hidden = !list.length;
  $('strategy-list').innerHTML = list.map((c,i) => `<button class="strategy-card ${i===state.selected?'active':''}" data-index="${i}"><span class="rank">0${i+1}</span><strong>${escape(c.strategy.name)}</strong><p>${c.latency_ms} ms / image · ${c.variants_tested} variant${c.variants_tested===1?'':'s'}<br>Train F1 ${percent(c.train?.f1)} · Validation F1 ${percent(c.validation?.f1)}</p></button>`).join('');
  document.querySelectorAll('.strategy-card').forEach(el => el.onclick = () => { if (state.busy) return; state.selected = Number(el.dataset.index); renderResults(); renderViewer(); });
  if (list.length) $('results-help').textContent = `Ordered by ${state.experiments.ranked_by}. Timing includes transforms and measurements; excludes file reading and preview encoding.`;
  renderDetail();
}
function renderDetail() {
  const candidate = selectedStrategy(); if (!candidate) return;
  const result = candidate.results.find(r => r.sample_id === state.active);
  const val = candidate.validation;
  $('metrics').innerHTML = [
    [result?.count ?? '—','Objects in this image'],[`${candidate.latency_ms} ms`,'Median CPU time'],
    [percent(val?.precision),'Validation precision'],[percent(val?.recall),'Validation recall']
  ].map(([value,label])=>`<div class="metric ${value==='—'?'warn':''}"><strong>${value}</strong><span>${label}</span></div>`).join('');
  $('strategy-rationale').textContent = candidate.strategy.rationale + (val ? ` Held-out labels: ${val.tp} matched, ${val.fp} extra, ${val.fn} missed across ${val.images} image(s).` : ' No labeled held-out images yet. Reliability is unmeasured.') + (result?.separation != null ? ` Mask separation proxy: ${result.separation} (inside target boxes minus background; not accuracy).` : '');
  $('parameters-json').value = JSON.stringify(candidate.strategy, null, 2);
  if (!result?.detections.length) { $('measurements-table').innerHTML = '<p class="help">No objects detected in this image.</p>'; return; }
  const fields = Object.keys(result.detections[0].measurements);
  const labels = {length:`Length (${result.unit})`,width:`Width (${result.unit})`,area:`Area (${result.unit}²)`,angle_deg:'Angle (°)',center_px:'Center (px)',mean_rgb:'RGB',color_hex:'Color'};
  $('measurements-table').innerHTML = `<table><thead><tr><th>Object</th>${fields.map(f=>`<th>${escape(labels[f]||f)}</th>`).join('')}</tr></thead><tbody>${result.detections.map((d,i)=>`<tr><td>${i+1}</td>${fields.map(f=>`<td>${d.measurements[f] == null ? '—' : Array.isArray(d.measurements[f]) ? d.measurements[f].join(', ') : escape(d.measurements[f])}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}
async function runStrategies(strategies, tune=true) {
  if (!state.samples.length) throw new Error('Add images first.');
  const result = await api('experiment', {samples:state.samples, strategies, measurements:measurements(), tune});
  state.experiments = result; state.selected = 0; state.drawing = false; state.stage = 'detections';
  document.querySelectorAll('[data-stage]').forEach(b=>b.classList.toggle('active',b.dataset.stage===state.stage));
  renderResults(); renderViewer(); setStep(2); updateButtons();
}

$('upload-button').onclick = () => $('files').click();
$('files').onchange = async event => { await addFiles(event.target.files); event.target.value = ''; };
for (const type of ['dragover','dragenter']) $('upload-button').addEventListener(type,e=>{e.preventDefault();$('upload-button').classList.add('dragging');});
for (const type of ['dragleave','drop']) $('upload-button').addEventListener(type,e=>{e.preventDefault();$('upload-button').classList.remove('dragging');if(type==='drop')addFiles(e.dataTransfer.files);});
$('label-button').onclick = () => { state.drawing = !state.drawing; renderViewer(); };
$('clear-boxes').onclick = () => { activeSample().boxes=[]; activeSample().labeled=false; invalidate(); renderSamples(); };
$('split').onchange = e => { activeSample().split=e.target.value; state.discovery=null; invalidate('Dataset split changed. Run the strategies again.'); renderSamples(); };
$('labeled').onchange = e => { activeSample().labeled=e.target.checked; invalidate('Labels changed. Run the strategies again.'); renderSamples(); };
$('remove-image').onclick = () => { state.samples=state.samples.filter(s=>s.id!==state.active);state.active=state.samples[0]?.id;state.discovery=null;invalidate();renderSamples(); };
for(const id of ['description','context']) $(id).oninput = () => { state.discovery=null;invalidate('Brief changed. Analyze again or test local baselines.'); };
for(const input of document.querySelectorAll('input[name="measure"],#scale,#unit')) input.addEventListener('change',()=>invalidate('Measurement options changed. Rerun to update the preview and export.'));
$('scale').addEventListener('input',()=>invalidate('Calibration changed. Rerun to update the preview and export.'));
document.querySelectorAll('[data-stage]').forEach(button=>button.onclick=()=>{state.stage=button.dataset.stage;state.drawing=false;document.querySelectorAll('[data-stage]').forEach(b=>b.classList.toggle('active',b===button));renderViewer();});

$('analyze-button').onclick=()=>task('Analyzing training images…',async()=>{
  checkAi(); addMessage('YOU',$('description').value);
  const result=await api('analyze',brief()); state.discovery=result;
  addMessage('IMAGE ANALYSIS',result.observations,result.important_features);
  addMessage('A FEW DETAILS', 'Help me narrow down the detector:', result.questions, result.limitations.join(' ')); setStep(1);
});
$('plan-button').onclick=()=>task('Designing and testing strategies…',async()=>{
  checkAi(); if($('answers').value.trim())addMessage('YOU',$('answers').value);
  const result=await api('plan',brief()); addMessage('DETECTOR PLAN',result.summary,result.strategies.map(s=>`${s.name}: ${s.rationale}`),result.limitations.join(' '));
  await runStrategies(result.strategies); addMessage('LOCAL RESULTS', 'Strategies were executed on your images. Select a strategy and click through the mask stages to inspect what it sees. I’m now comparing the actual transformed training images.', [], state.experiments.note);
  $('project-status').textContent='Reviewing transformed images…';
  try {
    const review=await api('review',{...brief(),strategies:state.experiments.strategies.map(c=>c.strategy)});
    addMessage('TRANSFORM REVIEW',review.assessment,review.next_steps,`AI recommendation: ${review.recommended_strategy}`);
  } catch(error) { addMessage('REVIEW UNAVAILABLE',error.message,[], 'Your local results and C++ export are still available. You can retry with “Review transform results”.'); }
});
$('review-button').onclick=()=>task('Reviewing the actual transforms…',async()=>{
  checkAi();const result=await api('review',{...brief(),strategies:state.experiments.strategies.map(c=>c.strategy)});
  addMessage('TRANSFORM REVIEW',result.assessment,result.next_steps,`AI recommendation: ${result.recommended_strategy}`);
});
$('baseline-button').onclick=()=>task('Running CPU experiments…',async()=>{
  const baselines=state.exampleStrategies || [
    {name:'Saturated color',method:'hsv',saturation_low:70,value_low:40,rationale:'Separate colored objects from neutral backgrounds; this is a general baseline, not an AI-selected target.'},
    {name:'Dark silhouettes',method:'otsu',invert:true,rationale:'Separate darker foreground shapes from a bright background.'},
    {name:'Bright silhouettes',method:'otsu',invert:false,rationale:'Separate light objects from a darker background.'},
    {name:'Closed edges',method:'canny',morph:5,rationale:'Find closed boundaries from brightness changes.'}
  ];await runStrategies(baselines);notify('Local strategies finished. No API key was used.');
});
$('rerun-button').onclick=()=>task('Testing adjusted parameters…',async()=>{let s;try{s=JSON.parse($('parameters-json').value);}catch{throw new Error('Parameters must be valid JSON.');}await runStrategies([s],false);});
$('export-button').onclick=()=>task('Preparing C++ export…',async()=>{
  const blob=await api('export',{strategy:selectedStrategy().strategy,measurements:measurements(),description:$('description').value||'Object detector'},true);
  const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='cpu-detector.zip';a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);setStep(3);notify('Exported C++ source, CMake build file, configuration, and instructions.');
});
$('settings-button').onclick=()=>{ $('api-key').value=state.apiKey;$('model').value=state.model;$('settings-dialog').showModal(); };
$('close-settings').onclick=()=>$('settings-dialog').close();
$('settings-form').onsubmit=e=>{e.preventDefault();state.apiKey=$('api-key').value.trim();state.model=$('model').value.trim()||'gpt-4.1';$('api-key').value='';$('settings-dialog').close();notify('Settings applied for this page session.');};
$('forget-key').onclick=()=>{state.apiKey='';$('api-key').value='';notify('Key removed from page memory.');};
$('example-select').onchange=e=>task('Loading internet test image…',async()=>{
  const example=state.examples.find(x=>x.id===e.target.value);if(!example)return;
  $('example-select').value='';
  if(state.samples.length)throw new Error('Remove the current images before starting a different example, so labels for different targets are not mixed.');
  const response=await fetch(example.path);if(!response.ok)throw new Error('Example image unavailable.');
  const blob=await response.blob();const sample=await readFile(new File([blob],example.filename,{type:blob.type}));
  sample.boxes=example.boxes||[];sample.labeled=!!example.labeled;
  state.samples.push(sample);state.active=sample.id;state.discovery=null;state.exampleStrategies=example.strategies;
  $('description').value=example.description;$('context').value=example.context||'';
  $('example-source').innerHTML=`Source: <a href="${escape(example.source)}" target="_blank" rel="noreferrer">${escape(example.credit)}</a>`;
  invalidate();renderSamples();$('example-select').value='';
});

async function init(){
  try{const [health,examples]=await Promise.all([fetch('/api/health').then(r=>r.json()),fetch('/api/examples').then(r=>r.json())]);
    state.serverKey=health.server_key;state.examples=examples;
    $('server-key-status').textContent=health.server_key?'A server environment key is available. A key entered here overrides it.':'No server key set. Add your key to use AI, or test baselines locally.';
    for(const example of examples.filter(e=>!e.workbench_only)){const option=document.createElement('option');option.value=example.id;option.textContent=example.title;$('example-select').append(option);}
  }catch{notify('Cannot connect to the local server. Start the application and reload.',true);}updateButtons();
}init();
