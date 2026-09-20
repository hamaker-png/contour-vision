import {normalizedBox} from './evaluation.mjs';
export function createLabelEditor(onSave) {
  const $=id=>document.getElementById(id),canvas=$('label-canvas'),ctx=canvas.getContext('2d');
  let sample,boxes=[],image,start=null,end=null,epoch=0,selected=null,undo=[],redo=[],coordinateDirty=false,zoom=1,fitScale=1,mode='draw',activePointer=null,panStart=null;
  const stage=canvas.parentElement,zoomLevels=[1,1.5,2,3,4];
  function clearGesture(){const id=activePointer;activePointer=null;panStart=null;start=end=null;if(id!==null&&canvas.hasPointerCapture(id))canvas.releasePointerCapture(id);draw();}
  function setMode(next){
    clearGesture();mode=next;canvas.classList.toggle('pan-mode',mode==='pan');
    $('mode-label-pan').setAttribute('aria-pressed',String(mode==='pan'));$('mode-label-draw').setAttribute('aria-pressed',String(mode==='draw'));
    $('label-pan-help').textContent=mode==='pan'?'Pan mode: drag the image to move around. Boxes stay unchanged.':'Draw mode: drag to add a box. Switch to Pan to move around.';
  }
  $('mode-label-pan').addEventListener('click',()=>setMode('pan'));$('mode-label-draw').addEventListener('click',()=>setMode('draw'));
  function resizeCanvas(){
    const scale=fitScale*zoom;canvas.width=Math.max(1,Math.round(image.naturalWidth*scale));canvas.height=Math.max(1,Math.round(image.naturalHeight*scale));
    canvas.style.width=`${canvas.width}px`;canvas.style.height=`${canvas.height}px`;
    $('label-zoom').textContent=zoom===1?'Fit':`${zoom}× fit`;$('zoom-label-out').disabled=zoom===1;$('zoom-label-in').disabled=zoom===4;draw();
  }
  function zoomTo(next){
    if(!image)return;clearGesture();const r=canvas.getBoundingClientRect(),s=stage.getBoundingClientRect(),x=(s.left+stage.clientWidth/2-r.left)/r.width,y=(s.top+stage.clientHeight/2-r.top)/r.height;
    zoom=next;resizeCanvas();stage.scrollLeft=canvas.offsetLeft+x*canvas.width-stage.clientWidth/2;stage.scrollTop=canvas.offsetTop+y*canvas.height-stage.clientHeight/2;
  }
  $('zoom-label-in').addEventListener('click',()=>zoomTo(zoomLevels[Math.min(zoomLevels.length-1,zoomLevels.indexOf(zoom)+1)]));
  $('zoom-label-out').addEventListener('click',()=>zoomTo(zoomLevels[Math.max(0,zoomLevels.indexOf(zoom)-1)]));
  $('zoom-label-fit').addEventListener('click',()=>zoomTo(1));
  const snapshot=()=>({boxes:structuredClone(boxes),complete:$('labels-complete').checked,selected});
  function fields(){
    coordinateDirty=false;$('coordinate-pending').hidden=true;
    const b=boxes[selected]||{x:0,y:0,width:.1,height:.1};
    for(const [id,key] of [['box-x','x'],['box-y','y'],['box-w','width'],['box-h','height']])$(id).value=Number((b[key]*100).toFixed(6));
    $('box-submit').textContent=selected===null?'Add box':'Update box '+(selected+1);
    $('delete-label').disabled=selected===null;
    $('label-mode').textContent=selected===null?'Add a new box by dragging or entering coordinates.':'Box '+(selected+1)+' selected. Edit its coordinates below, or drag to add another box.';
  }
  function draw() {
    ctx.clearRect(0,0,canvas.width,canvas.height);if(!image)return;ctx.drawImage(image,0,0,canvas.width,canvas.height);
    function rectangle(box,index,draft=false) {
      const x=box.x*canvas.width,y=box.y*canvas.height,w=box.width*canvas.width,h=box.height*canvas.height,chosen=index===selected||draft;
      ctx.lineWidth=chosen?3:2;ctx.strokeStyle=chosen?'#ac8400':'#23733b';ctx.fillStyle=chosen?'#ffe99f44':'#31764918';ctx.fillRect(x,y,w,h);ctx.strokeRect(x,y,w,h);
      if(!draft){ctx.fillStyle=chosen?'#856400':'#23733b';ctx.fillRect(x,y,23,20);ctx.fillStyle='#fff';ctx.font='13px sans-serif';ctx.fillText(String(index+1),x+6,y+14);}
    }
    boxes.forEach((b,i)=>rectangle(b,i));if(start&&end){const box=normalizedBox(...start,...end);if(box)rectangle(box,0,true);}
    $('label-count').textContent=boxes.length+' target box'+(boxes.length===1?'':'es');
    $('undo-label').disabled=!undo.length;$('redo-label').disabled=!redo.length;$('clear-labels').disabled=!boxes.length;
    $('label-boxes').innerHTML=boxes.map((_,i)=>'<button type="button" data-label-box="'+i+'" aria-pressed="'+(i===selected)+'" aria-label="Select box '+(i+1)+'">'+(i+1)+'</button>').join('');
  }
  function point(e){const r=canvas.getBoundingClientRect();return [(e.clientX-r.left)/r.width,(e.clientY-r.top)/r.height];}
  function change(fn){undo.push(snapshot());if(undo.length>50)undo.shift();redo=[];fn();$('labels-complete').checked=false;$('label-error').textContent='';fields();draw();}
  function checkCoordinates(){if(!coordinateDirty)return true;$('label-error').textContent='Update or reset the coordinate changes before continuing.';$('box-controls').open=true;$('box-submit').focus();return false;}
  function choose(index){if(!checkCoordinates())return;selected=index;fields();draw();if(index!==null)$('box-controls').open=true;}
  canvas.addEventListener('pointerdown',e=>{
    if(!image)return;
    if(!e.isPrimary){if(e.pointerType==='touch'&&mode==='draw')clearGesture();return;}
    if(activePointer!==null||(e.pointerType==='mouse'&&e.button!==0))return;
    if(mode==='pan'){
      if(e.pointerType!=='touch'){activePointer=e.pointerId;panStart={x:e.clientX,y:e.clientY,left:stage.scrollLeft,top:stage.scrollTop};canvas.setPointerCapture(e.pointerId);}
      return;
    }
    if(!checkCoordinates())return;activePointer=e.pointerId;start=point(e);end=start;canvas.setPointerCapture(e.pointerId);
  });
  canvas.addEventListener('pointermove',e=>{
    if(e.pointerId!==activePointer)return;
    if(panStart){stage.scrollLeft=panStart.left-(e.clientX-panStart.x);stage.scrollTop=panStart.top-(e.clientY-panStart.y);return;}
    if(!start)return;end=point(e);draw();
  });
  canvas.addEventListener('pointerup',e=>{
    if(e.pointerId!==activePointer)return;
    if(panStart){clearGesture();return;}
    if(!start){clearGesture();return;}const finish=point(e),box=normalizedBox(...start,...finish);clearGesture();
    if(!box){const hit=boxes.findLastIndex(b=>finish[0]>=b.x&&finish[0]<=b.x+b.width&&finish[1]>=b.y&&finish[1]<=b.y+b.height);choose(hit<0?null:hit);return;}
    if(boxes.length>=150){$('label-error').textContent='Use at most 150 target boxes. Select a box to correct or remove it.';draw();return;}
    change(()=>{boxes.push(box);selected=boxes.length-1;});
  });
  canvas.addEventListener('pointercancel',e=>{if(e.pointerId===activePointer)clearGesture();});
  canvas.addEventListener('lostpointercapture',e=>{if(e.pointerId===activePointer)clearGesture();});
  function history(back){if(!checkCoordinates())return;const from=back?undo:redo,to=back?redo:undo;if(!from.length)return;to.push(snapshot());const s=from.pop();boxes=s.boxes;selected=s.selected;$('labels-complete').checked=s.complete;$('label-error').textContent='';fields();draw();}
  $('undo-label').addEventListener('click',()=>history(true));$('redo-label').addEventListener('click',()=>history(false));
  $('clear-labels').addEventListener('click',()=>{if(checkCoordinates()&&boxes.length)change(()=>{boxes=[];selected=null;});});
  $('delete-label').addEventListener('click',()=>{if(checkCoordinates()&&selected!==null)change(()=>{boxes.splice(selected,1);selected=null;});});
  $('new-label').addEventListener('click',()=>choose(null));
  $('label-boxes').addEventListener('click',e=>{const b=e.target.closest('[data-label-box]');if(b)choose(Number(b.dataset.labelBox));});
  $('close-labels').addEventListener('click',()=>$('label-dialog').close());
  $('label-dialog').addEventListener('close',()=>{if($('label-dialog').open)return;epoch++;clearGesture();});
  $('box-form').addEventListener('input',()=>{coordinateDirty=true;$('coordinate-pending').hidden=false;});
  $('reset-coordinates').addEventListener('click',()=>{fields();$('label-error').textContent='';});
  $('box-form').addEventListener('submit',e=>{
    e.preventDefault();const [x,y,w,h]=['box-x','box-y','box-w','box-h'].map(id=>Number($(id).value)/100);
    if(![x,y,w,h].every(Number.isFinite)||x<0||y<0||x+w>1.000001||y+h>1.000001||w<=0||h<=0){$('label-error').textContent='Keep the complete box inside 100% of the image.';return;}
    if(selected===null&&boxes.length>=150){$('label-error').textContent='Use at most 150 target boxes.';return;}
    const box={x,y,width:w,height:h};
    if(selected!==null&&['x','y','width','height'].every(k=>Math.abs(box[k]-boxes[selected][k])<1e-8)){fields();$('label-error').textContent='';return;}
    change(()=>{if(selected===null){boxes.push(box);selected=boxes.length-1;}else boxes[selected]=box;});
  });
  $('save-labels').addEventListener('click',()=>{
    if(!image||!checkCoordinates())return;
    try{onSave(sample.id,structuredClone(boxes),$('labels-complete').checked,sample.data,JSON.stringify([sample.boxes,sample.labeled]));$('label-dialog').close();}
    catch(error){$('label-error').textContent=error.message;}
  });
  return {open(original){
    sample=structuredClone(original);boxes=structuredClone(sample.boxes);undo=[];redo=[];selected=null;
    $('labels-complete').checked=sample.labeled;$('label-error').textContent='Loading image…';$('label-image-name').textContent=sample.name;
    image=null;setMode('draw');ctx.clearRect(0,0,canvas.width,canvas.height);$('save-labels').disabled=true;$('label-boxes').textContent='';$('box-controls').open=false;fields();
    const token=++epoch,loaded=new Image();
    loaded.onload=()=>{if(token!==epoch||!$('label-dialog').open)return;image=loaded;zoom=1;fitScale=Math.min(1,Math.max(180,stage.clientWidth-18)/image.naturalWidth,Math.max(180,innerHeight*.43)/image.naturalHeight);$('save-labels').disabled=false;$('label-error').textContent='';resizeCanvas();stage.scrollLeft=stage.scrollTop=0;};
    loaded.onerror=()=>{if(token===epoch&&$('label-dialog').open)$('label-error').textContent='This image could not be displayed.';};loaded.src=sample.data;$('label-dialog').showModal();
  }};
}

