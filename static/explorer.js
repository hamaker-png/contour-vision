import {clone, uid, paths, editGraph, moveOperation, remapDraft, orderedTimelines, validSelection, savedSelection, formatMs as ms, Revision, supportingIds, dependencyIds} from './workflow.mjs';
import {estimate, inputKind, outputKind, aggregate as aggregateResults} from './evaluation.mjs';
import {createLabelEditor} from './label_editor.mjs';
import {AISession} from './ai_session.mjs';
import {previewMove,gapIndex,independentCopy,typeIssues} from './pipeline_edits.mjs';
import {updateAnswer,formatAnswers,checkedAnswers,familyFingerprint,readGuidance} from './clarifications.mjs';
import {ExposureLedger} from './ai_exposure.mjs';
import {reviewImage,matchedBoxes} from './validation_review.mjs';
import {ParameterDrafts} from './parameter_drafts.mjs';
import {createOptimizationUI} from './optimization_ui.mjs';

const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pretty = key => key.replaceAll('_', ' ').replace(/^./, c => c.toUpperCase());
function measurementText(key,value,unit){
  const label={mean_rgb:'Mean RGB',center_px:'Center',angle_deg:'Angle'}[key]||pretty(key);
  const suffix=key==='area'?` ${unit}²`:['length','width'].includes(key)?` ${unit}`:key==='center_px'?' px':key==='angle_deg'?'°':'';
  return `${label}: ${value===null?'undefined for this shape':(Array.isArray(value)?value.join(', '):value)+suffix}`;
}
const state = {samples:[], active:null, timelines:[], catalog:[], examples:[], results:new Map(), selected:null, undo:[], redo:[], draft:null,compareOpen:false,collectionOpen:false,screen:'images',serverKey:false,discovery:null,questionAnswers:[],example:false,uploadBusy:false};
const revision = new Revision();
const aiSession = new AISession();
const exposure = new ExposureLedger();
const parameterDrafts=new ParameterDrafts();
let optimizationUI;
function clearOptimization(message=''){optimizationUI?.clear(message);}
let pipelineView='focus';
const comparedPipelines=new Set(),pipelineScrolls=new Map(),pipelineSelections=new Map();
function clearParameterDrafts(){parameterDrafts.clear();for(const key of ['selectionKey','parameterKey','nameKey'])delete $('inspector').dataset[key];}
const expandedPrefixes=new Set();
function resetPipelineView(){
  pipelineView='focus';comparedPipelines.clear();pipelineSelections.clear();pipelineScrolls.clear();expandedPrefixes.clear();
  document.querySelector('.pipeline-layout').classList.remove('choosing-comparisons');$('choose-comparisons').setAttribute('aria-expanded','false');
  const selected=state.timelines.find(t=>t.id===state.selected?.timeline);
  if(selected?.parent_id&&!selected.operations.some(op=>op.id===state.selected.node))expandedPrefixes.add(selected.id);
}
let activeRun, autoTimer, addTimeline, drag, arrangeTimeline, loadEpoch = 0, projectRevision = 0, aiBusy = false;
const executionErrors=new Map();
const aggregate=(...args)=>aggregateResults(...args,executionErrors);
let fieldEdit;
let intake;
const hardwareFields={'hardware-mode':'mode','cpu-name':'cpu_name','architecture':'architecture','host-ghz':'host_ghz','target-ghz':'target_ghz','relative-speed':'relative_speed','reference-local':'reference_local_ms','reference-target':'reference_target_ms','budget':'budget_ms'};
const operation = kind => ({id:uid('op'), kind, params:clone(state.catalog.find(c => c.kind === kind).defaults)});
const currentResult = () => state.results.get(state.active);
const ownerOf = id => state.timelines.find(t => t.operations.some(o => o.id === id));
const selectedTimeline = () => state.timelines.find(t => t.id === state.selected?.timeline);
const selectedOperation = () => ownerOf(state.selected?.node)?.operations.find(o => o.id === state.selected.node);

