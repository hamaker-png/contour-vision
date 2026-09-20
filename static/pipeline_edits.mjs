import {paths,moveOperation,clone,uid,supportingIds,dependencyIds} from './workflow.mjs';
import {outputKind} from './evaluation.mjs';

export function typeIssues(timelines,catalog){
  const issues=[];
  const graph=paths(timelines);
  for(const [timeline,path] of graph){
    let input='color';
    for(const [index,op] of path.entries()){
      const info=catalog.find(c=>c.kind===op.kind);
      if(!info?.accepts.includes(input)){
        issues.push({timeline,operation:op.id,input,needs:info?.accepts||[],name:info?.name||op.kind});break;
      }
      if(op.kind==='confirm'){
        const detector=kind=>catalog.find(c=>c.kind===kind)?.detector;
        const references=supportingIds(op),bad=references.find(id=>!detector(graph.get(id)?.at(-1)?.kind));
        if(!detector(path[index-1]?.kind)||!references.length||references.length<op.params.min_support||bad){
          issues.push({timeline,operation:op.id,input:'unconfirmed input',needs:['a primary detector and enough supporting final detectors'],name:info.name});break;
        }
      }
      input=outputKind(op.kind,input,op.params);
    }
  }
  return issues;
}

export function previewMove(timelines,timelineId,operationId,index,catalog){
  try{
    const timeline=timelines.find(t=>t.id===timelineId);
    if(!timeline)throw Error('Choose an approach first.');
    const source=timeline.operations.findIndex(o=>o.id===operationId);
    if(source<0)throw Error('This is a shared step. Edit its parent or make an independent copy.');
    if(index<0||index>=timeline.operations.length)throw Error(index<0?'Already the first editable step.':'Already the last step.');
    const next=moveOperation(timelines,timelineId,operationId,index);
    const before=paths(timelines),after=paths(next);
    const affected=timelines.filter(t=>t.id!==timelineId&&(JSON.stringify(before.get(t.id).map(o=>o.id))!==JSON.stringify(after.get(t.id).map(o=>o.id))||JSON.stringify([...dependencyIds(timelines,t.id)])!==JSON.stringify([...dependencyIds(next,t.id)]))).map(t=>({id:t.id,name:t.name}));
    const issues=typeIssues(next,catalog),oldIssues=typeIssues(timelines,catalog);
    const newIssues=issues.filter(issue=>!oldIssues.some(old=>old.timeline===issue.timeline&&old.operation===issue.operation&&old.input===issue.input));
    const issue=newIssues[0];
    return {allowed:!issue,next,affected,issues,reason:issue?`${issue.name} needs ${issue.needs.join(' or ')}, but would receive ${issue.input}. This move would break ${new Set(newIssues.map(i=>i.timeline)).size} pipeline${new Set(newIssues.map(i=>i.timeline)).size===1?'':'s'}.`:affected.length?`Also updates ${affected.map(t=>t.name).join(', ')} through shared steps or confirmation.`:'Only this pipeline changes.'};
  }catch(error){return {allowed:false,reason:error.message,affected:[],issues:[]};}
}

export function gapIndex(sourceIndex,gap){return gap>sourceIndex?gap-1:gap;}

export function independentCopy(timelines,timelineId){
  const source=timelines.find(t=>t.id===timelineId),resolved=paths(timelines).get(timelineId);
  if(!source)throw Error('Choose an approach to copy.');
  if(resolved.some(op=>op.kind==='confirm'))throw Error('This pipeline confirms other branches. Duplicate its image-processing steps separately to keep those dependencies explicit.');
  if(resolved.length>12)throw Error('Independent copies currently support at most 12 steps. Shorten this path first.');
  const result=clone(timelines),id=uid('timeline');
  result.push({id,name:`${source.name.slice(0,75)} · independent`,parent_id:null,fork_after:null,rationale:'Independent copy. Edits do not change the original approach.',operations:resolved.map(op=>({...clone(op),id:uid('op')}))});
  paths(result);return {timelines:result,id};
}
