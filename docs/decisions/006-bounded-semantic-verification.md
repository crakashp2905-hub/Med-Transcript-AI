# ADR 006: Bounded whole-note advisory verification

Status: implemented for local synthetic evaluation.

The semantic verifier processes every non-excluded, evidence-linked saved fact by default. It sends at most 20 claims per local model call and merges only an exact set of unique fact IDs. A missing, duplicated, or invented ID, an unsupported quotation, or any failed batch rejects the entire request; no partial proposal is saved. The upper bound is the 300-fact note limit. An optional explicit fact selection remains available for investigations and is marked as partial.

The request schema now allows up to 300 selected fact IDs. The frozen v1 OpenAPI snapshot remains unchanged; its contract test permits this single declared maximum-item change and still rejects other route or schema drift.

Each saved proposal records checked and unchecked evidence-linked IDs, clinician-entered facts without source evidence, excluded IDs, total note fact count, batch count, and a completion status restricted to its evidence-linked scope. A source-free clinician addition cannot be called model-verified. Model output stays an unapprovable advisory proposal and cannot clear deterministic findings or clinician approval requirements.

The local model may need up to 15 sequential bounded calls for a 300-fact note. Each model call has its existing timeout; overall latency and successful model coverage are not yet established. Synthetic fake-provider tests check batching and failure behavior without claiming model accuracy. No paid calls or model downloads are used.
