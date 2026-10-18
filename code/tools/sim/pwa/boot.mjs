import {normalizeRuntimeConfig} from './runtime_mode.mjs';

const runtime=normalizeRuntimeConfig(window.PARIVAR_SAATHI_RUNTIME,window.location.origin);
if(runtime.mode==='local-simulator') await import('./app.js');
else await import('./connected_lite.mjs');
