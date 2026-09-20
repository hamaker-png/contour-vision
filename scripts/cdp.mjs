// Browser QA against the installed standalone Chrome, using a dedicated review profile.
import {writeFile} from 'node:fs/promises';
const endpoint='http://127.0.0.1:9223';
export async function pages(){return (await fetch(`${endpoint}/json/list`)).json();}
export async function newPage(url='http://127.0.0.1:8000/'){
  const page=await (await fetch(`${endpoint}/json/new?${encodeURIComponent(url)}`,{method:'PUT'})).json();
  return connect(page.id);
}
export async function connect(id){
  const page=(await pages()).find(p=>p.id===id);if(!page)throw Error(`Browser tab ${id} is missing`);
  const ws=new WebSocket(page.webSocketDebuggerUrl),pending=new Map(),listeners=new Map();let sequence=0;
  await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
  ws.onmessage=e=>{const event=JSON.parse(e.data);if(event.id){const p=pending.get(event.id);if(p){clearTimeout(p.timer);pending.delete(event.id);event.error?p.reject(Error(event.error.message)):p.resolve(event.result);}}else for(const fn of listeners.get(event.method)||[])fn(event.params);};
  ws.onclose=()=>{for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error('Chrome connection closed'));}pending.clear();};
  const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++sequence,timer=setTimeout(()=>{pending.delete(id);reject(Error(`Chrome timed out: ${method}`));},30000);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params}));});
  const evaluate=async expression=>{const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;};
  const box=selector=>evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e)throw Error('Missing element');e.scrollIntoView({block:'center',inline:'center'});const r=e.getBoundingClientRect();if(!r.width||!r.height||e.disabled)throw Error('Element is not available');return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
  const click=async selector=>{const p=await box(selector);await call('Input.dispatchMouseEvent',{type:'mousePressed',...p,button:'left',clickCount:1});await call('Input.dispatchMouseEvent',{type:'mouseReleased',...p,button:'left',clickCount:1});};
  const fill=async(selector,text)=>{await click(selector);await call('Input.dispatchKeyEvent',{type:'keyDown',key:'a',code:'KeyA',windowsVirtualKeyCode:65,modifiers:2});await call('Input.dispatchKeyEvent',{type:'keyUp',key:'a',code:'KeyA',windowsVirtualKeyCode:65,modifiers:2});await call('Input.insertText',{text:String(text)});};
  const select=(selector,value)=>evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});e.value=${JSON.stringify(value)};e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));return e.value;})()`);
  const upload=async(selector,files)=>{const {root}=await call('DOM.getDocument');const {nodeId}=await call('DOM.querySelector',{nodeId:root.nodeId,selector});await call('DOM.setFileInputFiles',{nodeId,files});};
  const waitFor=async(expression,timeout=10000)=>{const start=Date.now();let lastError;while(Date.now()-start<timeout){try{const value=await evaluate(expression);if(value)return value;}catch(error){lastError=error;}await new Promise(r=>setTimeout(r,100));}throw Error(`Condition timed out: ${expression}${lastError?` (${lastError.message})`:''}`);};
  const screenshot=async(path)=>{const {data}=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await writeFile(path,Buffer.from(data,'base64'));return path;};
  return {id:page.id,call,evaluate,click,fill,select,upload,waitFor,screenshot,on:(name,fn)=>listeners.set(name,[...(listeners.get(name)||[]),fn]),close:()=>ws.close()};
}
