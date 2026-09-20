export function estimate(local, hardware) {
  if(hardware.mode==='local') return {ms:local,low_ms:local,high_ms:local,estimated:false,basis:'same machine'};
  let factor=null,span=2,basis='Insufficient hardware information';
  if(hardware.mode==='relative' && hardware.relative_speed>0){factor=1/hardware.relative_speed;basis='User-supplied single-thread speed ratio';}
  if(hardware.mode==='clock' && hardware.host_ghz>0 && hardware.target_ghz>0){factor=hardware.host_ghz/hardware.target_ghz;span=3;basis='GHz-only heuristic; assumes equal work per clock';}
  if(hardware.mode==='calibrated' && hardware.reference_local_ms>0 && hardware.reference_target_ms>0){factor=hardware.reference_target_ms/hardware.reference_local_ms;span=1.5;basis='Reference-workload scaling; other operations may scale differently';}
  const ms=factor===null?null:local*factor;
  return {ms,low_ms:ms===null?null:ms/span,high_ms:ms===null?null:ms*span,estimated:true,basis};
}

export function outputKind(kind,input,params={}) {
  if(['grayscale','channel','cimg_distance','sobel','top_hat','black_hat'].includes(kind)) return 'gray';
  if(['hsv_mask','otsu','threshold','adaptive_threshold','canny','contours','cimg_components','hough_circles','hough_lines','barcode','confirm','range_mask','fill_holes'].includes(kind)) return 'mask';
  if(kind==='gaussian_blur' && input==='mask' && params.kernel>1)return 'gray';
  return input;
}
export function inputKind(path,index,catalog) {
  let kind='color';
  for(const op of path.slice(0,index)) {
    if(!catalog.find(c=>c.kind===op.kind)?.accepts.includes(kind))return null;
    kind=outputKind(op.kind,kind,op.params);
  }
  return kind;
}

export function aggregate(timelineId,samples,results,split,executionErrors=new Map()) {
  let tp=0,fp=0,fn=0,labeled=0,tested=0,failed=0,negatives=0,emptyCorrect=0; const times=[];
  const group=samples.filter(s=>s.split===split);
  for(const sample of group) {
    if(executionErrors.has(sample.id)){tested++;failed++;continue;}
    const image=results.get(sample.id),path=image?.timelines.find(t=>t.id===timelineId);
    if(!path)continue;
    tested++;if(path.errors){failed++;continue;}if(path.local_ms!==null)times.push(path.local_ms);
    const stage=image.stages[path.path.at(-1)],fit=stage?.details?.fit;
    if(!sample.labeled || !fit)continue;
    labeled++;tp+=fit.tp;fp+=fit.fp;fn+=fit.fn;
    if(!sample.boxes.length){negatives++;if(!fit.fp)emptyCorrect++;}
  }
  return {tp,fp,fn,labeled,tested,failed,untested:group.length-tested,unlabeled:group.filter(s=>!s.labeled).length,total:group.length,negatives,emptyCorrect,
    f1:2*tp+fp+fn?2*tp/(2*tp+fp+fn):null,
    mean_ms:times.length?times.reduce((a,b)=>a+b,0)/times.length:null};
}

export function normalizedBox(x1,y1,x2,y2) {
  const clamp=v=>Math.max(0,Math.min(1,v));
  const x=clamp(Math.min(x1,x2)),y=clamp(Math.min(y1,y2));
  const width=clamp(Math.max(x1,x2))-x,height=clamp(Math.max(y1,y2))-y;
  return width>.003 && height>.003?{x,y,width,height}:null;
}
