type Finding={finding_id:string;code:string;message:string;severity:string;fact_id:string|null};
const title=(value:string)=>value.replaceAll('_',' ');
export function VerificationWarnings({findings,review}:{findings:Finding[];review:(id:string|null)=>void}){
 const groups=['critical','major','minor','info'];
 const group=(severity:string)=>groups.includes(severity)?severity:severity==='warning'?'minor':'major';
 return <div className="verification-groups">{groups.map(severity=>{
  const items=findings.filter(item=>group(item.severity)===severity);
  return items.length?<section key={severity} aria-label={`${severity} verification issues`}><h3>{title(severity)} <span className="count">{items.length}</span></h3>{items.map(item=><div className="finding" key={item.finding_id}><span className={`severity ${severity}`}>{item.severity}</span><h4>{title(item.code)}</h4><p>{item.message}</p>{item.fact_id&&<button onClick={()=>review(item.fact_id)}>Review statement and source</button>}</div>)}</section>:null;
 })}</div>;
}
