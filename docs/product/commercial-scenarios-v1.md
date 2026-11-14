# Commercial scenarios v1

**Status:** internal planning hypotheses; not customer research, a price quote, a forecast, or a service commitment.
**Scope:** English-language documentation assistance for small outpatient clinics. Real-patient use and deployment remain unauthorized.

## Initial customer profile and roles

The initial profile to validate is a single-site outpatient practice with 3–10 clinicians, an owner or practice manager who controls purchasing, and an IT-capable administrator who can manage workstations, access, storage and recovery. The workflow assumes English documentation and a clinician who reviews and signs every note. It does not assume that the clinic has approved this product or that clinicians want to adopt it.

| Role | Primary concern | Product responsibility |
|---|---|---|
| Physician or other authorized clinician | Correct, reviewable documentation | Review source, correct proposals, resolve warnings and approve the exact saved version |
| Scribe | Efficient preparation under clinician direction | Organize source and proposed note content; never approve on the clinician’s behalf |
| Practice owner or manager | Workflow fit, price and continuity | Select a proposed commercial model and provide purchasing feedback |
| Administrator or IT operator | Accounts, devices, storage, updates and recovery | Configure the approved workspace and follow tested operator procedures |
| Viewer or records recipient | Readable, attributable output | View or receive only the records allowed by the assigned role |

These roles describe the proposed buyer and user group. They are not an authorization model for real clinic data; deployment identity, retention and security still need institutional review.

## Positioning hypotheses

Proposed positioning: **English encounter documentation with source-linked review, version-bound approval and a local-first operating option.** The differentiators are product design hypotheses, not superiority claims.

| Dimension | Product hypothesis | Evidence available locally | External comparison still needed |
|---|---|---|---|
| Workflow | Keep capture, transcript, evidence, note correction and approval in one review path | Synthetic browser journeys exercise the scripted flow | Observe real clinic workflows and compare current alternatives |
| Traceability | Link supported statements to source evidence and bind approval to saved versions | Automated provenance and approval tests | Validate whether clinicians find the links useful and whether receiver workflows preserve them |
| Privacy | Offer a local-first mode with explicit processing boundaries | Offline and loopback-only engineering tests | Institution security/privacy review, deployment assessment and current vendor data-flow research |
| Cost | Make local hardware, energy, support and storage assumptions visible | An illustrative calculator and scenario formulas; actual operating cost is not measured | Metered workloads, support labor, procurement inputs and source-audited competitor prices |

No competing product capability, price, trial, market share or privacy practice is asserted here. A public comparison requires a dated, source-audited claim pack before it is used in sales material.

## Illustrative pricing ladders

The figures below use **notional planning units (NPU)** only. NPU has no currency conversion, tax, purchasing-power or market-price meaning. The low/base/high columns are deliberately broad values for interview and sensitivity-test scenarios; they are not recommended prices.

| Model | Low | Base | High | Calculation and scope assumption |
|---|---:|---:|---:|---|
| Per-clinician subscription | 40 NPU / clinician / month | 80 NPU / clinician / month | 140 NPU / clinician / month | One clinician seat; excludes hardware, local setup and custom integration |
| Five-seat clinic bundle | 180 NPU / clinic / month | 340 NPU / clinic / month | 560 NPU / clinic / month | Five seats at the corresponding per-seat scenario with 10%, 15% or 20% bundle discount |
| Offline site deployment | 1,500 NPU one-time setup | 3,000 NPU one-time setup | 6,000 NPU one-time setup | Setup hypothesis for one site and up to three configured workstations; hardware and EHR work excluded |
| Offline annual license and support | 2,160 NPU / year | 4,080 NPU / year | 6,720 NPU / year | Five-seat bundle annualized at 12 months; draft support fee is an additional 20% of that annual license |

For a five-seat offline site, the illustrative first-year total before tax, hardware, storage and integration is setup + annual license + 20% support: **4,092 / 7,896 / 14,064 NPU** in the low/base/high cases. Renewal is license plus the support assumption. No gross margin or payback is calculated because internal deployment costs are not measured.

The pricing exercise should record buyer role, preferred unit, acceptable setup burden, renewal expectations and reasons for rejection. Replace every NPU value only after interviews and a sourced cost model; do not convert these values into public prices.

## Cost model and measurement plan

For each completed encounter, calculate a cost only when its inputs have a measured or explicitly assumed basis:

`successful encounter cost = (measured energy + allocated hardware amortization + measured storage + allocated support and operations) / successful approved exports`

Keep inference time, peak RAM, energy, support time and storage as separate fields. Do not infer a zero cost when a field is missing. The existing [local unit-economics note](local-unit-economics-v1.md) contains illustrative workstation inputs, not measured costs; it should be replaced with metered power, recorded local runs, site tariffs, procurement records and operating logs before a commercial decision.

## Successful-encounter analytics

The proposed internal dashboard should count encounters reaching an **approved export** and show the funnel stages: created, capture completed, transcript ready, draft ready, clinician-approved and export delivered. Show retries, cancellation, manual fallback, recovery and failure counts beside successful counts so the dashboard cannot hide unsuccessful work.

Use encounter IDs only as short-lived deduplication keys, then aggregate. Do not include audio, transcript text, note text, medication names, patient identifiers or free-text error messages. Separate scripted test telemetry from any future clinic telemetry. Do not call an approved export a clinically correct encounter or a productivity gain.

## Draft support objectives

These are internal planning targets for a future staffed service, not a current SLA or an external commitment. They start only after a support owner, coverage hours, escalation path and monitoring are funded and tested.

| Severity | Example | Proposed initial response target | Proposed update cadence |
|---|---|---:|---|
| P1 | Suspected data exposure, corrupted approval, or clinic-wide inability to recover encounters | 4 staffed business hours | Every staffed business day until contained |
| P2 | A core workflow fails for one user but a safe manual fallback exists | 1 staffed business day | Every 2 staffed business days |
| P3 | Non-blocking usability or configuration issue | 3 staffed business days | At triage or the next release note |

Response means acknowledgment and triage, not resolution. No 24/7 coverage, uptime promise, recovery-time objective or response guarantee is offered. Before publication, replace targets with operating evidence and an accountable support owner.

## Onboarding and demo package

Use the existing [offline runbook](../demo-runbook-offline.md), [troubleshooting guide](../troubleshooting.md), [support and launch controls](product-commercial-operations-v1.md), and [synthetic browser evidence](../../evaluation/reports/offline-product-acceptance-b3adce0.json) for an internal walkthrough. The demo should show a synthetic encounter, source playback, a blocked inconsistency, correction, version-bound approval, export, and one recoverable failure. It must keep scripted results distinct from clinical validation and must not accept patient data.

## Validation gates

- Interview small-clinic buyers, clinicians, scribes and IT operators separately; record consent and distinguish observed feedback from hypotheses.
- Source-audit public competitor claims and capture access dates before making comparisons.
- Measure workstation resources, support labor, storage and recovery using approved synthetic workflows and named hardware.
- Test the dashboard against successful and failed synthetic journeys, including manual fallback and retries.
- Approve support coverage, security, retention and deployment procedures before proposing any clinic pilot.

Until these gates are complete, the customer profile, position, price ladders, cost model and support objectives remain internal hypotheses.
