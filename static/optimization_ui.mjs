import {AISession} from './ai_session.mjs';
import {paths,formatMs} from './workflow.mjs';

export function createOptimizationUI({getInput,hasKey,hasDrafts,catalog,api,prepare,markTuned,markSubmitted,beforeStart,apply}){
  const $=id=>document.getElementById(id),session=new AISession();
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let busy=false,result=null,ticket=null;
  const input=()=>({...getInput(),useAI:$('optimization-ai').checked,max_trials:Number($('optimization-trials').value),budget_seconds:Number($('optimization-budget').value)});
  function controls(){
    if(!hasKey())$('optimization-ai').checked=false;
    $('start-optimization').disabled=busy;$('cancel-optimization').hidden=!busy;
    for(const id of ['optimization-trials','optimization-budget'])$(id).disabled=busy;
    $('optimization-ai').disabled=busy||!hasKey();
  }
  function clear(message=''){
    session.cancel();busy=false;result=null;ticket=null;
    $('optimization-results').textContent='';$('optimization-status').textContent=message;controls();
  }
  function render(){
    if(!result)return;
    const recommendations=result.candidates.filter(c=>c.recommended).length;
    $('optimization-results').innerHTML=`<p class="optimization-outcome">${recommendations?`${recommendations} alternative${recommendations===1?"":"s"} improved the training checks or showed a clear speed gain.`:"No clear improvement found in this search. The current pipeline remains the baseline."}</p><p class="optimization-summary">${result.evaluated} candidates evaluated · ${(result.wall_ms/1000).toFixed(2)} s · ${result.cache_hits} reused steps · ${esc(result.stopped)}</p><p class="help">Finalist timings are fresh CPU measurements. ${result.timing_incomplete?'Timing budget ended; incomplete timings stay unknown.':''}</p><div class="optimization-cards">${result.candidates.map((c,index)=>`<article class="optimization-card ${c.baseline?'baseline':''}"><div class="section-heading"><strong>${c.baseline?'Current pipeline':c.recommended?'Recommended alternative':'Measured alternative'}</strong><span class="badge">${c.baseline?'Preserved':'Box checks passed'}</span></div>${c.preview?`<img src="${esc(c.preview)}" alt="${esc(c.name)} output on first training image">`:'<p class="help">Run this candidate to inspect its output.</p>'}<p><strong>F1 ${c.metrics.f1==null?'—':c.metrics.f1.toFixed(3)}</strong> · ${c.metrics.tp} matched / ${c.metrics.fp} extra / ${c.metrics.fn} missed<br>${formatMs(c.local_ms)} ms CPU median</p><details><summary>Changes &amp; image results</summary><ul>${c.changes.map(change=>`<li>${esc(change.proposal||`${change.operation}: ${change.parameter} → ${change.value}`)}</li>`).join('')||'<li>Unchanged baseline</li>'}</ul>${c.per_image.map(row=>`<p class="help">${esc(row.name)}: ${row.tp} matched, ${row.fp} extra, ${row.fn} missed · overlap ${row.mean_iou==null?'—':row.mean_iou.toFixed(3)}</p>`).join('')}${c.measurement_method_changed?'<p class="notice">Measurement method changed. Check dimensions and masks independently.</p>':''}</details>${c.baseline?'':`<button class="primary full" data-apply-optimization="${index}" aria-label="Add ${esc(c.name)} as an alternative">Add as alternative</button>`}</article>`).join('')}</div><p class="help">${result.limitations.map(esc).join(' ')}</p><details><summary>Search and timing details</summary><p class="help">${esc(result.timing_note)} ${result.executed_nodes} native node executions during screening; ${(result.cache_peak_bytes/1048576).toFixed(1)} MiB peak cache. ${result.failed_or_incomplete} candidates failed or did not finish.</p></details>`;
  }
  $('open-optimizer').addEventListener('click',()=>{
    if(ticket&&!session.current(ticket,input()))clear('Selected pipeline or project changed. Run a new search.');
    const context=getInput();
    $('optimization-target').textContent=`Selected: ${context.name||'choose a pipeline'}`;
    if(!$('optimization-ai').dataset.chosen)$('optimization-ai').checked=hasKey();
    $('optimization-key-note').textContent=hasKey()?'AI proposes up to 3 structures; CPU search tests them against training labels.':'CPU optimization works without a key. Connect OpenAI in AI settings to include AI proposals.';
    if(hasDrafts())$('optimization-status').textContent='Apply or reset pending parameters before optimization.';
    controls();$('optimization-dialog').showModal();
  });
  $('optimization-ai').addEventListener('change',()=>{$('optimization-ai').dataset.chosen='true';clear('Options changed. Run search for these settings.');});
  for(const id of ['optimization-trials','optimization-budget'])$(id).addEventListener('change',()=>clear('Options changed. Run search for these settings.'));
  $('close-optimization').addEventListener('click',()=>{if(busy)clear('Search cancelled.');$('optimization-dialog').close();});
  $('optimization-dialog').addEventListener('cancel',()=>{if(busy)clear('Search cancelled.');});
  $('cancel-optimization').addEventListener('click',()=>clear('Search cancelled. The current pipeline is unchanged.'));
  $('start-optimization').addEventListener('click',async()=>{
    if(busy)return;
    let current;
    try{
      if(hasDrafts())throw Error('Apply or reset pending parameters first.');
      const frozen=structuredClone(input()),training=frozen.samples.filter(s=>s.split==='train');
      if(!training.length||training.some(s=>!s.labeled)||!training.some(s=>s.boxes.length))throw Error('Label every training image, confirm all targets are labeled, and include at least one positive image.');
      const final=paths(frozen.timelines).get(frozen.selected_timeline_id)?.at(-1);
      if(!catalog().find(c=>c.kind===final?.kind)?.detector)throw Error('End the selected pipeline with an object detector before optimization.');
      beforeStart();clear();current=session.start(frozen);ticket=current;busy=true;controls();
      await prepare(training);if(!session.current(current,input()))return;
      markTuned(training);let seeds=[],proposalNote="";
      if(frozen.useAI){
        if(frozen.brief.description.trim().length<3)throw Error('Describe the target before asking AI for alternatives.');
        $('optimization-status').textContent='AI is proposing alternatives · one API call…';markSubmitted(training);
        try{const proposal=await api('/api/timelines/suggest',{...frozen.brief,samples:training,measurements:frozen.measurements,hardware:frozen.hardware,timelines:frozen.timelines,focus_timeline_id:frozen.selected_timeline_id},current.signal);
        if(!session.current(current,input()))return;
        const graph=paths(proposal.timelines);
        seeds=proposal.timelines.filter(t=>catalog().find(c=>c.kind===graph.get(t.id).at(-1)?.kind)?.detector).slice(0,3).map(t=>({name:t.name,timelines:proposal.timelines,selected_timeline_id:t.id}));
        }catch(error){if(error.name==='AbortError')throw error;if(!session.current(current,input()))return;proposalNote=`AI proposals were unavailable (${error.message}). CPU search completed without them. `;}
      }
      $('optimization-status').textContent=`Testing up to ${frozen.max_trials} candidates on ${training.length} training images…`;
      const response=await api('/api/timelines/optimize',{samples:training,timelines:frozen.timelines,selected_timeline_id:frozen.selected_timeline_id,hardware:frozen.hardware,measurements:frozen.measurements,max_trials:frozen.max_trials,budget_seconds:frozen.budget_seconds,seeds},current.signal);
      if(!session.current(current,input()))return;
      result=response;render();$('optimization-status').textContent=proposalNote+'Search complete. Add an alternative to inspect its full pipeline, then validate on fresh images.';
    }catch(error){if(error.name!=='AbortError'&&(!current||current.revision===session.revision))$('optimization-status').textContent=error.message;}
    finally{if(!current||current.revision===session.revision){busy=false;controls();}}
  });
  $('optimization-results').addEventListener('click',event=>{
    const button=event.target.closest('[data-apply-optimization]');if(!button)return;
    try{
      if(!result||!ticket||!session.current(ticket,input()))throw Error('The project changed. Run optimization again before applying a candidate.');
      if(hasDrafts())throw Error('Apply or reset pending parameters first.');
      apply(result.candidates[Number(button.dataset.applyOptimization)]);$('optimization-dialog').close();
    }catch(error){$('optimization-status').textContent=error.message;}
  });
  document.addEventListener('input',event=>{if(!event.target.closest('#optimization-dialog')&&(busy||result))clear('Project changed. Run search again.');});
  return {clear};
}
