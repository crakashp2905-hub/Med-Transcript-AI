import type {Fact} from './facts';
import type {Segment} from './workspaceTypes';

export type ClinicalDraftSnapshot={
 scope:string;
 transcript_id:string;
 note_id:string|null;
 segments:Segment[];
 facts:Fact[];
 english:boolean;
 complete:boolean;
 reviewReason:string;
 correction:string;
 updated_at:number;
};

const DATABASE='med-transcript-clinical-drafts-v1';

function open():Promise<IDBDatabase>{
 return new Promise((resolve,reject)=>{
  const request=indexedDB.open(DATABASE,1);
  request.onupgradeneeded=()=>{if(!request.result.objectStoreNames.contains('drafts'))request.result.createObjectStore('drafts',{keyPath:'scope'});};
  request.onsuccess=()=>resolve(request.result);
  request.onerror=()=>reject(request.error||new Error('Local draft storage could not be opened.'));
 });
}

function transact<T>(mode:IDBTransactionMode,run:(store:IDBObjectStore,done:(value:T)=>void)=>void):Promise<T>{
 return open().then(db=>new Promise((resolve,reject)=>{
  const tx=db.transaction('drafts',mode),store=tx.objectStore('drafts');let result:T;
  tx.oncomplete=()=>{db.close();resolve(result);};
  tx.onerror=tx.onabort=()=>{db.close();reject(tx.error||new Error('Local draft storage failed.'))};
  try{run(store,value=>{result=value;});}catch(error){tx.abort();db.close();reject(error);}
 }));
}

export function readClinicalDraft(scope:string):Promise<ClinicalDraftSnapshot|null>{
 return transact('readonly',(store,done)=>{const request=store.get(scope);request.onsuccess=()=>done((request.result as ClinicalDraftSnapshot|undefined)||null);});
}

export function writeClinicalDraft(draft:ClinicalDraftSnapshot):Promise<void>{
 return transact('readwrite',(store,done)=>{store.put(draft);done(undefined);});
}

export function deleteClinicalDraft(scope:string):Promise<void>{
 return transact('readwrite',(store,done)=>{store.delete(scope);done(undefined);});
}