function notify(message = '') { $('notice').textContent = message; $('notice').hidden = !message; }
function status(message) { $('status').textContent = message; }
function stopIntake(){
  loadEpoch++;intake?.controller.abort();intake=null;state.uploadBusy=false;$('upload').disabled=false;
}
function beginIntake(kind){
  stopIntake();intake={kind,epoch:loadEpoch,controller:new AbortController()};return intake;
}
async function api(path, body, signal) {
  const headers=body?{'Content-Type':'application/json'}:{};
  if(['/api/analyze','/api/timelines/suggest'].includes(path))headers['X-OpenAI-Key']=$('api-key').value.trim();
  const response = await fetch(path, {method:body ? 'POST' : 'GET', headers, body:body ? JSON.stringify(body) : undefined, signal});
  let data; try { data = await response.json(); } catch { throw Error('The server returned an unreadable response. Please try again.'); }
  if (!response.ok) throw Error(Array.isArray(data.detail) ? data.detail.map(e => `${e.loc.slice(1).join(' → ')}: ${e.msg}`).join('; ') : data.detail || 'Request failed.');
  return data;
}
const number = id => $(id).value.trim() === '' ? null : Number($(id).value);
function hardware() {
  return {mode:$('hardware-mode').value, cpu_name:$('cpu-name').value, architecture:$('architecture').value,
    host_ghz:number('host-ghz'), target_ghz:number('target-ghz'), relative_speed:number('relative-speed'),
    reference_local_ms:number('reference-local'), reference_target_ms:number('reference-target'), budget_ms:number('budget')};
}
function measurements() {
  return {fields:[...$('measurements').querySelectorAll('input:checked')].map(i => i.value), pixels_per_unit:number('scale') ?? 0, unit:$('unit').value};
}
function runBody(samples = state.samples) { return {samples, timelines:state.timelines, hardware:hardware(), measurements:measurements()}; }
function aiBody(suggest=false,validate=true) {
  if(validate&&!state.samples.some(s=>s.split==='train'))throw Error('Add at least one training image. Validation images stay out of AI.');
  if(validate&&suggest&&$('description').value.trim().length<3)throw Error('Name the object or feature in Your target before generating approaches.');
  const answers=(validate?checkedAnswers:formatAnswers)(state.questionAnswers,$('answers').value);
  return {samples:state.samples,description:$('description').value,context:$('context').value,answers,measurements:measurements(),model:$('model').value.trim(),...(suggest?{timelines:state.timelines,hardware:hardware()}:{})};
}
function hasKey(){return state.serverKey||Boolean($('api-key').value.trim());}
function imageRole(sample){
  if(sample.split==='train')return 'Training';
  return {unseen:'Held-out validation',submitted:'Reused validation · submitted for AI',tuned:'Reused validation · locally optimized',unknown:'Validation · usage history unknown'}[exposure.status(sample)];
}
function evaluationGroups(){
  return [{name:'Training',split:'train',samples:state.samples},
    {name:'Held-out validation',split:'validation',samples:state.samples.filter(s=>exposure.status(s)==='unseen')},
    ...['submitted','tuned','unknown'].filter(kind=>state.samples.some(s=>s.split==='validation'&&exposure.status(s)===kind)).map(kind=>({name:kind==='submitted'?'Reused validation · previously submitted for AI':kind==='tuned'?'Reused validation · locally optimized':'Validation · usage history unknown',split:'validation',samples:state.samples.filter(s=>exposure.status(s)===kind)}))];
}
function clearAI(clearDiscovery=false){
  clearOptimization();
  aiSession.cancel();aiBusy=false;state.draft=null;state.draftKey=null;$('suggestions').textContent='';
  if(clearDiscovery){state.discovery=null;renderDiscovery();}
  renderAIState();
}
function renderDiscovery(){
  const result=state.discovery,questions=result?.questions.slice(0,4)||[];
  $('analysis').innerHTML=result?`<p>${esc(result.observations)}</p><h3>Features to compare</h3><ul>${result.important_features.map(f=>`<li>${esc(f)}</li>`).join('')}</ul>${result.limitations.map(l=>`<p class="help">${esc(l)}</p>`).join('')}`:'';
  const field=(q,i)=>`<div class="question-field"><label for="question-${i}">${esc(q)}</label><input id="question-${i}" data-question="${esc(q)}" maxlength="1500" placeholder="Your answer" value="${esc(state.questionAnswers.find(a=>a.question===q)?.answer||'')}"></div>`;
  const earlier=state.questionAnswers.filter(a=>!questions.includes(a.question));
  $('question-fields').innerHTML=questions.map(field).join('')+(earlier.length?`<details class="earlier-answers"><summary>Earlier answers · ${earlier.length} retained</summary><p class="help">These constraints are included in the next AI request. You can edit or clear them.</p>${earlier.map((a,i)=>field(a.question,i+questions.length)).join('')}</details>`:'');
  renderAnswerBudget();
}
function renderAnswerBudget(){
  const size=formatAnswers(state.questionAnswers,$('answers').value).length;
  $('answer-budget').textContent=`Answers and requirements: ${size.toLocaleString()} / 6,000 characters`;
  $('answer-budget').classList.toggle('over-budget',size>6000);
}
function showTab(name) {
  if(name==='ai')return showScreen('define');
  if(name==='hardware')return $('hardware-dialog').showModal();
  showScreen('explore');panel('inspector',true);
}
function select(timeline, node = 'source') {
  pipelineSelections.set(timeline,node);
  if(pipelineView==='compare'&&!comparedPipelines.has(timeline)){if(comparedPipelines.size>=3)comparedPipelines.delete([...comparedPipelines].at(-1));comparedPipelines.add(timeline);}
  const t=state.timelines.find(t=>t.id===timeline);if(t?.parent_id&&(node==='source'||!t.operations.some(op=>op.id===node)))expandedPrefixes.add(timeline);
  state.selected = {timeline,node}; showTab('step'); renderTimelines(); renderInspector();
  revealSelectedStep(true);
}
function revealSelectedStep(animate=false){
  const selection=state.selected;if(!selection)return;
  requestAnimationFrame(()=>{
    if(state.screen!=='explore'||state.selected?.timeline!==selection.timeline||state.selected?.node!==selection.node)return;
    const node=document.querySelector(`.node[data-timeline="${CSS.escape(selection.timeline)}"][data-node="${CSS.escape(selection.node)}"]`),row=node?.closest('[data-node-row]');
    if(!row)return;
    const bounds=node.getBoundingClientRect(),viewport=row.getBoundingClientRect();
    if(bounds.left>=viewport.left+4&&bounds.right<=viewport.right-4)return;
    row.scrollTo({left:row.scrollLeft+bounds.left-viewport.left-(row.clientWidth-bounds.width)/2,behavior:animate&&!matchMedia('(prefers-reduced-motion:reduce)').matches?'smooth':'auto'});
    pipelineScrolls.set(selection.timeline,row.scrollLeft);
  });
}
function focusPipeline(timeline,node){
  const hasPosition=pipelineScrolls.has(timeline);
  const path=paths(state.timelines).get(timeline);if(!path)return;
  const remembered=node||pipelineSelections.get(timeline),chosen=path.some(op=>op.id===remembered)||remembered==='source'?remembered:path.at(-1)?.id||'source';
  state.selected={timeline,node:chosen};pipelineSelections.set(timeline,chosen);
  if(node&&!state.timelines.find(t=>t.id===timeline).operations.some(op=>op.id===node))expandedPrefixes.add(timeline);
  if(pipelineView==='compare'&&!comparedPipelines.has(timeline)){if(comparedPipelines.size>=3)comparedPipelines.delete([...comparedPipelines].at(-1));comparedPipelines.add(timeline);}
  showScreen('explore');renderTimelines();renderInspector();
  if(node||!hasPosition)revealSelectedStep();
}
function panel(name,open) {
  if(name==='images')return showScreen('images');
  document.body.classList.toggle(`show-${name}`,open);
  $(`toggle-${name}`).setAttribute('aria-expanded',String(open));
}
function showScreen(name){
  closeMobileMenus();
  if(name!=='images'&&!state.samples.length)return notify('Upload an image family first.');
  if(['explore','finish'].includes(name)&&!state.timelines.length)return notify('Generate approaches or start a manual pipeline first.');
  if(name==='finish'&&state.selected?.timeline)$('export-choice').value=state.selected.timeline;
  state.screen=name;document.body.classList.remove('stage-images','stage-define','stage-explore','stage-finish');document.body.classList.add(`stage-${name}`);
  for(const screen of ['images','define','explore','finish'])$(`screen-${screen}`).hidden=screen!==name;
  document.querySelectorAll('[data-screen]').forEach(b=>{if(b.dataset.screen===name)b.setAttribute('aria-current','step');else b.removeAttribute('aria-current');});
  if(name==='finish')renderFinish();
  window.scrollTo({top:0});
}
function renderAIState(){
  $('analyze').disabled=aiBusy||!state.samples.some(s=>s.split==='train');$('suggest').disabled=aiBusy||!state.discovery||$('description').value.trim().length<3||!state.samples.some(s=>s.split==='train');$('cancel-ai').hidden=!aiBusy;
  $('analyze').hidden=!hasKey();$('suggest').hidden=!hasKey()||!state.discovery;
  $('analyze').classList.toggle('primary',!state.discovery);$('analyze').textContent=aiBusy?'Inspecting…':state.discovery?'Inspect again':'Inspect image family →';$('suggest').textContent=aiBusy?'Working…':'Generate approaches →';
  const count=state.samples.filter(s=>s.split==='train').length;
  $('family-ai-state').innerHTML=aiBusy?'<p>Comparing the training images. You can cancel or keep editing.</p>':!hasKey()?(state.timelines.length?'<div class="key-required"><strong>Your pipelines are ready to use.</strong><p>Edit your target and measurements here, then use Compare &amp; edit to test them. AI inspection is optional.</p><button data-connect-key>Connect API key for AI suggestions</button></div>':'<div class="key-required"><strong>Start with a pipeline or connect AI.</strong><p>Describe your target and start a manual pipeline, or connect a key for image analysis and new suggestions.</p><button data-connect-key>Connect API key</button></div>'):state.discovery?`<p>AI inspected ${state.discovery.imageCount} training image${state.discovery.imageCount===1?'':'s'}. ${$('description').value.trim().length<3?'Name your target, then answer any relevant questions below.':'Answer the questions below, then generate approaches.'}</p>${$('description').value.trim().length<3?'<button data-set-target>Set your target</button>':''}`:`<p>${count} training image${count===1?'':'s'} ready. First, inspect the family to identify shared features and questions.</p>`;
}
function renderFlow(){
  $('continue-analysis').disabled=!state.samples.length;$('open-ai').disabled=!state.samples.length;$('open-explore').disabled=!state.timelines.length;$('open-finish').disabled=!state.timelines.length;
  const validation=state.samples.filter(s=>s.split==='validation'),reused=validation.filter(s=>exposure.status(s)!=='unseen').length;
  $('family-context').textContent=`${state.samples.filter(s=>s.split==='train').length} training images · ${validation.length} validation images${reused?` · ${reused} cannot be counted as held-out`:''}`;
  $('family-preview').innerHTML=state.samples.map(s=>`<button data-family-image="${esc(s.id)}" class="${s.split==='validation'?'heldout':''}" title="${esc(s.name)} · ${esc(imageRole(s))}"><img src="${esc(s.data)}" alt="${esc(s.name)}"><span>${esc(s.name)}</span></button>`).join('');
  for(const id of ['preview-image','validation-image'])$(id).innerHTML=state.samples.map(s=>`<option value="${esc(s.id)}" ${s.id===state.active?'selected':''}>${esc(s.name)}${s.split==='validation'?' · validation':''}</option>`).join('');
  renderAIState();renderFinish();
}
function renderFinish(){
  const chosen=$('export-choice').value||state.selected?.timeline;
  $('export-choice').innerHTML=state.timelines.map(t=>`<option value="${esc(t.id)}" ${t.id===chosen?'selected':''}>${esc(t.name)}</option>`).join('');
  const id=$('export-choice').value,t=state.timelines.find(t=>t.id===id);
  $('chosen-summary').textContent=t?paths(state.timelines).get(id).map(o=>state.catalog.find(c=>c.kind===o.kind)?.name||o.kind).join(' → '):'';
  $('validation-summary').innerHTML=t?evaluationGroups().map(group=>{const a=aggregate(id,group.samples,state.results,group.split);return `<p><strong>${esc(group.name)}</strong>: ${a.tested}/${a.total} tested · ${a.failed} failed<br>${a.labeled} labeled and scored · ${a.unlabeled} unlabeled${a.labeled?` · box F1 ${a.f1===null?'—':a.f1.toFixed(3)}`:''}</p>`;}).join(''):'';
  $('export-chosen').disabled=!t;
  if(t){
    const path=paths(state.timelines).get(id),detector=state.catalog.find(c=>c.kind===path.at(-1)?.kind)?.detector,hasMeasurements=path.some(o=>state.catalog.find(c=>c.kind===o.kind)?.detector),issues=typeIssues(state.timelines,state.catalog).filter(i=>i.timeline===id||dependencyIds(state.timelines,id).has(i.operation)),held=aggregate(id,state.samples.filter(s=>exposure.status(s)==='unseen'),state.results,'validation');
    let note=$('export-status');if(!note){note=document.createElement('p');note.id='export-status';note.className='export-status';$('export-chosen').before(note);}
    note.textContent=issues.length?`Fix the sequence before export: ${issues[0].name} needs ${issues[0].needs.join(' or ')}; it receives ${issues[0].input}.`:`${detector?'Detector with object measurements.':hasMeasurements?'Transform pipeline with intermediate measurements.':'Transform-only pipeline: no object detection or measurements yet.'} ${held.labeled&&!held.failed?`Scored on ${held.labeled} held-out image${held.labeled===1?'':'s'}; inspect errors before deploying.`:'Detection accuracy has not been established on labeled held-out images.'}`;
    $('export-chosen').textContent=detector?'Download C++ detector':'Download C++ transforms';$('export-chosen').disabled=issues.length>0;
  }
  renderValidationReview(id);
}
function labelOverlay(sample,matches){
  return `<svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">${sample.boxes.map((b,i)=>`<rect class="${matches?.missed.includes(i)?'missed':''}" x="${b.x*100}" y="${b.y*100}" width="${b.width*100}" height="${b.height*100}"/><text x="${b.x*100+1}" y="${b.y*100+4}">${i+1}</text>`).join('')}</svg>`;
}
function detectionOverlay(detections,matches){
  if(!detections)return '';
  return `<svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">${detections.map((d,i)=>{const [x,y,w,h]=d.normalized_box;return `${matches?.extra.includes(i)?`<rect class="extra" x="${x*100}" y="${y*100}" width="${w*100}" height="${h*100}"/>`:''}<text x="${x*100+1}" y="${y*100+4}">${i+1}</text>`;}).join('')}</svg>`;
}
function renderValidationReview(id){
  const container=$('validation-review');if(!id){container.textContent='';return;}
  const focus=container.contains(document.activeElement)?document.activeElement:null,focusedImage=focus?.closest('[data-review-image]')?.dataset.reviewImage;
  const previousStage=$('review-stage')?.value,listScroll=container.querySelector('.validation-list')?.scrollTop||0;
  const rows=state.samples.map(sample=>{
    const review=reviewImage(id,sample,state.results.get(sample.id),executionErrors.get(sample.id)),running=activeRun?.currentId===sample.id;
    return `<button class="validation-row ${sample.id===state.active?'selected':''} ${review.status==='failed'||review.status==='mismatch'?'needs-attention':''}" data-review-image="${esc(sample.id)}" aria-pressed="${sample.id===state.active}"><img src="${esc(sample.data)}" alt=""><span><strong>${esc(sample.name)}</strong><small>${esc(imageRole(sample))}</small><span>${running?'Running… · ':''}${esc(review.summary)}</span></span></button>`;
  }).join('');
  const sample=state.samples.find(s=>s.id===state.active),image=state.results.get(state.active),review=sample?reviewImage(id,sample,image,executionErrors.get(sample.id)):null;
  let detail='';
  if(sample){
    const stages=review.path?.path.filter(oid=>image.stages[oid]?.details?.detections!==undefined)||[],selected=stages.includes(previousStage)&&previousStage!==review.finalId?previousStage:'final',stage=selected==='final'?review.finalStage:image.stages[selected];
    const options=`<option value="final">Final output</option>`+stages.filter(oid=>oid!==review.finalId).map(oid=>`<option value="${esc(oid)}" ${selected===oid?'selected':''}>Intermediate measurements · step ${review.path.path.indexOf(oid)+1}</option>`).join('');
    const measurements=stage?.details?.detections,unit=stage?.details?.unit||'px',fit=stage?.details?.fit,matches=matchedBoxes(sample,measurements,fit);
    const matchSummary=matches?`<p class="match-summary">${matches.missed.length?`Missed target labels: ${matches.missed.map(i=>i+1).join(', ')}. `:''}${matches.extra.length?`Extra detections: ${matches.extra.map(i=>i+1).join(', ')}.`:''}</p>`:'';
    const measurementTable=measurements?.length?`<div class="validation-measures"><table class="measure-table"><thead><tr><th>Object</th><th>Measurements</th></tr></thead><tbody>${measurements.slice(0,50).map((d,i)=>`<tr><th>${i+1}${matches?`<small>${matches.extra.includes(i)?'Extra detection':`Label ${matches.matches.find(m=>m.detection===i).label+1}`}</small>`:''}</th><td>${Object.entries(d.measurements).map(([key,value])=>esc(measurementText(key,value,unit))).join('<br>')}</td></tr>`).join('')}</tbody></table></div>`:'';
    detail=`<div class="validation-detail"><h3>${esc(sample.name)}</h3>${review.errors.map(error=>`<p class="error-copy">${esc(error)}</p>`).join('')}${executionErrors.has(sample.id)&&stage?.image?'<p class="help">The image below is from the previous successful run. It is excluded from the latest score until a retest succeeds.</p>':''}<label for="review-stage">Inspect output</label><select id="review-stage">${options}</select><div class="validation-image-pair"><figure><figcaption>Original · your target boxes</figcaption><div class="validation-frame"><img src="${esc(sample.data)}" alt="Original ${esc(sample.name)} with target labels">${labelOverlay(sample,matches)}</div></figure><figure><figcaption>${selected==='final'?'Final output':'Intermediate measurement output'}</figcaption>${stage?.image?`<div class="validation-frame predictions"><img src="${esc(stage.image)}" alt="${selected==='final'?'Final':'Intermediate'} output for ${esc(sample.name)}">${detectionOverlay(measurements,matches)}</div>`:'<p class="empty-preview">Run this image to see its result.</p>'}</figure></div><p class="help">Dashed boxes are your target labels. Green numbers identify detections in the table. Highlighted boxes are missed labels or extra detections. Label and detection numbers are separate lists.</p>${matchSummary}${selected!=='final'?`<p class="export-status">These measurements belong to an intermediate step. The final output is evaluated separately.</p>`:''}${fit?`<p>${fit.tp} matched · ${fit.fp} extra · ${fit.fn} missed${fit.f1===null?' · F1 is undefined for an empty negative image':` · box F1 ${fit.f1.toFixed(3)}`}</p>`:measurements?'<p class="help">Complete target labels to calculate box matches.</p>':''}${measurements?.length===0?'<p>No objects passed the selected filters.</p>':''}${measurementTable}${measurements?.length>50?`<p class="help">Showing the first 50 of ${measurements.length} detections. The C++ program reports every detection.</p>`:''}<div class="validation-detail-actions"><button data-review-label>Correct target labels</button><button data-review-run ${activeRun?'disabled':''}>Retest this image</button><button data-review-step="${esc(selected==='final'?review.finalId||'source':selected)}">Inspect in pipeline</button></div></div>`;
  }
  container.innerHTML=`<h2>Review each image</h2><p class="help">Select an image to compare its labels, result and measurements.</p><div class="validation-list">${rows}</div>${detail}`;
  container.querySelector('.validation-list').scrollTop=listScroll;
  if(focusedImage)container.querySelector(`[data-review-image="${CSS.escape(focusedImage)}"]`)?.focus({preventScroll:true});
  else if(focus?.id==='review-stage')$('review-stage')?.focus({preventScroll:true});
}
function snapshot() { return clone({...runBody(),active:state.active,selected:state.selected,screen:state.screen,example:state.example,description:$('description').value,context:$('context').value,answers:$('answers').value,guidance:{answers:state.questionAnswers,discovery:state.discovery}}); }
function recordFieldEdit(element){
  if(fieldEdit?.element===element&&!fieldEdit.recorded){
    state.undo.push(fieldEdit.before);if(state.undo.length>20)state.undo.shift();state.redo=[];fieldEdit.recorded=true;
    $('undo').disabled=false;$('redo').disabled=true;
  }
}
function restore(saved) {
  const guidance=readGuidance(saved.guidance);
  clearParameterDrafts();state.samples=saved.samples;state.timelines=saved.timelines;state.active=saved.active;state.selected=validSelection(saved.timelines,saved.selected);
  for(const id of ['description','context','answers'])$(id).value=saved[id]||'';
  for(const [id,key] of Object.entries(hardwareFields))$(id).value=saved.hardware[key]??'';
  $('measurements').querySelectorAll('input').forEach(i=>{i.checked=saved.measurements.fields.includes(i.value);});
  $('scale').value=saved.measurements.pixels_per_unit;$('unit').value=saved.measurements.unit;showHardwareFields();
  $('source-credit').textContent='';
  state.example=Boolean(saved.example);clearAI(true);state.questionAnswers=guidance.answers;state.discovery=guidance.discovery;renderDiscovery();showScreen(saved.screen||'images');
}
function executionKey(timelines) {return JSON.stringify(timelines.map(({id,parent_id,fork_after,operations})=>({id,parent_id,fork_after,operations})));}
function refreshEstimates() {
  const h=hardware();
  for(const image of state.results.values()) {
    for(const stage of Object.values(image.stages))if(stage.local_ms!=null)stage.target=estimate(stage.local_ms,h);
    for(const path of image.timelines){path.target=path.local_ms===null?null:estimate(path.local_ms,h);path.over_budget=path.target?.ms!=null&&path.target.ms>h.budget_ms;}
  }
}
function invalidate(schedule = true) {
  clearOptimization();
  stopIntake(); revision.bump(); stopRun(); clearTimeout(autoTimer); state.results.clear();executionErrors.clear();
  $('run').textContent = 'Run pipelines';
  status(state.samples.length ? 'Edits ready to run.' : 'Add an image to begin.'); render();
  if (schedule && $('auto-run').checked && state.samples.length && state.timelines.length) autoTimer = setTimeout(() => run(false), 450);
}
function commit(next, message = 'Pipeline updated.', before=snapshot()) {
  try {
    paths(next); const pixelsChanged=executionKey(state.timelines)!==executionKey(next)||JSON.stringify(before.samples)!==JSON.stringify(state.samples)||JSON.stringify(before.measurements)!==JSON.stringify(measurements());
    projectRevision++;state.undo.push(before); if (state.undo.length > 20) state.undo.shift();
    state.redo = []; state.timelines = next;
    if(state.draft||aiBusy)clearAI();else clearOptimization();
    state.selected = validSelection(next,state.selected);
    notify(); if(pixelsChanged)invalidate();else {refreshEstimates();render();} status(message); return true;
  } catch (error) { notify(error.message); return false; }
}
function edit(fn, message) { try { return commit(editGraph(state.timelines,fn),message); } catch (error) { notify(error.message); return false; } }
function undo(redo = false) {
  const from = redo ? state.redo : state.undo, to = redo ? state.undo : state.redo;
  if (!from.length) return;
  try{readGuidance(from.at(-1).guidance);paths(from.at(-1).timelines);}catch(error){notify(error.message);return;}
  fieldEdit=null;const resetDrafts=parameterDrafts.size;
  projectRevision++;to.push(snapshot()); restore(from.pop());
  notify(resetDrafts?'Project history restored. Unapplied parameter fields were reset.':''); invalidate();
}

