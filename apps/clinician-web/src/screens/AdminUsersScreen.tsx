import {useEffect,useMemo,useState} from 'react';

type WorkspaceUser={email:string;user_id:string;clinician_id:string;tenant_id:string;role:string};
type AuditEvent={action:string;actor_user_id:string;target_user_id:string;time:string};
type Diagnostics={schema_version:string;runtime:{python:string;platform:string;node:boolean;npm:boolean;docker:boolean;psql:boolean};storage:{status:string;free_bytes:number|null;backup_restore:string};frontend_dependencies:string;offline_mode:string;model_inference_performed:boolean;external_services_contacted:boolean;patient_or_encounter_data_included:boolean};
type Role='physician'|'scribe'|'administrator'|'viewer';
type Props={request:(path:string,init?:RequestInit)=>Promise<any>;logout:()=>Promise<void>;userId:string};

function diagnosticFollowUps(diagnostics:Diagnostics){
 const actions:string[]=[];
 if(diagnostics.offline_mode!=='enabled')actions.push('Offline mode is not confirmed. Set MED_TRANSCRIPT_OFFLINE=1 in the local service configuration, restart it, then rerun diagnostics.');
 if(diagnostics.frontend_dependencies!=='available')actions.push('Browser dependencies are missing. Restore the approved offline application package or ask the installer to repair this installation.');
 if(diagnostics.storage.status!=='measured'||diagnostics.storage.free_bytes===null)actions.push('Disk headroom could not be measured. Check the application volume and its permissions using the operating system tools.');
 if(diagnostics.storage.backup_restore!=='validated')actions.push('Backup and restore have not been validated here. Follow the operator runbook to create a new backup and test restore in a separate recovery directory.');
 if(!diagnostics.runtime.python)actions.push('Python runtime details are unavailable. Ask the installer to verify the application runtime.');
 return actions;
}

