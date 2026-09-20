export function reviewImage(timelineId,sample,image,requestError){
  const path=image?.timelines.find(t=>t.id===timelineId),finalId=path?(path.path.at(-1)||'source'):undefined,finalStage=image?.stages[finalId];
  const measurementId=path?.path.findLast(id=>image.stages[id]?.details?.detections!==undefined),measurementStage=image?.stages[measurementId];
  const errors=requestError?[requestError]:path?.path.map(id=>image.stages[id]?.error).filter(Boolean)||[];
  const base={path,finalId,finalStage,measurementId,measurementStage,errors};
  if(errors.length||path?.errors)return {...base,status:'failed',summary:requestError?'Latest run failed':`Pipeline failed · ${errors.length||path.errors} step errors`};
  if(!path)return {...base,status:'untested',summary:'Not tested yet'};
  const details=finalStage?.details;
  if(details?.detections===undefined)return {...base,status:'transform',summary:measurementStage?'Final transform · measurements available at an earlier step':'Transform only · no object measurements'};
  if(!sample.labeled)return {...base,status:'unlabeled',summary:`${details.count} objects · labels incomplete`};
  const fit=details.fit;
  if(!fit)return {...base,status:'unscored',summary:'Labels complete · scoring unavailable; retest this image'};
  if(!sample.boxes.length)return {...base,status:fit.fp?'mismatch':'negative',summary:`Negative image · ${fit.fp} false detection${fit.fp===1?'':'s'}`};
  return {...base,status:fit.fp||fit.fn?'mismatch':'matched',summary:`${fit.tp} matched · ${fit.fp} extra · ${fit.fn} missed · F1 ${fit.f1===null?'—':fit.f1.toFixed(3)}`};
}
// Same greedy 0.5-IoU assignment and descending index tie breaks as backend.engine.counts.
// Suppress annotations if the returned score disagrees, rather than inventing matches.
export function matchedBoxes(sample,detections,fit){
  if(!sample.labeled||!detections||!fit)return null;
  const pairs=[];
  detections.forEach((d,i)=>sample.boxes.forEach((b,j)=>{
    const [x,y,w,h]=d.normalized_box,intersection=Math.max(0,Math.min(x+w,b.x+b.width)-Math.max(x,b.x))*Math.max(0,Math.min(y+h,b.y+b.height)-Math.max(y,b.y));
    pairs.push([intersection/Math.max(w*h+b.width*b.height-intersection,1e-12),i,j]);
  }));
  pairs.sort((a,b)=>b[0]-a[0]||b[1]-a[1]||b[2]-a[2]);
  const usedD=new Set(),usedT=new Set(),matches=[];
  for(const [overlap,i,j] of pairs)if(overlap>=.5&&!usedD.has(i)&&!usedT.has(j)){usedD.add(i);usedT.add(j);matches.push({detection:i,label:j});}
  if(fit.tp!==matches.length||fit.fp!==detections.length-matches.length||fit.fn!==sample.boxes.length-matches.length)return null;
  return {matches,extra:detections.map((_,i)=>i).filter(i=>!usedD.has(i)),missed:sample.boxes.map((_,i)=>i).filter(i=>!usedT.has(i))};
}