function renderRunControls(){
  for(const id of ['run','run-all','validate-family','continue-run'])$(id).disabled=Boolean(activeRun)||!state.timelines.length;
  $('run').textContent=activeRun?'Running…':'Run pipelines';$('cancel-run').hidden=!activeRun;
  $('run-progress').hidden=!activeRun;
  if(activeRun){$('run-progress').max=activeRun.total;$('run-progress').value=activeRun.completed;}
  $('continue-run').hidden=!state.samples.some(s=>!state.results.has(s.id)||executionErrors.has(s.id))||(!state.results.size&&!executionErrors.size);
}
function stopRun(message=false){
  const stopped=activeRun;activeRun=null;stopped?.controller.abort();renderRunControls();
  if(message&&stopped)status(`Stopped · ${stopped.completed}/${stopped.total} images completed in this run. Completed results are kept; remaining images can be tested later.`);
}
async function run(all = false, remaining = false) {
  clearTimeout(autoTimer);
  if (!state.samples.length || !state.timelines.length) return notify('Add an image and a pipeline first.');
  stopRun();const token = revision.bump();
  const requestStart=performance.now();
  const samples=(all?state.samples:state.samples.filter(s=>s.id===state.active)).filter(s=>!remaining||!state.results.has(s.id)||executionErrors.has(s.id));
  if(!samples.length)return status('All images already have results. Run all images to test them again.');
  const body=clone(runBody(samples)),session={token,controller:new AbortController(),completed:0,total:samples.length,currentId:null,all};
  activeRun=session;notify();renderRunControls();let failures=0;
  try {
    for(const sample of body.samples){
      if(activeRun!==session||!revision.current(token))return;
      session.currentId=sample.id;executionErrors.delete(sample.id);
      status(`Running ${session.completed+1}/${session.total}: ${sample.name} · ${session.completed} completed`);renderFinish();
      const result=await api('/api/timelines/run',{...body,samples:[sample]},session.controller.signal);
      if(activeRun!==session||!revision.current(token))return;
      result.images.forEach(image=>state.results.set(image.sample_id,image));session.completed++;
      failures+=result.images.flatMap(i=>i.timelines).filter(t=>t.errors).length;refreshEstimates();
      $('timing-note').textContent=result.timing_note;$('estimate-note').textContent=result.estimate_note;
      render();renderRunControls();
    }
    status(failures?`Finished · ${session.completed} images tested · ${failures} paths need attention. Select a yellow step.`:`Ready · ${session.completed} image${session.completed===1?'':'s'} tested · timings measured ${state.publicMode?'on the server':'on this computer'}`);
    $('status').title=`Total request time: ${Math.round(performance.now()-requestStart)} ms, including previews and transfer.`;
  } catch(error){
    if(error.name!=='AbortError'&&activeRun===session&&revision.current(token)){
      executionErrors.set(session.currentId,error.message);notify(error.message);status(`Run stopped after ${session.completed}/${session.total} completed. ${body.samples.find(s=>s.id===session.currentId)?.name} failed; later images were not run.`);
    }
  } finally { if(activeRun===session){activeRun=null;renderRunControls();renderFinish();} }
}

