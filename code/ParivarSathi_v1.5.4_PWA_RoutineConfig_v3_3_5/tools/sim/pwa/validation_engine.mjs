export function valueAt(root,dotted){
  let cur=root;
  if(!dotted) return cur;
  for(const token of dotted.split('.')){
    if(Array.isArray(cur)) cur=cur[Number(token)];
    else if(cur && typeof cur==='object' && Object.prototype.hasOwnProperty.call(cur,token)) cur=cur[token];
    else throw new Error(`path missing: ${dotted}`);
  }
  return cur;
}
export function sameValue(a,b){return JSON.stringify(a)===JSON.stringify(b)}
export function itemMatches(item,where){return Object.entries(where||{}).every(([k,v])=>{try{return sameValue(valueAt(item,k),v)}catch(_){return false}})}
export function evaluateAssertion(snapshot,a){
  try{
    if(a.path!==undefined){
      const actual=valueAt(snapshot,a.path);
      if('eq' in a)return {pass:sameValue(actual,a.eq),detail:`${a.path}=${JSON.stringify(actual)} expected ${JSON.stringify(a.eq)}`};
      if('ne' in a)return {pass:!sameValue(actual,a.ne),detail:`${a.path}=${JSON.stringify(actual)} expected != ${JSON.stringify(a.ne)}`};
      if('ge' in a)return {pass:actual>=a.ge,detail:`${a.path}=${actual} expected >= ${a.ge}`};
      if('gt' in a)return {pass:actual>a.gt,detail:`${a.path}=${actual} expected > ${a.gt}`};
      if('le' in a)return {pass:actual<=a.le,detail:`${a.path}=${actual} expected <= ${a.le}`};
      if('lt' in a)return {pass:actual<a.lt,detail:`${a.path}=${actual} expected < ${a.lt}`};
      if(a.truthy===true)return {pass:!!actual,detail:`${a.path}=${JSON.stringify(actual)} expected truthy`};
      if(a.falsy===true)return {pass:!actual,detail:`${a.path}=${JSON.stringify(actual)} expected falsy`};
    }
    if(a.select!==undefined){
      const items=valueAt(snapshot,a.select);
      if(!Array.isArray(items))return {pass:false,detail:`${a.select} is not a list`};
      const n=items.filter(x=>itemMatches(x,a.where||{})).length;
      if('count' in a)return {pass:n===a.count,detail:`${a.select} matches=${n} expected=${a.count} where=${JSON.stringify(a.where||{})}`};
      if('min_count' in a)return {pass:n>=a.min_count,detail:`${a.select} matches=${n} expected>=${a.min_count} where=${JSON.stringify(a.where||{})}`};
    }
    if(a.order!==undefined){
      const spec=a.order,items=valueAt(snapshot,spec.path),field=spec.field||'kind';
      const actual=items.slice(0,spec.prefix.length).map(x=>valueAt(x,field));
      return {pass:sameValue(actual,spec.prefix),detail:`order=${JSON.stringify(actual)} expected=${JSON.stringify(spec.prefix)}`};
    }
    return {pass:false,detail:`unsupported assertion ${JSON.stringify(a)}`};
  }catch(err){return {pass:false,detail:err.message}}
}
export function evaluateScenario(payload){
  const checks=(payload.scenario.assertions||[]).map(a=>evaluateAssertion(payload.state,a));
  return {...payload,checks,pass:!!payload.steps_passed && checks.every(x=>x.pass)};
}
export function renderValidationRow(result){
  return `<div class="validation-row ${result.pass?'pass':'fail'}" data-validation-case="${result.scenario.id}" data-case-status="${result.pass?'PASS':'FAIL'}"><b>${result.pass?'PASS':'FAIL'}</b><span>${result.scenario.id}</span></div>`;
}
