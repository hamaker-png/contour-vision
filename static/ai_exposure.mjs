// Monotonic evidence use: encoded bytes plus exact decoded pixels where available.
const digest=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(b=>b.toString(16).padStart(2,'0')).join('');
async function pixelHash(data){
  if(typeof createImageBitmap==='undefined'||typeof OffscreenCanvas==='undefined'||!data.startsWith('data:image/'))return null;
  const [header,encoded]=data.split(',');const bytes=Uint8Array.from(atob(encoded),c=>c.charCodeAt(0));
  const image=await createImageBitmap(new Blob([bytes],{type:header.split(':')[1].split(';')[0]}));
  try{const canvas=new OffscreenCanvas(image.width,image.height),ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.fillStyle='white';ctx.fillRect(0,0,image.width,image.height);ctx.drawImage(image,0,0);const pixels=ctx.getImageData(0,0,image.width,image.height).data;const input=new Uint8Array(8+pixels.length);new DataView(input.buffer).setUint32(0,image.width);new DataView(input.buffer).setUint32(4,image.height);input.set(pixels,8);return digest(input);}finally{image.close();}
}
export class ExposureLedger {
  constructor(hashPixels=pixelHash){this.keys=new Map();this.pixelKeys=new Map();this.pending=new Map();this.submitted=new Set();this.tuned=new Set();this.unknown=new Set();this.hashPixels=hashPixels;this.decodeQueue=Promise.resolve();}
  async prepare(samples){
    for(const sample of samples){
      if(this.keys.has(sample.data))continue;
      if(!this.pending.has(sample.data)){
        const pixels=this.decodeQueue.then(()=>this.hashPixels(sample.data));this.decodeQueue=pixels.catch(()=>{});
        this.pending.set(sample.data,Promise.all([digest(new TextEncoder().encode(sample.data)),pixels]));
      }
      try{const [key,pixels]=await this.pending.get(sample.data);this.keys.set(sample.data,key);if(pixels)this.pixelKeys.set(sample.data,pixels);this.linkKnownKeys(sample);}finally{this.pending.delete(sample.data);}
    }
  }
  retain(samples){
    const data=new Set(samples.map(sample=>sample.data));
    for(const key of this.keys.keys())if(!data.has(key)){this.keys.delete(key);this.pixelKeys.delete(key);}
  }
  sampleKeys(sample){return [this.keys.get(sample.data),this.pixelKeys.get(sample.data)].filter(Boolean);}
  linkKnownKeys(sample){
    const keys=this.sampleKeys(sample);
    for(const field of ['submitted','tuned','unknown'])if(keys.some(key=>this[field].has(key)))for(const key of keys)this[field].add(key);
  }
  mark(samples,collection){
    for(const sample of samples.filter(s=>s.split==='train')){
      const keys=this.sampleKeys(sample);if(!keys.length)throw Error('Image provenance was not prepared.');
      for(const key of keys){collection.add(key);this.unknown.delete(key);}
    }
  }
  markSubmitted(samples){this.mark(samples,this.submitted);}
  markTuned(samples){this.mark(samples,this.tuned);}
  status(sample){
    const keys=this.sampleKeys(sample);
    return !keys.length?'unknown':keys.some(k=>this.submitted.has(k))?'submitted':keys.some(k=>this.tuned.has(k))?'tuned':keys.some(k=>this.unknown.has(k))?'unknown':'unseen';
  }
  merge(metadata,samples){
    if(metadata==null){for(const sample of samples)for(const key of this.sampleKeys(sample))this.unknown.add(key);return;}
    const fields=metadata.version===1?['submitted','unknown']:['submitted','unknown','tuned'];
    if(![1,2].includes(metadata.version)||!fields.every(field=>Array.isArray(metadata[field])&&metadata[field].every(key=>typeof key==='string'&&/^[a-f0-9]{64}$/.test(key))))throw Error('The saved AI exposure history is invalid. The current project is unchanged.');
    for(const field of fields)metadata[field].forEach(key=>this[field].add(key));
    for(const sample of samples)this.linkKnownKeys(sample);
  }
  save(){return {version:2,submitted:[...this.submitted],tuned:[...this.tuned],unknown:[...this.unknown].filter(key=>key&&!this.submitted.has(key)&&!this.tuned.has(key))};}
}