function renderSamples() {
  $('screen-images').classList.toggle('has-family',state.samples.length>0);
  $('image-count').textContent = `${state.samples.length} / 12`;
  $('samples').innerHTML = state.samples.map(s => `<div class="sample ${s.id === state.active ? 'selected' : ''}"><button class="sample-thumb" data-image="${esc(s.id)}" aria-label="Preview ${esc(s.name)}"><img src="${esc(s.data)}" alt=""></button><div class="sample-info"><button data-image="${esc(s.id)}">${esc(s.name)}</button><select data-split="${esc(s.id)}" aria-label="Image role for ${esc(s.name)}"><option value="train" ${s.split === 'train' ? 'selected' : ''}>Training</option><option value="validation" ${s.split === 'validation' ? 'selected' : ''}>Validation</option></select><p class="sample-label-status ${s.split==='validation'&&exposure.status(s)!=='unseen'?'exposure-warning':''}">${esc(imageRole(s))}</p></div><button class="sample-remove" data-remove-image="${esc(s.id)}" aria-label="Remove ${esc(s.name)}">×</button></div>`).join('');
  $('active-image').textContent = state.samples.find(s => s.id === state.active)?.name || 'No image selected';
}
function nodeCard(t, op, index, inherited, branchStart) {
  const id = op?.id || 'source', stage = currentResult()?.stages[id], source = state.samples.find(s => s.id === state.active);
  const image = stage?.image || (id === 'source' ? source?.data : null);
  const label = op ? state.catalog.find(c => c.kind === op.kind)?.name || op.kind : 'Starting image';
  const selected = state.selected?.timeline === t.id && state.selected?.node === id;
  const target = stage?.target;
  const shape=stage?`${stage.width} × ${stage.height} · ${{rgb:'color',gray:'grayscale',mask:'mask'}[stage.kind]||stage.kind}`:'';
  let meta = id === 'source' ? `<span>Original image</span><span class="node-shared">${esc(shape)}</span>` : stage?.local_ms==null ? '<span class="node-shared">Not run yet</span>' : `<span class="local">${state.publicMode?'Server':'Local'} ${ms(stage.local_ms)} ms</span>${target?.estimated?`<span class="target">Target ≈ ${ms(target.ms)} ms</span>`:`<span class="node-shared">${esc(shape)}</span>`}`;
  if (inherited) meta += '<span class="node-shared">Shared with parent</span>';
  const preview = image ? `<img src="${esc(image)}" alt="${esc(label)} output" loading="lazy">` : `<p>${stage?.status === 'error' ? 'Input incompatible<br>Select to resolve' : stage?.status === 'blocked' ? 'Waiting for earlier step' : 'Run to preview'}</p>`;
  const at=op?t.operations.findIndex(o=>o.id===op.id):-1;
  let controls=op&&!inherited?'<span class="drag-hint">⠿ Drag to reorder</span>':inherited?'<span class="drag-hint">Shared prefix</span>':'<span class="drag-hint">Original image</span>';
  if(selected&&op&&!inherited){controls=[[-1,'←','earlier'],[1,'→','later']].map(([delta,symbol,word])=>{const proposal=previewMove(state.timelines,t.id,op.id,at+delta,state.catalog);return `<button data-move-op="${esc(op.id)}" data-move-timeline="${esc(t.id)}" data-move-to="${at+delta}" aria-disabled="${!proposal.allowed}" aria-describedby="move-feedback" title="${esc(proposal.reason)}" aria-label="Move ${esc(label)} ${word}">${symbol}</button>`;}).join('')+`<button data-arrange="${esc(t.id)}" aria-label="Arrange steps in ${esc(t.name)}">Arrange</button><button data-fork-node="${esc(op.id)}" data-fork-pipeline="${esc(t.id)}">Branch</button>`;}
  return `<div class="node-wrap"><button class="node ${selected ? 'selected' : ''} ${inherited ? 'inherited' : ''} ${branchStart ? 'branch-start' : ''} ${stage?.error ? 'error' : ''}" data-node="${esc(id)}" data-timeline="${esc(t.id)}" draggable="${Boolean(op && !inherited)}" aria-label="${esc(label)}${inherited ? ', shared step' : ''}" aria-pressed="${selected}" ${op&&!inherited?'aria-keyshortcuts="Alt+ArrowLeft Alt+ArrowRight"':''}><span class="node-top"><span class="node-num">${String(index).padStart(2,'0')}</span><span>${esc(label)}</span></span><span class="node-preview">${preview}</span><span class="node-meta">${meta}</span></button><div class="node-inline">${controls}</div></div>`;
}
function sharedInputCard(t,path,inherited){
  const fork=inherited?path[inherited-1]:null,stage=currentResult()?.stages[fork?.id||'source'],source=state.samples.find(s=>s.id===state.active),parent=state.timelines.find(p=>p.id===t.parent_id);
  const image=stage?.image||(!fork?source?.data:null),name=fork?state.catalog.find(c=>c.kind===fork.kind)?.name:'Starting image';
  const preview=image?`<img src="${esc(image)}" alt="Input after ${esc(name)}">`:'<p>Run to preview</p>';
  return `<div class="node-wrap shared-input-wrap"><button class="node shared-input" data-prefix="${esc(t.id)}" aria-expanded="false" aria-label="Show ${inherited} shared steps from ${esc(parent.name)}"><span class="node-top">↳ Shared input</span><span class="node-preview">${preview}</span><span class="node-meta"><strong>${esc(parent.name)}</strong><span>Through ${esc(name)}</span><span>${inherited} shared step${inherited===1?'':'s'}</span></span></button><div class="node-inline"><button data-prefix="${esc(t.id)}" aria-expanded="false">Show shared steps</button></div></div>`;
}
function renderTimelines() {
  const focused=document.activeElement?.closest('[data-node]');const focus=focused?{timeline:focused.dataset.timeline,node:focused.dataset.node}:null;
  const outlineFocus=document.activeElement?.closest('#outline-list [data-focus-pipeline],#outline-list [data-compare-pipeline]');const outlineAnchor=outlineFocus?{kind:outlineFocus.dataset.comparePipeline?'compare-pipeline':'focus-pipeline',id:outlineFocus.dataset.comparePipeline||outlineFocus.dataset.focusPipeline}:null;
  document.querySelectorAll('[data-node-row]').forEach(row=>pipelineScrolls.set(row.dataset.nodeRow,row.scrollLeft));
  const graph = paths(state.timelines), result = currentResult(),ordered=orderedTimelines(state.timelines);
  for(const id of comparedPipelines)if(!graph.has(id))comparedPipelines.delete(id);
  if(state.selected)pipelineSelections.set(state.selected.timeline,state.selected.node);
  $('outline-count').textContent=ordered.length;
  $('outline-list').innerHTML=ordered.map(t=>{
    const path=graph.get(t.id),summary=result?.timelines.find(v=>v.id===t.id),stage=result?.stages[path.at(-1)?.id],parent=state.timelines.find(p=>p.id===t.parent_id),supports=path.flatMap(supportingIds);
    let depth=0,ancestor=parent;while(ancestor){depth++;ancestor=state.timelines.find(p=>p.id===ancestor.parent_id);}
    const fork=parent?graph.get(parent.id).find(op=>op.id===t.fork_after):null;
    return `<div class="outline-entry depth-${Math.min(depth,3)} ${state.selected?.timeline===t.id?'active':''}"><button data-focus-pipeline="${esc(t.id)}" aria-pressed="${state.selected?.timeline===t.id}">${stage?.image?`<img src="${esc(stage.image)}" alt="">`:'<span class="outline-placeholder">→</span>'}<span><strong>${esc(t.name)}</strong><small>${stage?.details?.count!=null?`${stage.details.count} objects · `:''}${summary?.errors?'Needs attention':`${ms(summary?.local_ms)} ms`}</small>${parent?`<small>↳ ${esc(parent.name)} · ${esc(fork?state.catalog.find(c=>c.kind===fork.kind)?.name:'Source')}</small>`:''}${supports.length?`<small class="support-mark">✓ ${supports.length} supporting method${supports.length===1?'':'s'}</small>`:''}</span></button>${pipelineView==='compare'?`<label class="outline-compare"><input type="checkbox" data-compare-pipeline="${esc(t.id)}" ${comparedPipelines.has(t.id)?'checked':''} aria-label="Compare ${esc(t.name)}">Compare</label>`:''}</div>`;
  }).join('');
  $('pipeline-mobile-select').innerHTML=ordered.map(t=>`<option value="${esc(t.id)}" ${state.selected?.timeline===t.id?'selected':''}>${esc(t.name)}</option>`).join('');
  $('view-focus').setAttribute('aria-pressed',String(pipelineView==='focus'));$('view-compare').setAttribute('aria-pressed',String(pipelineView==='compare'));
  document.querySelector('.pipeline-layout').classList.toggle('comparison-mode',pipelineView==='compare');
  $('choose-comparisons').hidden=pipelineView!=='compare';$('choose-comparisons').textContent=`${comparedPipelines.size} compared · choose`;
  $('pipeline-view-help').textContent=pipelineView==='focus'?'Select a pipeline to edit':`Comparing ${comparedPipelines.size} of ${ordered.length} · choose up to 3`;
  const shown=ordered.filter(t=>pipelineView==='compare'?comparedPipelines.has(t.id):state.selected?.timeline===t.id);
  $('timelines').innerHTML = shown.map((t,i) => {
    const path=graph.get(t.id),inherited=path.length-t.operations.length,summary=result?.timelines.find(v=>v.id===t.id),expanded=expandedPrefixes.has(t.id),compact=t.parent_id&&!expanded;
    const total=summary?.errors?'Fix steps to time path':`${state.publicMode?'Server':'Local'} ${ms(summary?.local_ms)} ms${hardware().mode!=='local'?` · target ≈ ${ms(summary?.target?.ms)} ms`:''}`;
    const start=compact?sharedInputCard(t,path,inherited):nodeCard(t,null,0,Boolean(t.parent_id),false);
    const steps=path.map((op,j)=>compact&&j<inherited?'':`${j>=inherited?dropGap(t.id,j-inherited):'<span class="node-connector" aria-hidden="true"></span>'}${nodeCard(t,op,j+1,j<inherited,Boolean(t.parent_id&&j===inherited))}`).join('');
    const parent=state.timelines.find(p=>p.id===t.parent_id),fork=t.parent_id?graph.get(t.parent_id).find(o=>o.id===t.fork_after):null;
    const provenance=parent?`<p class="branch-provenance">Input from <button data-focus-pipeline="${esc(parent.id)}" data-focus-step="${esc(t.fork_after)}">${esc(parent.name)}</button> after ${esc(fork?state.catalog.find(c=>c.kind===fork.kind).name:'Starting image')} · ${inherited} shared steps${expanded?` <button data-prefix="${esc(t.id)}" aria-expanded="true">Hide shared steps</button>`:''}</p>`:'';
    const supporters=[...new Set(path.flatMap(supportingIds))],supportLinks=supporters.length?`<p class="support-provenance">Confirmed by ${supporters.map(id=>`<button data-focus-pipeline="${esc(id)}">${esc(state.timelines.find(p=>p.id===id)?.name||id)}</button>`).join(' + ')}</p>`:'';
    return `<section class="timeline ${parent?'branch-timeline':''}" aria-label="${esc(t.name)}"><div class="timeline-heading"><button class="timeline-title" data-select-timeline="${esc(t.id)}">${esc(t.name)}</button>${parent?'<span class="branch-label">branch</span>':''}<span class="timeline-total ${summary?.over_budget?'over-budget':''}" title="${summary?.over_budget?'Exceeds your target budget':'All required operations, counted once'}">${total}</span><div class="row-actions"><button data-arrange="${esc(t.id)}">Arrange steps</button><button data-add="${esc(t.id)}" aria-label="Add operation to ${esc(t.name)}">＋ Step</button></div></div>${provenance}${supportLinks}<div class="nodes" data-node-row="${esc(t.id)}" role="group" aria-label="Steps in ${esc(t.name)}">${start}${steps}${dropGap(t.id,t.operations.length)}<button class="node-add" data-add="${esc(t.id)}" aria-label="Append operation to ${esc(t.name)}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg></button></div>${t.rationale?(pipelineView==='compare'?`<details class="timeline-explanation"><summary>Why this approach</summary><p>${esc(t.rationale)}</p></details>`:`<p class="timeline-rationale">${esc(t.rationale)}</p>`):''}</section>`;
  }).join('')||(pipelineView==='compare'?'<div class="empty"><h2>Choose pipelines to compare.</h2><p>Select up to 3 pipelines from the list.</p></div>':'<div class="empty"><h2>Start with an image and a transform.</h2><p>Generate approaches from your image family, or add a manual approach.</p></div>');
  document.querySelectorAll('[data-node-row]').forEach(row=>row.scrollLeft=pipelineScrolls.get(row.dataset.nodeRow)||0);
  $('undo').disabled=!state.undo.length;$('redo').disabled=!state.redo.length;
  if(outlineAnchor&&document.activeElement===document.body)document.querySelector(`#outline-list [data-${outlineAnchor.kind}="${CSS.escape(outlineAnchor.id)}"]`)?.focus({preventScroll:true});
  if(focus&&document.activeElement===document.body)document.querySelector(`.node[data-timeline="${CSS.escape(focus.timeline)}"][data-node="${CSS.escape(focus.node)}"]`)?.focus({preventScroll:true});
}
function renderComparison() {
  const result=currentResult();
  $('comparison').innerHTML=state.timelines.length?`<details ${state.compareOpen?'open':''}><summary>Compare results · this image: ${esc(state.samples.find(s=>s.id===state.active)?.name||'add an image')}</summary><div class="result-grid">${state.timelines.map(t=>{
    const path=result?.timelines.find(p=>p.id===t.id),stage=result?.stages[path?.path.at(-1)],d=stage?.details;
    return `<button class="result-card" data-result="${esc(t.id)}" data-end="${esc(path?.path.at(-1)||'source')}">${stage?.image?`<img src="${esc(stage.image)}" alt="Final result for ${esc(t.name)}">`:''}<span><strong>${esc(t.name)}</strong><span>This image: ${d?.count!=null?`${d.count} objects · `:''}${ms(path?.local_ms)} ms${path?.errors?' · failed':''}</span><small>${d?.fit?`Box F1 ${d.fit.f1===null?'—':d.fit.f1.toFixed(3)} · ${d.fit.tp} matched / ${d.fit.fp} extra / ${d.fit.fn} missed`:'Unscored · add complete target labels'}</small></span></button>`;
  }).join('')}</div><details class="collection-details" ${state.collectionOpen?'open':''}><summary>Collection evaluation · ${state.samples.length} image${state.samples.length===1?'':'s'}</summary><table class="collection-table"><thead><tr><th>Pipeline</th><th>Training collection</th><th>Validation collection</th></tr></thead><tbody>${state.timelines.map(t=>`<tr><th>${esc(t.name)}</th>${['train','validation'].map(split=>{const a=aggregate(t.id,state.samples,state.results,split);return `<td>${a.tested}/${a.total} tested · ${a.failed} failed · ${a.untested} untested<br>${a.labeled} scored · ${a.unlabeled} unlabeled<br>${a.labeled?`F1 ${a.f1===null?'—':a.f1.toFixed(3)} · ${a.tp} matched / ${a.fp} extra / ${a.fn} missed${a.negatives?`<br>${a.emptyCorrect}/${a.negatives} negatives clear`:''}`:'No complete labels scored'}</td>`;}).join('')}</tr>`).join('')}</tbody></table><p class="help">F1 measures box matches at 50% overlap; it does not measure mask or dimension precision. Failed and unlabeled images are excluded from F1 and reported above. Keep fresh validation images to check generalization. Validation totals include reused images; the final validation screen separates images previously submitted for AI.</p></details></details>`:'';
}
function fieldHTML(key, schema, value) {
  const units={hue_low:'Hue low (0–179)',hue_high:'Hue high (0–179)',saturation_low:'Saturation low (0–255)',saturation_high:'Saturation high (0–255)',value_low:'Brightness low (0–255)',value_high:'Brightness high (0–255)',kernel:'Kernel (odd pixels)',block_size:'Neighborhood (odd px)',min_area:'Min image fraction',max_area:'Max image fraction',max_side:'Longest side (px)',value:'Brightness cutoff (0–255)',min_support:'Required supporters',iou:'Minimum box overlap (IoU)',match_text:'Require matching decoded text',min_pixels:'Minimum region area (px²)',max_pixels:'Maximum region area (px²)',pixels_per_level:'Distance per gray level (px)',min_distance:'Minimum center spacing (px)',min_radius:'Minimum radius (px)',max_radius:'Maximum radius (px)',edge_threshold:'Edge threshold',votes:'Detection vote threshold',min_length:'Minimum segment length (px)',max_gap:'Maximum segment gap (px)'};
  const label = units[key]||pretty(key), id = `param-${key}`;
  if(key==='pipeline_ids'){
    const graph=paths(state.timelines),selected=new Set(String(value||'').split(','));
    const candidates=state.timelines.filter(t=>t.id!==selectedTimeline()?.id);
    return `<div class="support-field"><label for="${id}">Supporting pipelines</label><select id="${id}" data-param="pipeline_ids" multiple size="${Math.min(4,Math.max(2,candidates.length))}">${candidates.map(t=>`<option value="${esc(t.id)}" ${selected.has(t.id)?'selected':''}>${esc(t.name)}${state.catalog.find(c=>c.kind===graph.get(t.id).at(-1)?.kind)?.detector?'':' · needs final detector'}</option>`).join('')}</select><p class="help">Select one or more. Ctrl/Cmd-click adds selections. Supports must cover the same object extent.</p></div>`;
  }
  if (schema.type === 'boolean') return `<label class="checkbox-param"><input id="${id}" data-param="${esc(key)}" type="checkbox" ${value ? 'checked' : ''}>${esc(label)}</label>`;
  const input = schema.enum ? `<select id="${id}" data-param="${esc(key)}">${schema.enum.map(v => `<option ${v === value ? 'selected' : ''}>${esc(v)}</option>`).join('')}</select>` : `<input id="${id}" data-param="${esc(key)}" type="number" value="${esc(value)}" ${schema.minimum !== undefined ? `min="${schema.minimum}"` : ''} ${schema.maximum !== undefined ? `max="${schema.maximum}"` : ''} step="${schema.type === 'integer' ? (key === 'kernel' || key === 'block_size' ? '2' : '1') : 'any'}" required>`;
  return `<div><label for="${id}">${esc(label)}</label>${input}</div>`;
}
function fieldValue(input){return input.multiple?[...input.selectedOptions].map(o=>o.value).join(','):input.type==='checkbox'?input.checked:input.value;}
function restoreField(input,value){if(input.multiple){const ids=String(value||'').split(',');for(const option of input.options)option.selected=ids.includes(option.value);}else if(input.type==='checkbox')input.checked=value;else input.value=value;}
function renderInspector() {
  parameterDrafts.reconcile(state.timelines);
  const t = selectedTimeline(), op = selectedOperation();
  const container=$('inspector'),selectionKey=JSON.stringify(state.selected),parameterKey=JSON.stringify([op?.id,op?.kind,ownerOf(op?.id)?.id,op?.params]),nameKey=JSON.stringify([t?.id,t?.name]);
  const sameSelection=container.dataset.selectionKey===selectionKey,focused=sameSelection&&container.contains(document.activeElement)?document.activeElement:null;
  const retainedForm=sameSelection&&container.dataset.parameterKey===parameterKey?$('params-form'):null;
  const retainedName=container.dataset.nameKey===nameKey?$('timeline-name'):null;
  const panelScroll=container.closest('.right-panel')?.scrollTop;
  container.dataset.selectionKey=selectionKey;container.dataset.parameterKey=parameterKey;container.dataset.nameKey=nameKey;
  if (!t) { container.innerHTML = '<h2>Inspect a step</h2><p class="help">Select any image in a pipeline to see parameters, timings and measurements.</p>'; return; }
  const stage = currentResult()?.stages[state.selected.node], owner = op ? ownerOf(op.id) : null, shared = op && owner.id !== t.id;
  const catalog = state.catalog.find(c => c.kind === op?.kind), at = owner?.operations.findIndex(o => o.id === op?.id);
  const image = stage?.image || (state.selected.node === 'source' ? state.samples.find(s => s.id === state.active)?.data : null);
  const target = stage?.target, details = stage?.details || {};
  const measurementsHTML = details.detections?.length ? `<div class="inspector-block"><h3>${details.count} object${details.count === 1 ? '' : 's'} · ${esc(details.unit)}</h3><table class="measure-table"><thead><tr><th>Object</th><th>Measurements</th></tr></thead><tbody>${details.detections.slice(0,50).map((d,i) => `<tr><td>${i+1}</td><td>${Object.entries(d.measurements).map(([k,v]) => esc(measurementText(k,v,details.unit))).join('<br>')}</td></tr>`).join('')}</tbody></table>${details.count > 50 ? '<p class="help">Showing the first 50 objects.</p>' : ''}<p class="help">${esc(details.measurement_basis||'Detector measurements')}. Color samples the original image. Center is in original pixels.</p></div>` : details.count === 0 ? '<p class="help">No objects detected.</p>' : '';
  let stats = stage?.status === 'ok' ? `<dl class="stat-list"><dt>Output</dt><dd>${stage.width} × ${stage.height} · ${esc(stage.kind)}</dd>${op ? `<dt>${state.publicMode?'Server':'Local'} median</dt><dd>${ms(stage.local_ms)} ms</dd><dt>${state.publicMode?'Server':'Local'} run range</dt><dd>${stage.local_range_ms.map(ms).join('–')} ms</dd><dt>${target.estimated ? 'Target estimate' : 'Target measured'}</dt><dd>${ms(target.ms)} ms</dd>${target.estimated ? `<dt>Planning range</dt><dd>${ms(target.low_ms)}–${ms(target.high_ms)} ms</dd>` : ''}` : ''}${details.foreground_pct !== undefined ? `<dt>Foreground</dt><dd>${details.foreground_pct}%</dd>` : ''}${details.separation != null ? `<dt>Box separation proxy</dt><dd>${details.separation}</dd>` : ''}${details.fit ? `<dt>Labeled image F1</dt><dd>${details.fit.f1 === null ? '—' : details.fit.f1.toFixed(3)}</dd><dt>TP / FP / FN</dt><dd>${details.fit.tp} / ${details.fit.fp} / ${details.fit.fn}</dd>` : ''}</dl>` : '';
  $('inspector').innerHTML = `<h2>${esc(catalog?.name || 'Starting image')}</h2>${image ? `<img class="inspector-image" src="${esc(image)}" alt="Selected step output">` : ''}${stage?.error ? `<p class="error-copy">${esc(stage.error)}</p>` : ''}${target?.estimated ? `<p class="help">${esc(target.basis)}. Ranges are approximate.</p>` : ''}${catalog ? `<p class="inspector-note">${esc(catalog.description)}</p>` : '<p class="help">The source image is shared. Fork here to compare completely different approaches.</p>'}${shared ? `<p class="error-copy">Shared from ${esc(owner.name)}. Editing it changes every dependent branch.</p><button id="edit-owner" class="full">Edit in parent pipeline</button>` : op ? `<div class="inspector-controls"><button id="move-left" ${at===0 ? 'disabled' : ''}>← Earlier</button><button id="move-right" ${at===owner.operations.length-1 ? 'disabled' : ''}>Later →</button><button id="remove-step">Remove</button></div><form id="params-form"><div class="param-grid">${Object.entries(catalog.fields).map(([k,s]) => fieldHTML(k,s,op.params[k])).join('')}</div>${Object.keys(catalog.fields).length ? '<button class="full" type="submit">Apply parameters</button>' : '<p class="help">No parameters for this operation.</p>'}</form>` : ''}<details class="step-diagnostics"><summary>Timing &amp; output details</summary>${stats}</details><div class="inspector-controls"><button id="fork">⑂ Branch from here</button><button id="insert-step">＋ Add step</button></div>${measurementsHTML}<div class="inspector-block"><h3>Pipeline settings</h3><label for="timeline-name">Name</label><input id="timeline-name" value="${esc(t.name)}" maxlength="100">${t.parent_id ? `<label for="fork-point">Branch from parent step</label><select id="fork-point"><option value="source" ${t.fork_after==='source'?'selected':''}>Starting image</option>${paths(state.timelines).get(t.parent_id).map(o => `<option value="${esc(o.id)}" ${t.fork_after===o.id?'selected':''}>${esc(state.catalog.find(c=>c.kind===o.kind).name)}</option>`).join('')}</select>` : ''}<button id="delete-timeline" class="full">Remove this pipeline</button></div>`;
  $('edit-owner')?.addEventListener('click', () => select(owner.id,op.id));
  $('move-left')?.addEventListener('click', () => move(owner.id,op.id,at-1));
  $('move-right')?.addEventListener('click', () => move(owner.id,op.id,at+1));
  $('remove-step')?.addEventListener('click', () => edit(next => { const timeline = next.find(v=>v.id===owner.id); timeline.operations = timeline.operations.filter(o=>o.id!==op.id); }));
  if(retainedForm&&$('params-form'))$('params-form').replaceWith(retainedForm);
  if(retainedName&&$('timeline-name'))$('timeline-name').replaceWith(retainedName);
  if(!retainedForm&&op&&$('params-form')){
    const draft=parameterDrafts.read(op);
    if(draft)for(const input of $('params-form').querySelectorAll('[data-param]'))restoreField(input,draft[input.dataset.param]);
    $('params-form').addEventListener('input',()=>{
      const values=Object.fromEntries([...$('params-form').querySelectorAll('[data-param]')].map(input=>[input.dataset.param,fieldValue(input)]));
      parameterDrafts.record(op,values);projectRevision++;
      if(intake?.kind==='open'){stopIntake();notify('Project opening cancelled because you edited parameters.');}
      renderParameterState();
    });
  }
  if(!retainedForm)$('params-form')?.addEventListener('submit', e => {
    e.preventDefault(); const params = {};
    e.currentTarget.querySelectorAll('[data-param]').forEach(input => { params[input.dataset.param] = input.type === 'checkbox'||input.tagName === 'SELECT' ? fieldValue(input) : Number(input.value); });
    const draft=parameterDrafts.read(op);parameterDrafts.delete(op.id);
    if(!edit(next => { next.find(v=>v.id===owner.id).operations.find(o=>o.id===op.id).params = params; })&&draft)parameterDrafts.record(op,draft);
    renderParameterState();
  });
  $('fork').addEventListener('click', () => {
    const id = uid('timeline'), forkAfter = state.selected.node;
    if (edit(next => next.push({id,name:`${t.name.slice(0,70)} · alternative`,parent_id:t.id,fork_after:forkAfter,rationale:'Explore an alternative from this shared step.',operations:[]}))) select(id,'source');
  });
  $('insert-step').addEventListener('click', () => openAdd(t.id, shared ? 0 : op ? t.operations.findIndex(o=>o.id===op.id)+1 : 0));
  if(!retainedName){
    $('timeline-name').addEventListener('input',()=>{projectRevision++;if(intake?.kind==='open'){stopIntake();notify('Project opening cancelled because you edited the pipeline name.');}});
    $('timeline-name').addEventListener('change', e => { if (e.target.value.trim()) edit(next => { next.find(v=>v.id===t.id).name=e.target.value.trim(); }); });
  }
  $('fork-point')?.addEventListener('change', e => edit(next => { next.find(v=>v.id===t.id).fork_after=e.target.value; }));
  $('delete-timeline').addEventListener('click', () => {
    if (state.timelines.some(v=>v.parent_id===t.id)) return notify('This pipeline has dependent branches. Remove those branches first.');
    commit(state.timelines.filter(v=>v.id!==t.id));
  });
  const exportButton=document.createElement('button');exportButton.className='primary full';exportButton.id='export-timeline';exportButton.textContent='Export this pipeline to C++';
  exportButton.addEventListener('click',()=>exportSelected(t.id));$('inspector').append(exportButton);
  const exportHelp=document.createElement('p');exportHelp.className='help';exportHelp.textContent='Exports the full selected path, including shared steps, in this exact order. Build with OpenCV and C++17 (C++20 for barcode reading); runs offline on CPU.';$('inspector').append(exportHelp);
  if(focused){const replacement=focused.isConnected?focused:focused.id?$(focused.id):null;replacement?.focus({preventScroll:true});}
  if(sameSelection&&panelScroll!=null)container.closest('.right-panel').scrollTop=panelScroll;
  renderParameterState();
}
function renderParameterState(){
  parameterDrafts.reconcile(state.timelines);const first=[...parameterDrafts.entries.keys()][0],op=ownerOf(first)?.operations.find(o=>o.id===first);
  const notice=$('pending-parameters');notice.hidden=!parameterDrafts.size;
  notice.innerHTML=op?`<span>${parameterDrafts.size} step${parameterDrafts.size===1?' has':'s have'} unapplied parameters. Previews, saved projects and C++ use the last applied values.</span><button data-review-parameters="${esc(op.id)}">Review changes</button><button data-discard-parameters>Discard changes</button>`:'';
  const form=$('params-form');if(form){let note=form.querySelector('.parameter-draft-note');if(!note){note=document.createElement('div');note.className='parameter-draft-note';form.append(note);}note.hidden=!parameterDrafts.entries.has(selectedOperation()?.id);note.innerHTML='<p>Unapplied changes. Apply to update the pipeline.</p><button type="button" data-reset-parameters>Reset parameters</button>';}
}
async function exportSelected(id) {
  try {
    const required=dependencyIds(state.timelines,id),pending=state.timelines.flatMap(t=>t.operations).find(op=>required.has(op.id)&&parameterDrafts.entries.has(op.id));
    if(pending){select(ownerOf(pending.id).id,pending.id);return notify('Apply or reset this step’s pending parameters before exporting this path.');}
    notify();const response=await fetch('/api/timelines/export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({timelines:state.timelines,selected_timeline_id:id,measurements:measurements()})});
    if(!response.ok){const data=await response.json();throw Error(Array.isArray(data.detail)?data.detail.map(e=>e.msg).join('; '):data.detail);}
    const url=URL.createObjectURL(await response.blob()),a=document.createElement('a');a.href=url;a.download='pipeline-detector.zip';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);status('C++ pipeline exported · build instructions included.');
  }catch(error){notify(error.message);}
}
function render() { exposure.retain([...state.samples,...state.undo.flatMap(s=>s.samples),...state.redo.flatMap(s=>s.samples)]);renderSamples(); renderTimelines(); renderInspector();renderComparison();renderFlow();renderRunControls();renderParameterState(); $('save').disabled = !state.samples.length; }
function dropGap(tid,index,tag='span'){return `<${tag} class="drop-gap ${tag==='li'?'sequence-gap':''}" data-drop-gap="${index}" data-drop-timeline="${esc(tid)}" aria-hidden="true"></${tag}>`;}
function move(tid,oid,index){
  const proposal=previewMove(state.timelines,tid,oid,index,state.catalog);
  if(!proposal.allowed){notify();moveFeedback(proposal.reason,true);return false;}
  const from=state.timelines.find(t=>t.id===tid).operations.findIndex(o=>o.id===oid);if(from===index)return false;
  const before=snapshot();state.selected={timeline:tid,node:oid};
  if(!commit(proposal.next,`Step moved. ${proposal.affected.length?proposal.reason:'Undo is available.'}`,before))return false;
  if($('arrange-dialog').open){renderArrange(tid);$('arrange-list').querySelector(`[data-sequence-node="${CSS.escape(oid)}"]`)?.focus();}
  else {const card=document.querySelector(`.node[data-timeline="${CSS.escape(tid)}"][data-node="${CSS.escape(oid)}"]`);card?.focus({preventScroll:true});card?.scrollIntoView({block:'nearest',inline:'nearest'});}
  moveFeedback(proposal.affected.length?proposal.reason:'Step moved. The preview will update.');return true;
}
function moveFeedback(text,error=false){for(const id of ['move-feedback','arrange-feedback']){const e=$(id);if(e){e.textContent=text;e.hidden=!text;e.classList.toggle('move-error',error);}}}
function renderArrange(tid){
  arrangeTimeline=tid;const t=state.timelines.find(t=>t.id===tid);if(!t)return $('arrange-dialog').close();
  const path=paths(state.timelines).get(tid),inherited=path.length-t.operations.length;
  $('arrange-title').textContent=`Arrange ${t.name}`;
  $('arrange-copy').hidden=!t.parent_id;
  $('arrange-copy').disabled=path.length>12;
  $('arrange-help').textContent=`Use the arrow buttons, drag into a gap, or press Alt + ↑ / ↓ on a row.${inherited?(path.length>12?` The first ${inherited} steps are shared. This ${path.length}-step path exceeds the 12-step copy limit; edit shared steps in the parent.`:` The first ${inherited} steps are shared; make an independent copy to rearrange them here.`):''}`;
  $('arrange-list').innerHTML=path.map((op,i)=>{
    const own=i>=inherited,at=i-inherited,c=state.catalog.find(c=>c.kind===op.kind),left=own?previewMove(state.timelines,tid,op.id,at-1,state.catalog):null,right=own?previewMove(state.timelines,tid,op.id,at+1,state.catalog):null;
    const buttons=own?[[-1,'↑','earlier',left],[1,'↓','later',right]].map(([delta,symbol,word,p])=>`<button data-move-op="${esc(op.id)}" data-move-timeline="${esc(tid)}" data-move-to="${at+delta}" aria-disabled="${!p.allowed}" aria-describedby="arrange-feedback" title="${esc(p.reason)}" aria-label="Move ${esc(c.name)} ${word}">${symbol}</button>`).join(''):`<span class="sequence-shared">Shared</span>`;
    return `${own?dropGap(tid,at,'li'):''}<li class="sequence-row ${own?'':'inherited'}" data-sequence-node="${esc(op.id)}" data-sequence-timeline="${esc(tid)}" draggable="${own}" tabindex="0" ${own?'aria-keyshortcuts="Alt+ArrowUp Alt+ArrowDown"':''}><span class="sequence-grip" aria-hidden="true">${own?'⠿':'↳'}</span><span class="sequence-number">${i+1}</span><span class="sequence-name">${esc(c.name)}<small>${esc(pretty(inputKind(path,i,state.catalog)||'invalid'))} → ${esc(pretty(outputKind(op.kind,inputKind(path,i,state.catalog),op.params)||'invalid'))} · ${state.publicMode?'Server':'Local'} ${ms(currentResult()?.stages[op.id]?.local_ms)} ms${own?'':` · Shared from ${esc(ownerOf(op.id)?.name)}`}</small></span><div class="sequence-controls">${buttons}</div></li>`;
  }).join('')+dropGap(tid,t.operations.length,'li');
  $('arrange-undo').disabled=!state.undo.length;$('arrange-redo').disabled=!state.redo.length;
}
function openArrange(tid){renderArrange(tid);moveFeedback('');$('arrange-dialog').showModal();$('arrange-list').querySelector('[data-sequence-node]')?.focus();}
function describeArrangeStep(oid){
  const t=state.timelines.find(t=>t.id===arrangeTimeline),at=t?.operations.findIndex(o=>o.id===oid);
  if(at==null||at<0)return moveFeedback('This step is shared. Edit it in the parent, or make an independent copy.');
  const reasons=[[-1,'Earlier'],[1,'Later']].map(([delta,label])=>{const p=previewMove(state.timelines,t.id,oid,at+delta,state.catalog);return `${label}: ${p.reason}`;});
  moveFeedback(reasons.join(' '));
}

