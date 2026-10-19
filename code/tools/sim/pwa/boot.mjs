import {normalizeRuntimeConfig} from './runtime_mode.mjs';

const runtime=normalizeRuntimeConfig(window.PARIVAR_SAATHI_RUNTIME,window.location.origin);
const stylesheet=document.createElement('link');
stylesheet.rel='stylesheet';
stylesheet.href=runtime.mode==='local-simulator'?'styles.css':'caregiver.css';
await new Promise((resolve,reject)=>{
  stylesheet.onload=resolve;
  stylesheet.onerror=()=>reject(new Error('Caregiver stylesheet could not be loaded'));
  document.head.append(stylesheet);
});
if(runtime.mode==='local-simulator') await import('./app.js');
else await import('./connected_lite.mjs');