export function AdminUsersScreen({request,logout,userId}:Props){
 const [users,setUsers]=useState<WorkspaceUser[]>([]),[events,setEvents]=useState<AuditEvent[]>([]);
 const [email,setEmail]=useState(''),[role,setRole]=useState<Role>('physician'),[assigned,setAssigned]=useState('');
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
 const [diagnostics,setDiagnostics]=useState<Diagnostics|null>(null),[diagnosticsBusy,setDiagnosticsBusy]=useState(false),[diagnosticsError,setDiagnosticsError]=useState('');
 const physicians=useMemo(()=>users.filter(user=>user.role==='physician'||user.role==='clinician'),[users]);
 async function refresh(){
  setBusy(true);setError('');
  try{const [userResult,auditResult]=await Promise.all([request('/v1/admin/users'),request('/v1/admin/users/audit')]);setUsers(userResult.users);setEvents(auditResult.events);}
  catch(reason){setError(reason instanceof Error?reason.message:'Workspace accounts could not be loaded.');}
  finally{setBusy(false);}
 }
 useEffect(()=>{void refresh();},[]);
 async function runDiagnostics(){setDiagnosticsBusy(true);setDiagnosticsError('');try{setDiagnostics(await request('/v1/admin/diagnostics'));}catch(reason){setDiagnosticsError(reason instanceof Error?reason.message:'Local diagnostics could not be loaded.');}finally{setDiagnosticsBusy(false);}}
 async function addUser(event:React.FormEvent){
  event.preventDefault();setBusy(true);setError('');setNotice('');
  try{
   const body:{email:string;role:Role;assigned_clinician_id?:string}={email,role};
   if(role==='scribe'||role==='viewer')body.assigned_clinician_id=assigned;
   await request('/v1/admin/users',{method:'POST',body:JSON.stringify(body)});
   setEmail('');setAssigned('');setNotice('Invitation added. Access begins after the invited account signs in.');await refresh();
  }catch(reason){setError(reason instanceof Error?reason.message:'Invitation could not be added.');}
  finally{setBusy(false);}
 }
 async function removeUser(user:WorkspaceUser){
  setBusy(true);setError('');setNotice('');
  try{await request(`/v1/admin/users/${user.user_id}`,{method:'DELETE'});setNotice('Account removed and active sessions revoked.');await refresh();}
  catch(reason){setError(reason instanceof Error?reason.message:'Account could not be removed.');}
  finally{setBusy(false);}
 }
 return <main className="content" aria-label="Workspace account administration">
  <section className="panel">
   <div className="panel-heading"><div><h1>Workspace accounts</h1><p className="muted">Manage invitations for this clinic. Administrator access cannot open encounter content.</p></div><button onClick={()=>void logout()}>Sign out</button></div>
   <p className="callout">Account invitations and removals are recorded in the workspace membership audit. Assign each scribe to a physician. A physician must approve every clinical note.</p>
  <section className="panel" aria-label="Clinic operator diagnostics">
   <div className="panel-heading"><div><h2>Clinic operator diagnostics</h2><p className="muted">Read-only local checks. They do not inspect encounter content, run models, or contact external services.</p></div><button disabled={diagnosticsBusy} onClick={()=>void runDiagnostics()}>{diagnosticsBusy?'Checking…':'Run local diagnostics'}</button></div>
   {diagnosticsError&&<p role="alert" className="error">{diagnosticsError}</p>}
   {diagnostics&&<div role="status" aria-label="Local diagnostic results"><p>Python {diagnostics.runtime.python} · {diagnostics.runtime.platform}</p><p>Browser dependencies: {diagnostics.frontend_dependencies} · offline mode: {diagnostics.offline_mode}</p><p>Disk headroom: {diagnostics.storage.status==='measured'&&diagnostics.storage.free_bytes!==null?`${(diagnostics.storage.free_bytes/1024**3).toFixed(1)} GB available`:'unavailable'}</p><p>Optional tools: Node {diagnostics.runtime.node?'available':'missing'}, npm {diagnostics.runtime.npm?'available':'missing'}, Docker {diagnostics.runtime.docker?'available':'missing'}, PostgreSQL client {diagnostics.runtime.psql?'available':'missing'}.</p><p>Backup/restore validation: {diagnostics.storage.backup_restore}. Model inference: not run. External services: not contacted. Patient or encounter data: not included.</p><h3>Recommended follow-up</h3><ul>{diagnosticFollowUps(diagnostics).map(action=><li key={action}>{action}</li>)}</ul></div>}
   <details><summary>Support and recovery commands</summary><p>Run commands from the installed application directory. Keep output local and remove identifiers before sharing support details.</p><p><strong>Read-only readiness report</strong><br/><code>python -m services.status_report</code></p><p><strong>Backup to a new destination</strong><br/><code>python -m services.maintenance backup --destination data/backups/snapshot-UNIQUE</code></p><p><strong>Restore into a separate recovery directory</strong><br/><code>python -m services.maintenance restore --source data/backups/snapshot-UNIQUE --destination data/recovery-UNIQUE --tombstones-from data/development.sqlite3</code></p><p>Restore checks do not run from this screen. Use a separate destination and consult the operator runbook before replacing a live workspace.</p></details>
  </section>
   {error&&<p role="alert" className="error">{error}</p>}{notice&&<p role="status" className="verified">{notice}</p>}
   <div className="table-scroll"><table><thead><tr><th>Email</th><th>Role</th><th>Assigned physician</th><th>Account ID</th><th>Action</th></tr></thead><tbody>
    {users.map(user=><tr key={user.user_id}><td>{user.email}</td><td>{user.role}</td><td>{physicians.find(item=>item.clinician_id===user.clinician_id)?.email||'—'}</td><td><code>{user.user_id.slice(0,8)}</code></td><td><button disabled={busy||user.user_id===userId} onClick={()=>void removeUser(user)}>Remove</button></td></tr>)}
   </tbody></table></div>
   <h2>Invite an account</h2>
   <form onSubmit={addUser} className="admin-user-form">
    <label>Email<input required type="email" autoComplete="off" value={email} onChange={event=>setEmail(event.target.value)}/></label>
    <label>Role<select value={role} onChange={event=>setRole(event.target.value as Role)}><option value="physician">Physician</option><option value="scribe">Scribe</option><option value="administrator">Administrator</option><option value="viewer">Viewer</option></select></label>
    {(role==='scribe'||role==='viewer')&&<label>Assigned physician<select required value={assigned} onChange={event=>setAssigned(event.target.value)}><option value="">Choose a physician</option>{physicians.map(user=><option key={user.user_id} value={user.clinician_id}>{user.email}</option>)}</select></label>}
    <button className="primary" disabled={busy||((role==='scribe'||role==='viewer')&&!assigned)} type="submit">Add invitation</button>
   </form>
   <h2>Account audit</h2>
   {events.length===0?<p className="muted">No account changes recorded.</p>:<ol>{events.slice().reverse().map((event,index)=><li key={`${event.time}-${index}`}>{event.action} · {event.time} · actor {event.actor_user_id.slice(0,8)} · account {event.target_user_id.slice(0,8)}</li>)}</ol>}
  </section>
 </main>;
}