function openAdd(tid, position) {
  addTimeline = tid; const t = state.timelines.find(t=>t.id===tid);
  $('operation-kind').innerHTML = state.catalog.map(c=>`<option value="${c.kind}">${esc(c.name)}</option>`).join('');
  $('insert-position').innerHTML = Array.from({length:t.operations.length+1},(_,i)=>`<option value="${i}" ${i === (position ?? t.operations.length) ? 'selected' : ''}>${i===t.operations.length ? 'At the end' : `Before ${state.catalog.find(c=>c.kind===t.operations[i].kind).name}`}</option>`).join('');
  updateOperationOptions(); $('add-dialog').showModal();
}
function updateOperationOptions() {
  const t=state.timelines.find(t=>t.id===addTimeline),path=paths(state.timelines).get(t.id),position=path.length-t.operations.length+Number($('insert-position').value),kind=inputKind(path,position,state.catalog),previous=$('operation-kind').value;
  $('operation-kind').innerHTML=[...new Set(state.catalog.map(c=>c.category))].map(group=>`<optgroup label="${esc(group||'Operations')}">${state.catalog.filter(c=>c.category===group).map(c=>`<option value="${c.kind}" ${kind&&!c.accepts.includes(kind)?'disabled':''}>${esc(c.name)} · ${esc(c.library||'OpenCV')}${kind&&!c.accepts.includes(kind)?` — needs ${c.accepts.join('/')}`:''}</option>`).join('')}</optgroup>`).join('');
  const prior=[...$('operation-kind').options].find(o=>o.value===previous&&!o.disabled);
  if(prior)$('operation-kind').value=prior.value;else $('operation-kind').selectedIndex=[...$('operation-kind').options].findIndex(o=>!o.disabled);
  $('operation-help').dataset.input=kind||'invalid upstream sequence';updateOperationHelp();
}
function updateOperationHelp() {
  const c = state.catalog.find(c=>c.kind===$('operation-kind').value);
  $('operation-help').textContent = `${c.library||'OpenCV'} · CPU · C++ export. Input here: ${$('operation-help').dataset.input}. ${c.description} Accepts: ${c.accepts.join(', ')}.`;
}
function blobURL(blob) { return new Promise((resolve,reject)=>{ const reader=new FileReader(); reader.onload=()=>resolve(reader.result); reader.onerror=()=>reject(Error('Could not read image.')); reader.readAsDataURL(blob); }); }
async function addFiles(files) {
  if(state.uploadBusy)return notify('Wait for the current image upload to finish.');
  if(!files.length)return;
  const role=$('upload-role').value,replaceExample=state.example&&role==='train';
  const upload=beginIntake('upload'),epoch=upload.epoch,pending=[],base=replaceExample?[]:state.samples,graphs=replaceExample?[]:state.timelines;
  let skipped=0,automatic=false;clearAI();state.uploadBusy=true;$('upload').disabled=true;status('Checking the image family…');
  try {
    for (const file of files) {
      if (!['image/png','image/jpeg','image/webp'].includes(file.type)) throw Error(`${file.name}: use PNG, JPEG or WebP.`);
      if (file.size>8_000_000) throw Error(`${file.name}: the image exceeds 8 MB.`);
      const data=await blobURL(file);
      if(upload.controller.signal.aborted)return;
      if([...base,...pending].some(s=>s.data===data)){skipped++;continue;}
      if(base.length+pending.length>=12)throw Error('This family would exceed 12 images. Nothing was added.');
      const sample = {id:uid('image'),name:file.name.slice(0,200),data,split:role,labeled:false,boxes:[]};
      pending.push(sample);
    }
    if(!pending.length){status('These images are already in this family.');return;}
    const valid=await api('/api/timelines/validate',{...runBody([...base,...pending]),timelines:graphs},upload.controller.signal);
    await exposure.prepare(valid.samples);
    if (epoch !== loadEpoch) return notify('The project changed during upload. Your edits are preserved; add those images again.');
    const before=snapshot();
    state.samples=valid.samples;state.active=pending[0].id;
    if(replaceExample){for(const id of ['description','context','answers'])$(id).value='';state.questionAnswers=[];$('scale').value='0';}
    const trainingChanged=replaceExample||pending.some(s=>s.split==='train');
    if(replaceExample||!state.example){state.example=false;$('source-credit').textContent='';}clearAI(trainingChanged);
    commit(valid.timelines,`${pending.length} image${pending.length===1?'':'s'} added${skipped?` · ${skipped} duplicate${skipped===1?'':'s'} skipped`:''}.`,before);clearTimeout(autoTimer);
    if(trainingChanged||!before.samples.length){showScreen('define');if(matchMedia('(max-width:720px)').matches){$('panel-ai').tabIndex=-1;$('panel-ai').focus({preventScroll:true});$('panel-ai').scrollIntoView({block:'start'});}else $('description').focus();}else showScreen(before.screen);
    automatic=pending.some(s=>s.split==='train')&&$('auto-analysis').checked&&hasKey();
  } catch(error) { if(epoch === loadEpoch){notify(error.message);status('Upload was not added. Your existing family is unchanged.');} }
  finally{if(intake===upload){intake=null;state.uploadBusy=false;$('upload').disabled=false;}$('files').value='';}
  if(automatic)askAI(false);
}
async function loadExample(id) {
  const loading=beginIntake('example'),request = loading.epoch, example = state.examples.find(e=>e.id===id);
  if (!example) return;
  status('Loading example workspace…');
  try {
    const definitions=example.samples?.length?example.samples:[example];
    const [samples,preset] = await Promise.all([Promise.all(definitions.map(async definition=>{
      const response=await fetch(definition.path,{signal:loading.controller.signal});
      if(!response.ok)throw Error(`Example image could not be loaded: ${definition.filename}`);
      return {id:definition.id,name:definition.name||definition.filename,data:await blobURL(await response.blob()),split:'train',labeled:definition.labeled,boxes:definition.boxes};
    })),api(`/api/timelines/presets/${id}`,undefined,loading.controller.signal)]);
    if(request!==loadEpoch)return;
    const selectedMeasurements=example.suggested_measurements||['length','width','color'];
    const valid=await api('/api/timelines/validate',{...runBody(samples),timelines:preset.timelines,measurements:{fields:selectedMeasurements,pixels_per_unit:0,unit:'mm'}},loading.controller.signal);
    await exposure.prepare(valid.samples);if(request!==loadEpoch)return;
    const before=snapshot();
    clearParameterDrafts();state.samples=valid.samples;state.questionAnswers=[];clearAI(true);state.example=true;$('answers').value='';$('scale').value='0';$('unit').value='mm';
    $('measurements').querySelectorAll('input').forEach(input=>{input.checked=selectedMeasurements.includes(input.value);});
    state.active=valid.samples[0].id; $('description').value=example.description; $('context').value=example.context;
    $('source-credit').innerHTML=example.source?`<a href="${esc(example.source)}" target="_blank" rel="noreferrer">${esc(example.credit)}</a>`:esc(example.credit);
    if (commit(valid.timelines,'Example tree loaded · ready to edit · no API call.',before)) {
      const preferred=valid.timelines.find(t=>t.id===example.recommended_timeline_id)||valid.timelines[0];
      state.selected={timeline:preferred.id,node:paths(valid.timelines).get(preferred.id).at(-1)?.id||'source'};
      resetPipelineView();
      render();showScreen('explore');if(matchMedia('(max-width:720px)').matches)revealSelectedStep();await run(true);
    }
  } catch(error) { if(request===loadEpoch) { notify(error.message); status('Could not load example.'); } }
  $('examples').value='';
}

