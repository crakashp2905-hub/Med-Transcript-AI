import fixture from '../../../data/demo-sample.json';

type DemoFixture={fixture_id:string;synthetic:true;segments:{start_ms:number;end_ms:number;role:string;text:string}[]};
const demo=fixture as DemoFixture;

export function InvestorDemo(){
 return <main className="investor-demo">
  <header><span className="brand-mark">m<span>+</span></span><div><strong>Med Transcript AI</strong><small>Investor preview · read only · no sign-in</small></div></header>
  <section className="investor-disclaimer" role="note"><strong>Synthetic scripted preview</strong><p>This page uses bundled synthetic text only. It does not process audio, call an AI model, create or approve a clinical record, or access workspace data. It is not evidence of ASR or clinical accuracy. Independent clinical validation is pending.</p></section>
  <div className="investor-title"><div><span className="eyebrow">ENGLISH OUTPATIENT DOCUMENTATION</span><h1>Keep every proposed statement connected to its source.</h1><p>Static walkthrough of the source-to-note review concept.</p></div><span className="readonly-badge">READ ONLY</span></div>
  <div className="investor-columns">
   <section className="investor-panel" aria-label="Scripted source excerpt"><div className="panel-heading"><h2>Scripted source excerpt</h2><span className="pill">{demo.fixture_id}</span></div><p className="muted">Source text supplied by a synthetic development fixture. Audio and ASR are unavailable in this preview.</p><ol className="investor-transcript">{demo.segments.map((segment,index)=><li key={index}><span>{(segment.start_ms/1000).toFixed(1)}–{(segment.end_ms/1000).toFixed(1)} s · {segment.role}</span><p>{segment.text}</p></li>)}</ol></section>
   <section className="investor-panel" aria-label="Evidence-linked note preview"><div className="panel-heading"><h2>Evidence-linked note preview</h2><span className="pill">UNAPPROVED DEMONSTRATION</span></div><p className="muted">Each display row repeats one scripted source statement with a direct reference. No extraction or drafting model ran.</p><ol className="investor-facts">{demo.segments.map((segment,index)=><li key={index}><p>{segment.text}</p><blockquote>Source {index+1} · {segment.role} · {(segment.start_ms/1000).toFixed(1)}–{(segment.end_ms/1000).toFixed(1)} s</blockquote></li>)}</ol><div className="investor-approval">Clinician approval: unavailable in this static preview</div></section>
  </div>
  <footer>Fixture scope: Bundled synthetic scripted text; not ASR output or human clinical gold. · No API requests or persistent writes occur on this page.</footer>
 </main>;
}
