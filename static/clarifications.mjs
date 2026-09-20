// Clarification answers belong to the project, not to a particular rendered question list.
export function updateAnswer(answers,question,answer){
  const next=answers.filter(item=>item.question!==question);
  if(answer.trim())next.push({question,answer});
  return next;
}

export function formatAnswers(answers,requirements=''){
  return [...answers.filter(item=>item.answer.trim()).map(item=>`${item.question}: ${item.answer.trim()}`),requirements.trim()].filter(Boolean).join('\n');
}

export function checkedAnswers(answers,requirements=''){
  const text=formatAnswers(answers,requirements);
  if(text.length>6000)throw Error(`Answers and other requirements use ${text.length.toLocaleString()} of 6,000 characters. Shorten them before asking AI; nothing has been discarded.`);
  return text;
}

export async function familyFingerprint(samples){
  const family=samples.filter(s=>s.split==='train').map(({id,name,data,labeled,boxes})=>({id,name,data,labeled,boxes}));
  const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(family)));
  return [...new Uint8Array(digest)].map(byte=>byte.toString(16).padStart(2,'0')).join('');
}

export function readGuidance(value){
  if(value==null)return {answers:[],discovery:null};
  const string=(s,max)=>typeof s==='string'&&s.length<=max;
  if(typeof value!=='object'||!Array.isArray(value.answers)||!value.answers.every(a=>a&&string(a.question,6000)&&string(a.answer,1000000)))throw Error('The saved question answers are invalid. The current project is unchanged.');
  const answers=value.answers.reduce((all,a)=>updateAnswer(all,a.question,a.answer),[]);
  let discovery=null;
  if(value.discovery!=null){
    const d=value.discovery;
    if(!string(d.observations,20000)||!['important_features','questions','limitations'].every(key=>Array.isArray(d[key])&&d[key].length<=40&&d[key].every(s=>string(s,6000)))||!Number.isInteger(d.imageCount)||d.imageCount<1||d.imageCount>12||!/^([a-f0-9]{64})$/.test(d.familyFingerprint))throw Error('The saved image analysis is invalid. The current project is unchanged.');
    discovery={observations:d.observations,important_features:[...d.important_features],questions:d.questions.slice(0,4),limitations:[...d.limitations],imageCount:d.imageCount,familyFingerprint:d.familyFingerprint};
  }
  return {answers,discovery};
}