async function askAI(suggest) {
  if (aiBusy) return;
  if(!hasKey()){showScreen('define');renderAIState();$('settings-dialog').showModal();$('api-key').focus();return;}
  let ticket;
  try {
    const body=clone(aiBody(suggest));ticket=aiSession.start(body);aiBusy=true;renderAIState();notify();
    const fingerprint=await familyFingerprint(body.samples);
    await exposure.prepare(body.samples);
    if(!aiSession.current(ticket,aiBody(suggest,false)))return;
    exposure.markSubmitted(body.samples);renderFlow();
    if (suggest) {
      const draft=await api('/api/timelines/suggest',body,ticket.signal);
      if(!aiSession.current(ticket,aiBody(true,false)))return;
      state.draft=draft;state.draftKey=JSON.stringify(body);renderDraft();status('Approaches are ready to review and test.');
    } else {
      const result=await api('/api/analyze',body,ticket.signal);
      if(!aiSession.current(ticket,aiBody(false,false)))return;
      if(typeof result.observations!=='string'||!['important_features','questions','limitations'].every(k=>Array.isArray(result[k])&&result[k].every(v=>typeof v==='string')))throw Error('The AI returned an incomplete analysis. Your images are safe; try again.');
      state.discovery=readGuidance({answers:state.questionAnswers,discovery:{...result,imageCount:body.samples.filter(s=>s.split==='train').length,familyFingerprint:fingerprint}}).discovery;
      renderDiscovery();
      status('Family inspected. Answer the questions and describe your target.');
    }
  } catch(error) { if(error.name!=='AbortError'&&(!ticket||ticket.revision===aiSession.revision))notify(error.message); }
  finally {if(!ticket||ticket.revision===aiSession.revision){aiBusy=false;renderAIState();}}
}
function renderDraft() {
  const draft=state.draft; if (!draft) return;
  $('suggestions').innerHTML=`<h3>Proposed approaches</h3><p>${esc(draft.summary)}</p>${draft.timelines.map(t=>`<div class="draft"><h3>${esc(t.name)}</h3><p>${esc(t.rationale)}</p><p class="help">${t.parent_id?'Shared prefix → ':''}${t.operations.map(o=>esc(state.catalog.find(c=>c.kind===o.kind)?.name||o.kind)).join(' → ')}</p></div>`).join('')}<button id="accept-draft" class="primary full">${state.timelines.length?'Add and test these alternatives':'Test these approaches →'}</button>${state.timelines.length?'<button id="replace-draft" class="full">Replace current approaches</button>':''}${draft.limitations.map(l=>`<p class="help">${esc(l)}</p>`).join('')}`;
  function accept(replace) {
    try {
      if(state.draftKey!==JSON.stringify(aiBody(true,false)))throw Error('The image family or task changed. Generate approaches again for the current project.');
      const timelines=remapDraft(draft.timelines);
      if(commit(replace?timelines:[...state.timelines,...timelines])){state.draft=null;$('suggestions').textContent='Approaches added. Compare the outputs, then edit any step.';state.selected={timeline:timelines[0].id,node:'source'};showScreen('explore');run(true);}
    } catch(error) { notify(error.message); }
  }
  $('accept-draft').addEventListener('click',()=>accept(false)); $('replace-draft')?.addEventListener('click',()=>accept(true));
}
function saveWorkspace() {
  if(parameterDrafts.size){const id=[...parameterDrafts.entries.keys()][0];select(ownerOf(id).id,id);return notify('Apply or reset pending parameters before saving the project.');}
  const body={version:1,...runBody(),selected:state.selected,description:$('description').value,context:$('context').value,answers:$('answers').value,guidance:{answers:state.questionAnswers,discovery:state.discovery},ai_exposure:exposure.save()};
  const url=URL.createObjectURL(new Blob([JSON.stringify(body,null,2)],{type:'application/json'})), a=document.createElement('a');
  a.href=url; a.download='contour-workspace.json'; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
  status('Workspace saved with images and operations. API keys are excluded.');
}
async function loadWorkspace(file) {
  if (!file) return;
  const loading=beginIntake('open'),epoch=loading.epoch,expectedRevision=projectRevision;
  try {
    if (file.size>60_000_000) throw Error('Workspace file exceeds 60 MB.');
    const body=JSON.parse(await file.text()); if (body.version!==1) throw Error('Unsupported workspace version.');
    const valid=await api('/api/timelines/validate',{samples:body.samples,timelines:body.timelines,hardware:body.hardware,measurements:body.measurements},loading.controller.signal);
    const guidance=readGuidance(body.guidance);
    for(const name of ['description','context','answers'])if(body[name]!=null&&(typeof body[name]!=='string'||body[name].length>1000000))throw Error(`The saved ${name} is invalid. The current project is unchanged.`);
    if(guidance.discovery&&guidance.discovery.familyFingerprint!==await familyFingerprint(valid.samples))guidance.discovery=null;
    await exposure.prepare(valid.samples);
    if(epoch!==loadEpoch||expectedRevision!==projectRevision) return notify('The project changed while this file was opening. Your newer edits are preserved; open the file again when ready.');
    paths(valid.timelines);
    exposure.merge(body.ai_exposure,valid.samples);
    const before=snapshot();state.samples=valid.samples; state.active=valid.samples[0].id;
    for (const name of ['description','context','answers']) $(name).value=typeof body[name]==='string'?body[name]:'';
    const h=valid.hardware;
    for (const [id,key] of Object.entries({'hardware-mode':'mode','cpu-name':'cpu_name','architecture':'architecture','host-ghz':'host_ghz','target-ghz':'target_ghz','relative-speed':'relative_speed','reference-local':'reference_local_ms','reference-target':'reference_target_ms','budget':'budget_ms'})) $(id).value=h[key]??'';
    $('measurements').querySelectorAll('input').forEach(i=>{i.checked=valid.measurements.fields.includes(i.value);});
    $('scale').value=valid.measurements.pixels_per_unit; $('unit').value=valid.measurements.unit; showHardwareFields();
    $('source-credit').textContent='';clearParameterDrafts();clearAI(true);state.questionAnswers=guidance.answers;state.discovery=guidance.discovery;renderDiscovery();state.example=false;
    if(commit(valid.timelines,'Project opened.',before)){
      state.selected=savedSelection(valid.timelines,body.selected,body.recommended_timeline_id);resetPipelineView();render();showScreen(valid.timelines.length?'explore':'define');if(matchMedia('(max-width:720px)').matches)revealSelectedStep();
    }
  } catch(error) { if(epoch===loadEpoch) notify(error.message); }
  if(intake===loading)intake=null;$('workspace-file').value='';
}
function showHardwareFields() { document.querySelectorAll('[data-hardware]').forEach(el=>{el.hidden=el.dataset.hardware!==$('hardware-mode').value;}); }

