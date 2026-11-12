const assert = require('node:assert/strict');
const {test} = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require(process.env.TS_COMPILER_PATH || 'typescript');
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/lib/backend.ts'),'utf8'), {
  compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}
}).outputText;

function client(fetch) {
  const storage=new Map(),exports={};
  vm.runInNewContext(code,{exports,process:{env:{NEXT_PUBLIC_API_URL:'http://127.0.0.1:8000/'}},fetch,
    localStorage:{getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v)},
    crypto:require('node:crypto').webcrypto,AbortSignal,URLSearchParams,Uint8Array,console});
  return {api:exports,storage};
}
function response(body,ok=true,status=200){return {ok,status,json:async()=>body};}

test('catalog requests use configured URL and do not send a private token',async()=>{
  let seen;const {api}=client(async(url,opts)=>{seen={url,opts};return response([]);});
  await api.districts();assert.equal(seen.url,'http://127.0.0.1:8000/api/v1/districts');assert.equal(seen.opts.headers['X-Device-Token'],undefined);
});
test('farm saves use PUT with one persistent random browser token',async()=>{
  const calls=[];const {api}=client(async(url,opts)=>{calls.push({url,opts});return response({farm:null});});
  await api.getFarm();await api.saveFarm({district_id:'dhaka',fields:{water:'Rainfed'}});
  const token=calls[0].opts.headers['X-Device-Token'];assert.match(token,/^[0-9a-f]{64}$/);
  assert.equal(calls[1].opts.headers['X-Device-Token'],token);assert.equal(calls[1].opts.method,'PUT');
  assert.equal(JSON.parse(calls[1].opts.body).district_id,'dhaka');assert.ok(!calls[1].url.includes(token));
});
test('advisories encode selection and preserve backend Bangla errors',async()=>{
  let seen;const {api}=client(async url=>{seen=url;return response({detail:{message:'No data',message_bn:'তথ্য নেই'}},false,503);});
  await assert.rejects(()=>api.advisory('chattogram','mustard','bn'),{message:'তথ্য নেই'});
  assert.ok(seen.includes('district=chattogram&crop=mustard&lang=bn'));
});
test('network failure gives an actionable connection error',async()=>{
  const {api}=client(async()=>{throw new TypeError('Failed to fetch');});
  await assert.rejects(()=>api.getFarm(),/backend is running on port 8000/);
});
test('caller cancellation is preserved instead of shown as a server failure',async()=>{
  const stop=new AbortController();stop.abort();const reason=new Error('cancelled');
  const {api}=client(async()=>{throw reason;});
  await assert.rejects(()=>api.districts(stop.signal),err=>err===reason);
});
