// Real pointer drawing after zoom/pan and example-family boundaries in standalone Chrome.
import {connect} from './cdp.mjs';
import {readFile,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
const p=await connect(JSON.parse(await readFile('artifacts/strict/root-tab.json')).id),runs=[],errors=[];
p.on('Fetch.requestPaused',async e=>{runs.push(JSON.parse(e.request.postData));try{await p.call('Fetch.continueRequest',{requestId:e.requestId});}catch(error){errors.push(error.message);}});
p.on('Runtime.exceptionThrown',e=>errors.push(e.exceptionDetails.text));
async function point(x,y,type){await p.call('Input.dispatchMouseEvent',{type,x,y,button:type==='mouseMoved'?'none':'left',buttons:type==='mouseReleased'?0:1,clickCount:type==='mouseMoved'?0:1});}
try{
  await p.call('Page.bringToFront');await p.call('Runtime.enable');await p.call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  await p.call('Fetch.enable',{patterns:[{urlPattern:'*/api/timelines/run',requestStage:'Request'}]});
  await p.call('Page.reload',{ignoreCache:true});await p.waitFor("document.querySelector('#status')?.textContent.includes('Add an image family')");
  await p.select('#examples','green-shapes');await p.waitFor("document.querySelector('#status').textContent.startsWith('Ready')");
  await p.click('#to-finish');await p.click('[data-review-label]');await p.waitFor("!document.querySelector('#save-labels').disabled");
  const fit=await p.evaluate("document.querySelector('#label-canvas').getBoundingClientRect().width");await p.click('#zoom-label-in');await p.click('#zoom-label-in');
  // Move to a visible central portion of the zoomed canvas with real wheel input.
  await p.evaluate("document.querySelector('.label-stage').scrollIntoView({block:'center'})");
  const wheel=await p.evaluate("(()=>{const r=document.querySelector('.label-stage').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()");
  await p.call('Input.dispatchMouseEvent',{type:'mouseWheel',...wheel,deltaX:60,deltaY:60});await new Promise(r=>setTimeout(r,150));
  const bounds=await p.evaluate("(()=>{const s=document.querySelector('.label-stage').getBoundingClientRect(),c=document.querySelector('#label-canvas').getBoundingClientRect();return {s:s.toJSON(),c:c.toJSON(),overflow:document.documentElement.scrollWidth>innerWidth}})()");
  const x1=bounds.s.left+bounds.s.width*.35,y1=bounds.s.top+bounds.s.height*.35,x2=x1+45,y2=y1+45;
  const expected={x:(x1-bounds.c.left)/bounds.c.width,y:(y1-bounds.c.top)/bounds.c.height,width:45/bounds.c.width,height:45/bounds.c.height};
  await point(x1,y1,'mousePressed');await point(x2,y2,'mouseMoved');await point(x2,y2,'mouseReleased');
  const drawn=await p.evaluate("({count:document.querySelectorAll('[data-label-box]').length,complete:document.querySelector('#labels-complete').checked,zoom:document.querySelector('#label-zoom').textContent})");
  await p.click('#save-labels');await p.waitFor("!document.querySelector('#label-dialog').open&&document.querySelector('#status').textContent.startsWith('Ready')");
  const box=runs.at(-1).samples[0].boxes.at(-1);
  await p.click('[data-review-label]');await p.waitFor("!document.querySelector('#save-labels').disabled");const resetsFit=await p.evaluate("document.querySelector('#label-zoom').textContent==='Fit'");await p.click('#close-labels');
  await p.click('#toggle-images');await p.select('#upload-role','validation');await p.upload('#files',[resolve('examples/smarties.png')]);await p.waitFor("document.querySelector('#image-count').textContent.startsWith('2 /')");
  const heldout=await p.evaluate("({count:document.querySelector('#image-count').textContent,timelines:document.querySelectorAll('.timeline').length,roles:[...document.querySelectorAll('[data-split]')].map(e=>e.value)})");
  await p.click('#open-ai');await p.click('.target-brief details summary');await p.fill('#scale','3');await p.click('#unit');await p.click('#toggle-images');await p.select('#upload-role','train');await p.upload('#files',[resolve('examples/horse.png')]);await p.waitFor("document.querySelector('#image-count').textContent.startsWith('1 /')");
  const replaced=await p.evaluate("({scale:document.querySelector('#scale').value,timelines:document.querySelectorAll('.timeline').length,filename:document.querySelector('.sample-info button').textContent})");
  await p.screenshot('artifacts/strict/round-11-clean-family.png');
  const result={tested_at:new Date().toISOString(),fit,drawn,expected,box,heldout,replaced,checks:{zoomActuallyEnlarges:bounds.c.width>fit*1.9,noHorizontalPageOverflow:!bounds.overflow,pointerAddsOnlyOneBox:drawn.count===3&&!drawn.complete,normalizedDrawingCorrect:Object.keys(expected).every(k=>Math.abs(expected[k]-box[k])<.003),newDialogStartsAtFit:resetsFit,heldoutKeepsExampleGraph:heldout.timelines===3&&heldout.roles.join(',')==='train,validation',newTrainingReplacesExample:replaced.filename==='horse.png'&&replaced.timelines===0,newTrainingResetsScale:replaced.scale==='0',noRuntimeErrors:!errors.length},errors};
  await writeFile('artifacts/strict/round-11-zoom-family.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
}finally{await p.call('Fetch.disable');await p.call('Emulation.setDeviceMetricsOverride',{width:1424,height:905,deviceScaleFactor:1,mobile:false});p.close();}