document.addEventListener('click',e=>{const link=e.target.closest('[data-focus-pipeline]');if(link)focusPipeline(link.dataset.focusPipeline,link.dataset.focusStep);});
$('pipeline-mobile-select').addEventListener('change',e=>focusPipeline(e.target.value));
$('view-focus').addEventListener('click',()=>{pipelineView='focus';renderTimelines();});
$('view-compare').addEventListener('click',()=>{
  pipelineView='compare';const active=selectedTimeline();if(active){if(!comparedPipelines.has(active.id)&&comparedPipelines.size>=3)comparedPipelines.delete([...comparedPipelines].at(-1));comparedPipelines.add(active.id);const refs=paths(state.timelines).get(active.id).flatMap(supportingIds);const other=refs[0]||active.parent_id||state.timelines.find(t=>t.id!==active.id)?.id;if(comparedPipelines.size<2&&other)comparedPipelines.add(other);}
  renderTimelines();
});
$('choose-comparisons').addEventListener('click',()=>{const open=$('choose-comparisons').getAttribute('aria-expanded')!=='true';$('choose-comparisons').setAttribute('aria-expanded',String(open));document.querySelector('.pipeline-layout').classList.toggle('choosing-comparisons',open);});
$('outline-list').addEventListener('change',e=>{const id=e.target.dataset.comparePipeline;if(!id)return;if(e.target.checked){if(comparedPipelines.size>=3){e.target.checked=false;return notify('Compare up to 3 pipelines at once. Uncheck one to choose another.');}comparedPipelines.add(id);}else comparedPipelines.delete(id);renderTimelines();});
$('timelines').addEventListener('scroll',e=>{if(e.target.dataset.nodeRow)pipelineScrolls.set(e.target.dataset.nodeRow,e.target.scrollLeft);},true);
$('timelines').addEventListener('click',e=>{
  const node=e.target.closest('[data-node]'),add=e.target.closest('[data-add]'),title=e.target.closest('[data-select-timeline]'),arrange=e.target.closest('[data-arrange]'),mover=e.target.closest('[data-move-op]'),prefix=e.target.closest('[data-prefix]');
  if(prefix){const tid=prefix.dataset.prefix;expandedPrefixes.has(tid)?expandedPrefixes.delete(tid):expandedPrefixes.add(tid);renderTimelines();document.querySelector(`[data-prefix="${CSS.escape(tid)}"]`)?.focus({preventScroll:true});}
  else if(mover)move(mover.dataset.moveTimeline,mover.dataset.moveOp,Number(mover.dataset.moveTo));else if(arrange)openArrange(arrange.dataset.arrange);else if(node)select(node.dataset.timeline,node.dataset.node);else if(add)openAdd(add.dataset.add);else if(title)select(title.dataset.selectTimeline);
});
$('comparison').addEventListener('click',e=>{const b=e.target.closest('[data-result]');if(b)select(b.dataset.result,b.dataset.end);});
$('comparison').addEventListener('toggle',e=>{if(e.target.parentElement===$('comparison'))state.compareOpen=e.target.open;else if(e.target.classList.contains('collection-details'))state.collectionOpen=e.target.open;},true);
const labelEditor=createLabelEditor((id,boxes,labeled,imageData,baseline)=>{
  const sample=state.samples.find(s=>s.id===id);
  if(!sample||sample.data!==imageData)throw Error('This image changed while you were labeling it. Close this dialog and open the current image.');
  if(JSON.stringify([sample.boxes,sample.labeled])!==baseline)throw Error('The saved labels changed while this dialog was open. Close it and review the current labels before editing.');
  if(JSON.stringify(sample.boxes)===JSON.stringify(boxes)&&sample.labeled===labeled)return;
  state.undo.push(snapshot());if(state.undo.length>20)state.undo.shift();state.redo=[];sample.boxes=boxes;sample.labeled=labeled;
  projectRevision++;stopIntake();clearAI(sample.split==='train');
  revision.bump();stopRun();state.results.delete(id);executionErrors.delete(id);state.active=id;render();run();
});
$('open-ai').addEventListener('click',()=>showTab('ai'));$('open-hardware').addEventListener('click',()=>showTab('hardware'));
for(const name of ['images','inspector'])$(`toggle-${name}`).addEventListener('click',()=>panel(name,!document.body.classList.contains(`show-${name}`)));
$('close-inspector').addEventListener('click',()=>{panel('inspector',false);document.querySelector(`.node[data-timeline="${CSS.escape(state.selected?.timeline||'')}"][data-node="${CSS.escape(state.selected?.node||'')}"]`)?.focus({preventScroll:true});});
$('pending-parameters').addEventListener('click',e=>{
  const review=e.target.closest('[data-review-parameters]');
  if(review)select(ownerOf(review.dataset.reviewParameters).id,review.dataset.reviewParameters);
  else if(e.target.closest('[data-discard-parameters]')){clearParameterDrafts();renderInspector();renderParameterState();}
});
$('inspector').addEventListener('click',e=>{if(e.target.closest('[data-reset-parameters]')){parameterDrafts.delete(selectedOperation()?.id);$('inspector').dataset.parameterKey='';renderInspector();$('params-form [data-param]')?.focus({preventScroll:true});}});
function clearDrag(){drag=null;document.body.classList.remove('dragging-step');document.querySelectorAll('.drop-target,.drop-blocked').forEach(el=>el.classList.remove('drop-target','drop-blocked'));}
for(const container of [$('timelines'),$('arrange-list')]){
  container.addEventListener('dragstart',e=>{
    const node=e.target.closest('[data-node],[data-sequence-node]');if(!node||!node.draggable)return e.preventDefault();
    drag={timeline:node.dataset.timeline||node.dataset.sequenceTimeline,node:node.dataset.node||node.dataset.sequenceNode};e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain',drag.node);document.body.classList.add('dragging-step');moveFeedback('Drop into a highlighted gap. Incompatible moves are blocked.');
  });
  container.addEventListener('dragover',e=>{
    const gap=e.target.closest('[data-drop-gap]');if(!drag||!gap||gap.dataset.dropTimeline!==drag.timeline)return;
    e.preventDefault();const t=state.timelines.find(t=>t.id===drag.timeline),index=gapIndex(t.operations.findIndex(o=>o.id===drag.node),Number(gap.dataset.dropGap)),proposal=previewMove(state.timelines,drag.timeline,drag.node,index,state.catalog);
    document.querySelectorAll('.drop-target,.drop-blocked').forEach(el=>el.classList.remove('drop-target','drop-blocked'));
    e.dataTransfer.dropEffect=proposal.allowed?'move':'none';gap.classList.add(proposal.allowed?'drop-target':'drop-blocked');moveFeedback(proposal.reason,!proposal.allowed);
  });
  container.addEventListener('dragleave',e=>e.target.closest('[data-drop-gap]')?.classList.remove('drop-target','drop-blocked'));
  container.addEventListener('dragend',clearDrag);
  container.addEventListener('drop',e=>{e.preventDefault();const gap=e.target.closest('[data-drop-gap]');if(drag&&gap?.dataset.dropTimeline===drag.timeline){const t=state.timelines.find(t=>t.id===drag.timeline);move(drag.timeline,drag.node,gapIndex(t.operations.findIndex(o=>o.id===drag.node),Number(gap.dataset.dropGap)));}clearDrag();});
}
$('arrange-list').addEventListener('click',e=>{const b=e.target.closest('[data-move-op]');if(b)move(b.dataset.moveTimeline,b.dataset.moveOp,Number(b.dataset.moveTo));});
$('arrange-list').addEventListener('focusin',e=>{const row=e.target.closest('[data-sequence-node]');if(row)describeArrangeStep(row.dataset.sequenceNode);});
for(const id of ['close-arrange','done-arrange'])$(id).addEventListener('click',()=>{$('arrange-dialog').close();clearDrag();});
$('arrange-undo').addEventListener('click',()=>{undo();renderArrange(arrangeTimeline);});$('arrange-redo').addEventListener('click',()=>{undo(true);renderArrange(arrangeTimeline);});
$('arrange-copy').addEventListener('click',()=>{try{const copy=independentCopy(state.timelines,arrangeTimeline);if(commit(copy.timelines,'Independent approach created.')){state.selected={timeline:copy.id,node:'source'};renderArrange(copy.id);}}catch(error){moveFeedback(error.message,true);}});
document.addEventListener('keydown',e=>{
  if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z'&&!e.target.matches('input,textarea,select,[contenteditable=true]')&&(!document.querySelector('dialog[open]')||$('arrange-dialog').open)){
    e.preventDefault();undo(e.shiftKey);if($('arrange-dialog').open)renderArrange(arrangeTimeline);return;
  }
  if(!e.altKey||!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))return;
  const node=e.target.closest('[data-node],[data-sequence-node]');if(!node)return;
  const tid=node.dataset.timeline||node.dataset.sequenceTimeline,oid=node.dataset.node||node.dataset.sequenceNode,t=state.timelines.find(t=>t.id===tid),index=t.operations.findIndex(o=>o.id===oid);
  if(index<0)return;e.preventDefault();move(tid,oid,index+(['ArrowLeft','ArrowUp'].includes(e.key)?-1:1));
});
$('samples').addEventListener('click',e=>{
  const image=e.target.closest('[data-image]'), remove=e.target.closest('[data-remove-image]');
  if (image) { state.active=image.dataset.image; render(); if (!activeRun&&state.timelines.length&&!currentResult()) run(); }
  if (remove) { const before=snapshot(),removed=state.samples.find(s=>s.id===remove.dataset.removeImage);state.samples=state.samples.filter(s=>s.id!==remove.dataset.removeImage);if(!state.samples.some(s=>s.id===state.active))state.active=state.samples[0]?.id;clearAI(removed?.split==='train');commit(state.timelines,'Image removed.',before);if(!state.samples.length)showScreen('images'); }
});
$('samples').addEventListener('change',e=>{ if(e.target.dataset.split) { const before=snapshot(),sample=state.samples.find(s=>s.id===e.target.dataset.split);sample.split=e.target.value;clearAI(true);commit(state.timelines,'Image role updated.',before);if(sample.split==='validation'&&exposure.status(sample)!=='unseen')notify('This image has AI or local optimization history, or unknown history. It is counted separately from held-out validation.'); } });
$('upload').addEventListener('click',()=>$('files').click()); $('files').addEventListener('change',e=>addFiles(e.target.files));
$('upload').addEventListener('dragover',e=>{e.preventDefault();$('upload').classList.add('drag-over');});$('upload').addEventListener('dragleave',()=>$('upload').classList.remove('drag-over')); $('upload').addEventListener('drop',e=>{e.preventDefault();$('upload').classList.remove('drag-over');addFiles(e.dataTransfer.files);});
$('examples').addEventListener('change',e=>loadExample(e.target.value));
for (const id of ['description','context','answers','question-fields','model']) $(id).addEventListener('input',e=>{
  recordFieldEdit(e.target);
  if(intake?.kind==='open'){stopIntake();notify('Project opening cancelled because you edited the current project. Your newer edits are preserved.');}
  projectRevision++;
  if(e.target.dataset.question)state.questionAnswers=updateAnswer(state.questionAnswers,e.target.dataset.question,e.target.value);
  clearAI();renderAnswerBudget();
});
$('run').addEventListener('click',()=>run()); $('run-all').addEventListener('click',()=>run(true));
$('auto-run').addEventListener('change',()=>{clearTimeout(autoTimer);if($('auto-run').checked&&!activeRun)run();});
$('cancel-run').addEventListener('click',()=>{stopRun(true);renderFinish();});$('continue-run').addEventListener('click',()=>run(true,true));
$('undo').addEventListener('click',()=>undo()); $('redo').addEventListener('click',()=>undo(true));
$('new-timeline').addEventListener('click',()=>{ const t={id:uid('timeline'),name:'New timeline',parent_id:null,fork_after:null,rationale:'',operations:[operation('resize')]}; if(edit(next=>next.push(t)))select(t.id,t.operations[0].id); });
document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>showTab(b.dataset.tab)));
$('close-add').addEventListener('click',()=>$('add-dialog').close()); $('operation-kind').addEventListener('change',updateOperationHelp);
$('insert-position').addEventListener('change',updateOperationOptions);
$('add-form').addEventListener('submit',e=>{e.preventDefault(); const op=operation($('operation-kind').value); if(edit(next=>next.find(t=>t.id===addTimeline).operations.splice(Number($('insert-position').value),0,op))) { $('add-dialog').close(); select(addTimeline,op.id); }});
function hardwareEdited(e){recordFieldEdit(e.target);projectRevision++;stopIntake();clearOptimization();if(state.draft||aiBusy)clearAI();showHardwareFields();refreshEstimates();renderTimelines();renderComparison();renderInspector();renderFinish();status('Target estimates updated · image results reused.');}
$('panel-hardware').addEventListener('change',hardwareEdited);
$('panel-hardware').addEventListener('input',hardwareEdited);
for (const id of ['measurements','scale','unit']) $(id).addEventListener('change',e=>{recordFieldEdit(e.target);projectRevision++;clearAI();invalidate();});
$('analyze').addEventListener('click',()=>askAI(false)); $('suggest').addEventListener('click',()=>askAI(true));
$('save').addEventListener('click',saveWorkspace); $('load').addEventListener('click',()=>$('workspace-file').click()); $('workspace-file').addEventListener('change',e=>loadWorkspace(e.target.files[0]));

