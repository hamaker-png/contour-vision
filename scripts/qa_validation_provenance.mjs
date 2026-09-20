// External-browser integration check with explicit provider fixtures.
import {connect} from './cdp.mjs';
import {readFile,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
const p=await connect(JSON.parse(await readFile('artifacts/strict/root-tab.json')).id);
await p.call('Page.bringToFront');
let analyses=0;const errors=[];
p.on('Fetch.requestPaused',async e=>{try{
  const health=e.request.url.endsWith('/api/health');if(!health)analyses++;
  const body=health?{ok:true,server_key:true,cpu_only:true}:{observations:'CONTROLLED FIXTURE: common silhouette.',important_features:['Outline'],questions:['What matters?'],limitations:['This tests workflow, not model quality.']};
  await p.call('Fetch.fulfillRequest',{requestId:e.requestId,responseCode:200,responseHeaders:[{name:'Content-Type',value:'application/json'}],body:Buffer.from(JSON.stringify(body)).toString('base64')});
}catch(e){errors.push(e.message);}});
try{
  await p.call('Fetch.enable',{patterns:[{urlPattern:'*/api/health'},{urlPattern:'*/api/analyze'}]});
  await p.call('Page.reload',{ignoreCache:true});await p.waitFor("document.querySelector('#status')?.textContent.includes('Add an image family')");
  await p.upload('#files',[resolve('examples/smarties.png'),resolve('examples/horse.png')]);
  await p.waitFor("document.querySelectorAll('[data-question]').length===1 && !document.querySelector('#analyze').disabled");
  await p.fill('#description','Find red objects');await p.fill('#question-0','Color');
  await p.click('#back-images');
  const first=await p.evaluate("document.querySelector('[data-split]').dataset.split");
  await p.select(`[data-split="${first}"]`,'validation');
  const roleWarning=await p.evaluate("document.querySelector('.sample-label-status').textContent");
  await p.click('#continue-analysis');await p.click('#analyze');
  // Existing questions remain visible during reinspection; wait for the response
  // before measuring the manual button's position in the completed layout.
  await p.waitFor("document.querySelectorAll('[data-question]').length===1 && !document.querySelector('#analyze').disabled");
  await p.click('#manual-start');await p.waitFor("document.querySelector('#status').textContent.includes('Ready')");
  await p.click('#to-finish');
  const before=await p.evaluate("document.querySelector('#validation-summary').innerText");
  await p.click('#toggle-images');await p.select('#upload-role','validation');
  const count=analyses;
  await p.upload('#files',[resolve('examples/coins.png')]);
  await p.waitFor("document.querySelector('#image-count').textContent.startsWith('3 /')");
  const stageAfterHeld=await p.evaluate("document.querySelector('[aria-current=step]').dataset.screen");
  await p.click('#open-ai');
  const retained=await p.evaluate("({analysis:document.querySelector('#analysis').textContent,answer:document.querySelector('[data-question]')?.value,generateVisible:!document.querySelector('#suggest').hidden})");
  await p.click('#open-finish');const after=await p.evaluate("document.querySelector('#validation-summary').innerText");
  await p.screenshot('artifacts/strict/round-05-validation.png');
  const result={tested_at:new Date().toISOString(),provider:'Controlled browser fixture; no live AI',checks:{submittedImageIsReused:roleWarning.includes('Reused'),excludedFromHeldout:before.includes('Held-out validation: 0/0'),freshImageInHeldout:after.includes('Held-out validation: 0/1'),validationUploadKeepsScreen:stageAfterHeld==='images',validationUploadKeepsDiscovery:retained.analysis.includes('CONTROLLED FIXTURE')&&retained.answer==='Color'&&retained.generateVisible,validationUploadDoesNotCallAI:count===analyses},roleWarning,before,after,errors};
  console.log(JSON.stringify(result,null,2));await writeFile('artifacts/strict/round-05-provenance.json',JSON.stringify(result,null,2));
}catch(error){
  await writeFile('artifacts/strict/provenance-failure.json',JSON.stringify({error:error.message,page:await p.evaluate("({status:document.querySelector('#status').textContent,notice:document.querySelector('#notice')?.textContent,screen:document.querySelector('[aria-current=step]')?.dataset.screen,body:document.body.innerText})")},null,2));
  await p.screenshot('artifacts/strict/provenance-failure.png');throw error;
}finally{await p.call('Fetch.disable');await p.call('Page.reload',{ignoreCache:true});p.close();}
