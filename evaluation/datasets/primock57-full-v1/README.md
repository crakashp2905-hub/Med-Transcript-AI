# Full consultation development cases

Three English PriMock57 consultations, day1 consultations 11–13, total **1,899.6 seconds (31m39.6s)**. Individual durations: 803.28, 471.96 and 624.36 seconds. All 384 nonempty reference turns are retained, including flagged uncertainty and both source roles. These consultation groups were absent from the earlier 118-clip screen; this is development data, not a clinician-adjudicated acceptance holdout.

Rebuild from the pinned licensed source with:

```powershell
.\.venv\Scripts\python.exe -m services.prepare_full_consultations
```

This needs public network access and the media extra. Originals, annotations, normalized tracks and mixed full-length audio stay under ignored `data/datasets/primock57-full-v1`. The committed manifest records source/annotation/audio SHA-256 values and original-timeline reference turns; `lock.json` freezes its bytes and the 5% requirement. Do not edit references after inspecting candidate output. Retain the CC BY 4.0 license and attribution on redistribution.

Mixing follows upstream track clocks, averaging the two channels and padding the shorter track. Source-channel doctor/patient labels are reference metadata, not predicted diarization. An independent reviewer must check synchronization, overlaps, uncertain words and role attribution. No claim of speaker, site, device or noise independence is made. Independent clinical annotation and a separate untouched acceptance cohort require a clinical owner.