$('continue-analysis').addEventListener('click',()=>showScreen('define'));$('back-images').addEventListener('click',()=>showScreen('images'));
$('open-explore').addEventListener('click',()=>showScreen('explore'));$('open-finish').addEventListener('click',()=>showScreen('finish'));
$('to-finish').addEventListener('click',()=>showScreen('finish'));$('back-editor').addEventListener('click',()=>showScreen('explore'));$('edit-brief').addEventListener('click',()=>showScreen('define'));
$('open-settings').addEventListener('click',()=>$('settings-dialog').showModal());$('close-settings').addEventListener('click',()=>$('settings-dialog').close());
$('family-ai-state').addEventListener('click',e=>{if(e.target.closest('[data-connect-key]')){$('settings-dialog').showModal();$('api-key').focus();}else if(e.target.closest('[data-set-target]')){$('description').focus({preventScroll:true});$('description').scrollIntoView({block:'center'});}});
$('use-settings').addEventListener('click',async()=>{
  try{
    const key=$('api-key').value.trim(),remember=$('remember-key').checked;
    if(!state.publicMode&&(key||state.localKeySaved&&!remember)){
      const saved=await api('/api/local-settings',{key,remember});state.serverKey=saved.server_key;state.localKeySaved=saved.local_key_saved;
      if(saved.local_key_saved){$('api-key').value='';$('api-key').placeholder='Saved locally · used automatically';$('key-help').textContent='Saved on this computer. Never included in a project or C++ export.';}
    }
    $('settings-dialog').close();clearAI();if(state.samples.some(s=>s.split==='train')&&hasKey()&&!state.discovery){showScreen('define');askAI(false);}
  }catch(error){notify(error.message);}
});
$('cancel-ai').addEventListener('click',()=>{clearAI();status('AI request cancelled. Your images and edits are unchanged.');});
$('close-hardware').addEventListener('click',()=>$('hardware-dialog').close());$('export-hardware').addEventListener('click',()=>showTab('hardware'));
$('manual-start').addEventListener('click',()=>{const t={id:uid('timeline'),name:'My approach',parent_id:null,fork_after:null,rationale:'Manual pipeline. Add a transform to reveal your target.',operations:[operation('resize')]};if(edit(next=>next.push(t))){select(t.id,t.operations[0].id);run();}});
for(const id of ['preview-image','validation-image'])$(id).addEventListener('change',e=>{state.active=e.target.value;render();if(!activeRun&&state.timelines.length&&!currentResult())run();});
$('family-preview').addEventListener('click',e=>{const b=e.target.closest('[data-family-image]');if(b){state.active=b.dataset.familyImage;render();}});
$('export-choice').addEventListener('change',()=>{
  const timeline=$('export-choice').value,path=paths(state.timelines).get(timeline);
  if(path){state.selected={timeline,node:path.at(-1)?.id||'source'};pipelineSelections.set(timeline,state.selected.node);renderTimelines();renderInspector();}
  renderFinish();
});$('validate-family').addEventListener('click',()=>run(true));$('export-chosen').addEventListener('click',()=>exportSelected($('export-choice').value));
$('validation-review').addEventListener('change',e=>{if(e.target.id==='review-stage')renderValidationReview($('export-choice').value);});
$('validation-review').addEventListener('click',e=>{
  const image=e.target.closest('[data-review-image]'),label=e.target.closest('[data-review-label]'),rerun=e.target.closest('[data-review-run]'),step=e.target.closest('[data-review-step]');
  if(image){state.active=image.dataset.reviewImage;render();}
  else if(label){const sample=state.samples.find(s=>s.id===state.active);if(sample){if(intake?.kind==='open')stopIntake();labelEditor.open(sample);};}
  else if(rerun)run();else if(step)select($('export-choice').value,step.dataset.reviewStep);
});
$('new-project').addEventListener('click',()=>{if(state.samples.length)$('new-dialog').showModal();else showScreen('images');});$('cancel-new').addEventListener('click',()=>$('new-dialog').close());
$('confirm-new').addEventListener('click',()=>{projectRevision++;stopIntake();state.questionAnswers=[];clearAI(true);revision.bump();stopRun();clearTimeout(autoTimer);state.samples=[];state.timelines=[];state.results.clear();executionErrors.clear();state.active=null;state.selected=null;state.undo=[];state.redo=[];state.example=false;for(const id of ['description','context','answers'])$(id).value='';$('measurements').querySelectorAll('input').forEach(i=>i.checked=i.defaultChecked);$('scale').value='0';$('unit').value='mm';$('upload-role').value='train';$('source-credit').textContent='';$('new-dialog').close();showScreen('images');render();status('New image family. Add your images to begin.');notify();});

document.addEventListener('focusin',e=>{
  const tracked=['description','context','answers','scale','unit',...Object.keys(hardwareFields)];
  if(tracked.includes(e.target.id)||e.target.matches('[data-question],#measurements input'))fieldEdit={element:e.target,before:snapshot(),recorded:false};
});
document.addEventListener('focusout',e=>{if(fieldEdit?.element===e.target)fieldEdit=null;});

async function init() {
  try {
    const sizeWorkspace=()=>{const root=document.documentElement;root.style.setProperty('--header-height',`${document.querySelector('.topbar').getBoundingClientRect().height}px`);root.style.setProperty('--editor-top',`${document.querySelector('.topbar').offsetHeight+document.querySelector('.project-status').offsetHeight+document.querySelector('.editor-context').offsetHeight+$('notice').offsetHeight+$('pending-parameters').offsetHeight}px`);}; const layoutObserver=new ResizeObserver(sizeWorkspace);for(const selector of ['.topbar','.project-status','.editor-context','#notice','#pending-parameters'])layoutObserver.observe(document.querySelector(selector));
    const [catalog,examples,health]=await Promise.all([api('/api/timelines/catalog'),api('/api/examples'),api('/api/health')]);
    state.catalog=catalog.operations; state.examples=examples;
    state.serverKey=health.server_key;state.localKeySaved=Boolean(health.local_key_saved);state.publicMode=health.local_key_storage===false;$('remember-key').disabled=state.publicMode;$('remember-key').checked=!state.publicMode;if(state.publicMode)$('local-key-help').textContent='Public mode: use your own key for this page only. Local server keys are disabled.';if(state.localKeySaved)$('api-key').placeholder='Saved locally · used automatically';
    if(state.publicMode){
      $('processing-note').textContent='Images are processed by this server. AI analysis also sends training images to OpenAI when you connect a key. Save a project to keep your work.';
      $('local-key-help').textContent='Your key stays in this page until it closes. AI requests pass it through this server to OpenAI. It is not saved on the server.';
      $('remember-key').closest('label').hidden=true;
      $('cpu-name').value='Processing server';
      $('hardware-mode').querySelector('[value="local"]').textContent='Processing server · measured';
      document.querySelector('label[for="host-ghz"]').textContent='Server CPU nominal GHz';
      document.querySelector('label[for="relative-speed"]').textContent='Target single-thread speed ÷ server speed';
      $('timing-note').textContent='Measured on the processing server · one CPU thread · median of 5 warm runs. Image decoding, network transfer and previews are excluded.';
    }
    $('host-info').textContent=`${state.publicMode?'Processing server':'This computer'}: ${catalog.host.cpu_name}. OpenCV ${catalog.host.opencv}, one CPU thread.`;
    $('host-ghz').value=catalog.host.nominal_ghz??'';
    if (health.server_key) $('key-help').textContent='A server API key is available. An entered key overrides it for this page.';
    const exampleGroups=[...new Set(examples.map(e=>e.category||'Technique examples'))].sort((a,b)=>Number(b.startsWith('Object tests'))-Number(a.startsWith('Object tests'))||a.localeCompare(b));
    $('examples').innerHTML='<option value="">Choose an object to detect…</option>'+exampleGroups.map(group=>`<optgroup label="${esc(group)}">${examples.filter(e=>(e.category||'Technique examples')===group).map(e=>`<option value="${esc(e.id)}">${esc(e.title)}</option>`).join('')}</optgroup>`).join('');
    const objectTests=examples.filter(e=>e.collection==='object-tests').length;
    if(objectTests)$('example-library-note').textContent=`${objectTests} object tests, each with 3 labeled images and editable branches. Choosing one runs all images ${state.publicMode?'on the server':'on this computer'}. No API key needed. Photo variations and generated 2D cases are teaching examples.`;
    render();showScreen('images');status('Add an image family to begin.');
  } catch(error) { notify(error.message); status('Could not connect to Contour. Refresh to try again.'); }
}
init();

function branchFrom(pipelineId,node){
  const t=state.timelines.find(t=>t.id===pipelineId);if(!t)return;
  const id=uid('pipeline');
  if(edit(next=>next.push({id,name:`${t.name.slice(0,70)} · branch`,parent_id:t.id,fork_after:node,rationale:'Alternative method from this shared input.',operations:[]})))select(id,'source');
}
document.addEventListener('click',e=>{const button=e.target.closest('[data-fork-node]');if(button)branchFrom(button.dataset.forkPipeline,button.dataset.forkNode);});
function confirmationCandidates(){const graph=paths(state.timelines);return state.timelines.filter(t=>state.catalog.find(c=>c.kind===graph.get(t.id).at(-1)?.kind)?.detector);}
function updateConfirmationSupport(){
  const primary=$('confirm-primary').value;
  const graph=paths(state.timelines),seen=new Set([graph.get(primary)?.at(-1)?.id]);
  $('confirm-support').innerHTML=confirmationCandidates().filter(t=>{const id=graph.get(t.id).at(-1)?.id;if(seen.has(id))return false;seen.add(id);return true;}).map(t=>`<option value="${esc(t.id)}">${esc(t.name)}</option>`).join('');
}
$('confirm-branches').addEventListener('click',()=>{
  const choices=confirmationCandidates();
  if(choices.length<2)return notify('Finish at least two pipelines with a detector, then confirm their results. Use Branch on a selected step to build another method.');
  $('confirm-error').textContent='';$('confirm-primary').innerHTML=choices.map(t=>`<option value="${esc(t.id)}" ${t.id===state.selected?.timeline?'selected':''}>${esc(t.name)}</option>`).join('');
  updateConfirmationSupport();$('confirm-dialog').showModal();
});
$('confirm-primary').addEventListener('change',updateConfirmationSupport);
$('close-confirm').addEventListener('click',()=>$('confirm-dialog').close());
$('confirm-form').addEventListener('submit',e=>{
  e.preventDefault();const primary=$('confirm-primary').value,support=$('confirm-support').value;
  if(!primary||!support||primary===support){$('confirm-error').textContent='Choose two distinct detector pipelines.';return;}
  const source=state.timelines.find(t=>t.id===primary),last=paths(state.timelines).get(primary)?.at(-1);
  if(!last)return;
  const id=uid('pipeline'),node=operation('confirm');node.params={...node.params,pipeline_ids:support,iou:Number($('confirm-iou').value)};
  if(edit(next=>next.push({id,name:`${source.name.slice(0,65)} · confirmed`,parent_id:primary,fork_after:last.id,rationale:'Primary objects retained only when the supporting method agrees.',operations:[node]}))){$('confirm-dialog').close();select(id,node.id);run();}
});

optimizationUI=createOptimizationUI({
  getInput:()=>({...runBody(),selected_timeline_id:state.selected?.timeline,name:selectedTimeline()?.name,brief:{description:$('description').value,context:$('context').value,answers:formatAnswers(state.questionAnswers,$('answers').value),model:$('model').value.trim()}}),
  hasKey,hasDrafts:()=>parameterDrafts.size>0,catalog:()=>state.catalog,api,
  prepare:samples=>exposure.prepare(samples),
  markTuned:samples=>{exposure.markTuned(samples);renderFlow();},
  markSubmitted:samples=>{exposure.markSubmitted(samples);renderFlow();},
  beforeStart:()=>{stopRun();clearTimeout(autoTimer);if(aiBusy)clearAI();},
  apply:candidate=>{
    const originalIndex=candidate.timelines.findIndex(t=>t.id===candidate.selected_timeline_id),graphs=remapDraft(candidate.timelines);
    const usedNames=new Set(state.timelines.map(t=>t.name)),resolved=paths(graphs);
    graphs.forEach((graph,index)=>{
      const last=resolved.get(graph.id).at(-1),metadata=state.catalog.find(c=>c.kind===last?.kind);
      const base=index===originalIndex?`${selectedTimeline().name} · optimized`:metadata?.detector?`${graph.name} · supporting method`:`${metadata?.name||'Source'} input · optimized`;
      let name=base.slice(0,100),number=2;while(usedNames.has(name))name=`${base.slice(0,92)} (${number++})`;
      graph.name=name;usedNames.add(name);
      if(index!==originalIndex&&!metadata?.detector)graph.rationale='Shared input copied for this optimized alternative. Edit its steps to change the dependent branch.';
    });
    const next=[...state.timelines,...graphs];paths(next);
    if(!commit(next,'Optimization added as an alternative. Validate on fresh images.'))throw Error($('notice').textContent);
    focusPipeline(graphs[originalIndex].id);run(true);
  }
});

const narrowMenus=matchMedia("(max-width:720px)");
function syncMenus(){document.querySelectorAll(".project-menu,.context-menu").forEach(menu=>menu.open=!narrowMenus.matches);}
function closeMobileMenus(except){
  if(!matchMedia('(max-width:720px)').matches)return;
  document.querySelectorAll('.project-menu,.context-menu').forEach(menu=>{if(menu!==except)menu.open=false;});
}
syncMenus();narrowMenus.addEventListener("change",syncMenus);
document.addEventListener('click',event=>{
  const menu=event.target.closest('.project-menu,.context-menu');
  if(!menu||event.target.closest('button'))closeMobileMenus();
  else closeMobileMenus(menu);
});
document.addEventListener('keydown',event=>{
  if(event.key!=='Escape'||document.querySelector('dialog[open]'))return;
  const menu=document.activeElement?.closest('.project-menu[open],.context-menu[open]');
  closeMobileMenus();
  if(menu&&narrowMenus.matches)menu.querySelector('summary').focus();
  else if(document.body.classList.contains('show-inspector')){panel('inspector',false);$('toggle-inspector').focus();}
});
