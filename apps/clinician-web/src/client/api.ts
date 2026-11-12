import {ApiError,safeErrorCode} from "./errorCodes";
export async function request(path:string, options:RequestInit, key:string, csrf:string, onUnauthorized:()=>void){
   const method=(options.method||'GET').toUpperCase();
   const headers=new Headers(options.headers);
   if(key)headers.set('Authorization',`Bearer ${key}`);
   if(csrf)headers.set('X-CSRF-Token',csrf);
   if(!(options.body instanceof Blob)&&!headers.has('Content-Type'))headers.set('Content-Type','application/json');
   if(!['GET','HEAD','OPTIONS'].includes(method)&&!headers.has('Idempotency-Key'))headers.set('Idempotency-Key',crypto.randomUUID());
   const response=await fetch(path,{...options,method,credentials:'same-origin',headers});
   if(response.status===401)onUnauthorized();
   if(!response.ok){let code:unknown='request_failed';try{code=(await response.json()).code;}catch{}throw new ApiError(safeErrorCode(code),response.status);}
   return response;
 }
