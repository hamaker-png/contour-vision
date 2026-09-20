const fingerprint=op=>JSON.stringify([op.kind,op.params]);
export class ParameterDrafts{
  entries=new Map();
  record(op,values){
    const changed=Object.entries(values).some(([key,value])=>value!==(typeof value==='boolean'?Boolean(op.params[key]):String(op.params[key])));
    if(changed)this.entries.set(op.id,{base:fingerprint(op),values:structuredClone(values)});else this.entries.delete(op.id);
  }
  read(op){if(!op)return null;const draft=this.entries.get(op.id);return draft?.base===fingerprint(op)?structuredClone(draft.values):null;}
  reconcile(timelines){const ops=new Map(timelines.flatMap(t=>t.operations).map(op=>[op.id,op]));for(const [id,draft] of this.entries)if(!ops.has(id)||draft.base!==fingerprint(ops.get(id)))this.entries.delete(id);}
  delete(id){this.entries.delete(id);}
  clear(){this.entries.clear();}
  get size(){return this.entries.size;}
}
