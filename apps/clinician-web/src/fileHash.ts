import {sha256} from '@noble/hashes/sha2.js';
// Read Blob-backed recordings incrementally; never allocate the complete PCM file.
export async function fileHash(file:Blob):Promise<string>{
 const hash=sha256.create(),reader=file.stream().getReader();let yielded=0;
 try{while(true){const {value,done}=await reader.read();if(done)break;hash.update(value);yielded+=value.byteLength;if(yielded>=4*1024*1024){yielded=0;await new Promise(resolve=>setTimeout(resolve,0));}}return Array.from(hash.digest()).map(x=>x.toString(16).padStart(2,'0')).join('');}
 finally{reader.releaseLock();}
}
