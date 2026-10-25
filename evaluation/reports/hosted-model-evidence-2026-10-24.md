# Would a paid model improve this project?

Possibly, but no hosted service has been measured on this project's frozen corpus. Price is not evidence of accuracy, and vendor benchmarks cannot be inserted into the local ranking.

Deepgram's current medical-model announcement reports 6.61% batch WER on its internal English medical test set of over 11,500 recordings, and 3.36% streaming WER on a different 10-hour English benchmark. Those are different tasks, datasets and scoring procedures. The streaming result does not establish that a batch call will meet this project's 5% normalized WER requirement. Source: [Deepgram medical-model update](https://deepgram.com/learn/introducing-nova-3-medical-multilingual).

AWS documents a dedicated medical dictation mode with specialty selection and custom vocabularies. These features make it a reasonable medical challenger, but do not supply a comparable WER result on our data. Source: [Amazon Transcribe Medical dictation](https://docs.aws.amazon.com/transcribe/latest/dg/transcribe-medical-dictation.html).

The next controlled hosted comparison would run Deepgram Nova-3 Medical and Amazon Transcribe Medical against exactly the same committed audio and references, record the returned model/version and request settings, retain all failures, and apply the unchanged scorer. Batch and streaming must be reported separately. Vocabulary hints must be fixed from independent development material, never derived from evaluation reference transcripts. Compare clinical drug/dose/unit/negation errors separately from overall WER.

No paid calls, credentials, service activation, audio uploads or spending-limit changes were authorized or performed in this run. Hosted candidates remain visible and unranked. A future paid comparison requires the user's explicit authorization and a spending limit.

Provider formatting matters for this verbatim corpus: Deepgram documents `filler_words=false` by default, while our references retain fillers. Its numerals and Smart Format features can also change number rendering. A future comparison must explicitly fix supported formatting/disfluency options before evaluation, record model-specific feature support, and keep the project scorer unchanged. Sources: [official API specification](https://github.com/deepgram/deepgram-api-specs/blob/main/openapi.yml), [numerals documentation update](https://developers.deepgram.com/changelog/2025/3/11).
