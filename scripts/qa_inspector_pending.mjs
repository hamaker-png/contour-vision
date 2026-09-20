// A real CPU response is paused in standalone Chrome while the user types.
import {connect} from './cdp.mjs';
import {readFile,writeFile} from 'node:fs/promises';
const p=await connect(JSON.parse(await readFile('artifacts/strict/root-tab.json')).id);
let held;const errors=[];
p.on('Fetch.requestPaused',e=>{held=e;});
p.on('Runtime.exceptionThrown',e=>errors.push(e.exceptionDetails.text));
try{
  await p.call('Page.bringToFront');await p.call('Runtime.enable');
  await p.call('Emulation.setDeviceMetricsOverride',{width:1424,height:905,deviceScaleFactor:1,mobile:false});
  await p.call('Page.reload',{ignoreCache:true});await p.waitFor("document.querySelector('#status')?.textContent.includes('Add an image family')");
  await p.select('#examples','red-candies');await p.waitFor("document.querySelector('#status').textContent.startsWith('Ready')");
  await p.click('.node[aria-label="Resize"]');await p.click('#close-inspector');
  await p.call('Fetch.enable',{patterns:[{urlPattern:'*/api/timelines/run',requestStage:'Request'}]});
  await p.click('#run');for(let n=0;n<30&&!held;n++)await new Promise(r=>setTimeout(r,100));
  if(!held)throw Error('No paused CPU request');
  await p.click('#toggle-inspector');await p.fill('#param-max_side','640');
  const before=await p.evaluate("({value:document.querySelector('#param-max_side').value,focus:document.activeElement.id})");
  await p.call('Fetch.continueRequest',{requestId:held.requestId});await p.waitFor("document.querySelector('#status').textContent.startsWith('Ready')");
  const after=await p.evaluate("({value:document.querySelector('#param-max_side').value,focus:document.activeElement.id})");
  await p.call('Fetch.disable');
  await p.click('#params-form button[type=submit]');await p.waitFor("document.querySelector('#status').textContent.startsWith('Ready')");
  const applied=await p.evaluate("document.querySelector('#param-max_side').value");
  const result={tested_at:new Date().toISOString(),before,after,applied,checks:{valueSurvives:after.value==='640',focusSurvives:after.focus==='param-max_side',canApply:applied==='640',noRuntimeErrors:errors.length===0},errors};
  await writeFile('artifacts/strict/round-07-input-after.json',JSON.stringify(result,null,2));
  await p.screenshot('artifacts/strict/round-07-inspector-after.png');console.log(JSON.stringify(result,null,2));
}finally{await p.call('Fetch.disable');p.close();}
