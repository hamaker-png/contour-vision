// Standalone Chrome integration trial. Provider responses are fixtures, never live AI.
import {connect} from './cdp.mjs';
import {readFile,writeFile,mkdir,readdir} from 'node:fs/promises';
import {resolve} from 'node:path';
const folder=resolve('artifacts/strict');
const p=await connect(JSON.parse(await readFile(`${folder}/root-tab.json`)).id);
await p.call('Page.bringToFront');
const calls=[],errors=[];
const fixture={observations:'INTEGRATION FIXTURE: compare the shared silhouette across this family.',important_features:['Silhouette and foreground contrast'],questions:['Which feature must stay consistent?','Which measurements matter?'],limitations:['Fixture response; this does not test model quality.']};
p.on('Fetch.requestPaused',async event=>{
  try{
    const url=new URL(event.request.url);
    const body=url.pathname==='/api/health'?{ok:true,server_key:true,cpu_only:true}:fixture;
    if(url.pathname==='/api/analyze'){
      const request=JSON.parse(event.request.postData);
      calls.push({names:request.samples.map(s=>s.name),roles:request.samples.map(s=>s.split),answers:request.answers,target:request.description});
    }
    await p.call('Fetch.fulfillRequest',{requestId:event.requestId,responseCode:200,responseHeaders:[{name:'Content-Type',value:'application/json'}],body:Buffer.from(JSON.stringify(body)).toString('base64')});
  }catch(e){errors.push(e.message);}
});
try{
  await p.call('Fetch.enable',{patterns:[{urlPattern:'http://127.0.0.1:8000/api/health'},{urlPattern:'http://127.0.0.1:8000/api/analyze'}]});
  await p.call('Page.reload',{ignoreCache:true});
  await p.waitFor("document.querySelector('#status').textContent.includes('Add an image family')");
  await p.upload('#files',[resolve('examples/smarties.png'),resolve('examples/horse.png')]);
  await p.waitFor("document.querySelectorAll('[data-question]').length===2");
  await p.fill('#description','Find the shared objects');
  await p.fill('#question-0','Silhouette matters more than color');
  await p.fill('#question-1','Length in pixels');
  await p.click('#back-images');
  await p.upload('#files',[resolve('examples/coins.png')]);
  await p.waitFor("document.querySelectorAll('[data-question]').length===2 && document.querySelector('#family-context').textContent.startsWith('3 training')");
  const preserved=calls.at(-1)?.answers.includes('Silhouette matters more than color');
  const result={tested_at:new Date().toISOString(),browser:'Standalone Chrome through CDP',provider:'Intercepted fixture; no OpenAI call',checks:{uploadStartsDiscovery:calls.length===2,allFamilyImages:calls.at(-1)?.names.length===3,answersSurviveAddedImage:preserved},calls,errors};
  await writeFile(`${folder}/family-conversation-${preserved?'pass':'baseline'}.json`,JSON.stringify(result,null,2));
  await p.screenshot(`${folder}/family-conversation-${preserved?'pass':'baseline'}.png`);
  console.log(JSON.stringify(result,null,2));
}finally{
  await p.call('Fetch.disable');
  await p.call('Page.reload',{ignoreCache:true});
  p.close();
}
