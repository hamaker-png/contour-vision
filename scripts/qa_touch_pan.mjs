import {connect} from './cdp.mjs';
import {readFile,writeFile} from 'node:fs/promises';
const p=await connect(JSON.parse(await readFile('artifacts/strict/root-tab.json')).id),errors=[];
p.on('Runtime.exceptionThrown',e=>errors.push(e.exceptionDetails.text));
const snapshot=()=>p.evaluate("(()=>{const e=document.querySelector('.label-stage');return {left:e.scrollLeft,top:e.scrollTop,count:document.querySelectorAll('[data-label-box]').length,complete:document.querySelector('#labels-complete').checked};})()");
async function points(type,touchPoints){await p.call('Input.dispatchTouchEvent',{type,touchPoints});await new Promise(r=>setTimeout(r,35));}
async function center(){await p.evaluate("document.querySelector('.label-stage').scrollIntoView({block:'center'})");return p.evaluate("(()=>{const r=document.querySelector('.label-stage').getBoundingClientRect();return {x:r.x+r.width*.6,y:r.y+r.height*.6};})()");}
try{
  await p.call('Page.bringToFront');await p.call('Runtime.enable');await p.call('Fetch.disable');
  await p.call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});await p.call('Emulation.setTouchEmulationEnabled',{enabled:true,maxTouchPoints:2});
  await p.call('Page.reload',{ignoreCache:true});await p.waitFor("document.querySelector('#status')?.textContent.includes('Add an image family')");
  await p.select('#examples','green-shapes');await p.waitFor("document.querySelector('#status').textContent.startsWith('Ready')");await p.click('#to-finish');await p.click('[data-review-label]');await p.waitFor("!document.querySelector('#save-labels').disabled");
  for(let n=0;n<4;n++)await p.click('#zoom-label-in');
  await p.click('#mode-label-pan');let c=await center();const before=await snapshot();
  await points('touchStart',[{id:1,...c}]);for(let n=1;n<=5;n++)await points('touchMove',[{id:1,x:c.x-n*14,y:c.y-n*10}]);await points('touchEnd',[]);await new Promise(r=>setTimeout(r,200));const pan=await snapshot();
  c=await center();await points('touchStart',[{id:1,...c}]);for(let n=1;n<=5;n++)await points('touchMove',[{id:1,x:c.x,y:c.y-n*14}]);await points('touchEnd',[]);await new Promise(r=>setTimeout(r,150));const vertical=await snapshot();
  await p.click('#mode-label-draw');c=await center();const beforeTwo=await snapshot();
  await points('touchStart',[{id:1,...c}]);await points('touchStart',[{id:1,...c},{id:2,x:c.x-40,y:c.y-40}]);
  await points('touchMove',[{id:1,x:c.x+25,y:c.y+25},{id:2,x:c.x-15,y:c.y-15}]);await points('touchEnd',[]);const two=await snapshot();
  c=await center();await points('touchStart',[{id:1,...c}]);await points('touchMove',[{id:1,x:c.x+35,y:c.y+35}]);await points('touchEnd',[]);const drawn=await snapshot();await p.click('#undo-label');const undo=await snapshot();
  await p.click('#mode-label-pan');c=await center();const beforeMouse=await snapshot();
  await p.call('Input.dispatchMouseEvent',{type:'mousePressed',...c,button:'left',clickCount:1});await p.call('Input.dispatchMouseEvent',{type:'mouseMoved',x:c.x-40,y:c.y-35,button:'left',buttons:1});await p.call('Input.dispatchMouseEvent',{type:'mouseReleased',x:c.x-40,y:c.y-35,button:'left',clickCount:1});const mouse=await snapshot();
  await p.screenshot('artifacts/strict/round-12-touch-pan.png');
  const result={tested_at:new Date().toISOString(),before,pan,vertical,beforeTwo,two,drawn,undo,beforeMouse,mouse,checks:{touchPansBothAxes:Math.abs(pan.left-before.left)>10&&Math.abs(vertical.top-pan.top)>10,panDoesNotLabel:vertical.count===before.count&&vertical.complete===before.complete,twoFingerDrawDoesNotAdd:two.count===beforeTwo.count&&two.complete===beforeTwo.complete,singleFingerDrawAdds:drawn.count===two.count+1&&!drawn.complete,undoRestoresCompleteness:undo.count===before.count&&undo.complete===before.complete,mousePansWithoutLabels:mouse.left!==beforeMouse.left&&mouse.count===beforeMouse.count,noRuntimeErrors:!errors.length},errors};
  await writeFile('artifacts/strict/round-12-pan.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
}finally{await p.call('Emulation.setTouchEmulationEnabled',{enabled:false});await p.call('Emulation.setDeviceMetricsOverride',{width:1424,height:905,deviceScaleFactor:1,mobile:false});p.close();}
