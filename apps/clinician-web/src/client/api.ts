import {ApiError,safeErrorCode} from "./errorCodes";
export async function request(path:string, options:RequestInit, key:string, csrf:string, onUnauthorized:()=>void){
   const response=await fetch(path,{...options,credentials:'same-origin',headers:{...(key?{Authorization:`Bearer ${key}`} : {}),...(csrf?{'X-CSRF-Token':csrf}:{}),...(options.body instanceof Blob?{}:{'Content-Type':'application/json'}),...options.headers}});
   if(response.status===401)onUnauthorized();
   if(!response.ok){let code:unknown='request_failed';try{code=(await response.json()).code;}catch{}throw new ApiError(safeErrorCode(code),response.status);}
   return response;
 }
