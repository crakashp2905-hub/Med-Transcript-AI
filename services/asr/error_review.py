"""Build a local, read-only HTML review packet from frozen ASR runs."""

import argparse
import hashlib
import html
import json
import math
import os
import wave
from pathlib import Path


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_payload(manifest_path, report_paths, audio_root, output_path):
    manifest_path = Path(manifest_path).resolve()
    audio_root = Path(audio_root).resolve()
    output_path = Path(output_path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    samples = manifest.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("review_manifest_samples_required")
    by_id = {sample.get("sample_id"): sample for sample in samples}
    if None in by_id or len(by_id) != len(samples):
        raise ValueError("review_manifest_sample_ids_invalid")

    reports = []
    report_digests = []
    for report_path in sorted(map(Path, report_paths), key=lambda path: path.name):
        report_path = report_path.resolve()
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("manifest_sha256") != _sha256(manifest_path):
            raise ValueError("review_run_manifest_digest_mismatch")
        if not isinstance(report.get("model_revision"), str) or not isinstance(
            report.get("profile_sha256"), str
        ):
            raise ValueError("review_run_model_digest_missing")
        report_samples = report.get("samples")
        if not isinstance(report_samples, list):
            raise ValueError("review_run_samples_required")
        keyed = {sample.get("sample_id"): sample for sample in report_samples}
        if (
            None in keyed
            or len(keyed) != len(report_samples)
            or set(keyed) != set(by_id)
        ):
            raise ValueError("review_run_sample_coverage_mismatch")
        for sample_id, hypothesis in keyed.items():
            if hypothesis.get("reference") != by_id[sample_id].get("reference"):
                raise ValueError("review_run_reference_mismatch")
        reports.append((report_path.name, report, keyed))
        report_digests.append(
            {
                "file": report_path.name,
                "sha256": _sha256(report_path),
                "candidate_id": report.get("profile_id"),
                "model_revision": report["model_revision"],
                "profile_sha256": report["profile_sha256"],
                "artifact_digests": report.get("runtime_configuration", {}).get(
                    "artifacts", {}
                ),
            }
        )

    if not reports:
        raise ValueError("review_candidate_reports_required")
    items = []
    for sample_id, source in by_id.items():
        audio = (audio_root / source["audio"]).resolve()
        if not audio.is_relative_to(audio_root) or not audio.is_file():
            raise ValueError("review_audio_missing_or_outside_dataset")
        if _sha256(audio) != source.get("audio_sha256"):
            raise ValueError("review_audio_digest_mismatch")
        start, end = (
            source.get("source_start_seconds"),
            source.get("source_end_seconds"),
        )
        if (
            not isinstance(start, (int, float))
            or isinstance(start, bool)
            or not isinstance(end, (int, float))
            or isinstance(end, bool)
            or not math.isfinite(start)
            or not math.isfinite(end)
            or start < 0
            or end <= start
        ):
            raise ValueError("review_source_interval_invalid")
        with wave.open(str(audio), "rb") as stream:
            audio_duration = stream.getnframes() / stream.getframerate()
        if not math.isclose(audio_duration, end - start, abs_tol=1 / 16000):
            raise ValueError("review_audio_interval_duration_mismatch")
        alternatives = []
        for report_name, report, keyed in reports:
            hypothesis = keyed[sample_id]
            alternatives.append(
                {
                    "candidate_id": report.get("profile_id"),
                    "model_revision": report["model_revision"],
                    "profile_sha256": report["profile_sha256"],
                    "artifact_digests": report.get("runtime_configuration", {}).get(
                        "artifacts", {}
                    ),
                    "run_file": report_name,
                    "status": hypothesis.get("status"),
                    "error_code": hypothesis.get("error_code"),
                    "hypothesis": hypothesis.get("hypothesis", ""),
                    "normalized_edits": hypothesis.get("normalized_edits"),
                }
            )
        if any(
            alternative["status"] != "completed" or alternative["normalized_edits"] != 0
            for alternative in alternatives
        ):
            items.append(
                {
                    "sample_id": sample_id,
                    "group_id": source["group_id"],
                    "speaker_role": source.get("speaker_role", "unknown"),
                    "source_start_seconds": start,
                    "source_end_seconds": end,
                    "audio_path": Path(
                        os.path.relpath(audio, output_path.parent)
                    ).as_posix(),
                    "audio_sha256": source["audio_sha256"],
                    "reference": source["reference"],
                    "alternatives": alternatives,
                }
            )
    return {
        "schema_version": "asr_error_review_v1",
        "dataset_id": manifest["dataset_id"],
        "manifest_sha256": _sha256(manifest_path),
        "report_provenance": report_digests,
        "review_items": items,
        "reference_is_read_only": True,
        "scope": "licensed_public_development_audio",
    }


def render_html(payload):
    embedded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    embedded = embedded.replace("<", "\\u003c").replace(">", "\\u003e")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ASR error review · {html.escape(payload["dataset_id"])}</title>
<style>
body{{font:16px system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#172033;background:#f5f7fb}}
h1{{font-size:1.7rem}} .note{{padding:1rem;background:#e8eef8;border-radius:.6rem}} .controls{{display:flex;gap:.6rem;flex-wrap:wrap;margin:1rem 0}}
input,select{{font:inherit;padding:.55rem;border:1px solid #9aa7ba;border-radius:.4rem}} .card{{background:white;border:1px solid #d3dbe8;border-radius:.7rem;padding:1rem;margin:1rem 0}}
.meta{{color:#43516a;font-size:.9rem}} .reference{{padding:.8rem;background:#f4f5f8;border-left:4px solid #526b92;white-space:pre-wrap}}
details{{border-top:1px solid #e1e5ec;padding:.65rem 0}} summary{{cursor:pointer;font-weight:650}} .hyp{{white-space:pre-wrap;padding:.5rem 0}}
code{{overflow-wrap:anywhere;font-size:.8rem}} audio{{width:min(100%,500px)}} a{{display:inline-block;margin-left:.5rem}}
</style></head><body>
<h1>ASR error review</h1>
<p class="note">Read-only review of frozen development references and model outputs. The reference is never editable here. Audio files and each source/model digest were verified when this packet was built. These artifacts do not represent clinical adjudication.</p>
<p id="summary"></p><div class="controls"><input id="query" type="search" placeholder="Filter consultation, clip, or text"><select id="model"><option value="">All candidates</option></select></div>
<main id="items"></main>
<script>const PACKET={embedded};
const root=document.getElementById('items'), query=document.getElementById('query'), model=document.getElementById('model');
document.getElementById('summary').textContent=`${{PACKET.review_items.length}} clips · ${{PACKET.report_provenance.length}} candidates · ${{PACKET.dataset_id}} · manifest SHA-256 ${{PACKET.manifest_sha256}}`;
const candidateIds=[...new Set(PACKET.report_provenance.map(x=>x.candidate_id))];
for(const id of candidateIds){{const option=document.createElement('option');option.value=id;option.textContent=id;model.append(option)}}
function appendText(parent,tag,text,className){{const el=document.createElement(tag);el.textContent=text??'';if(className)el.className=className;parent.append(el);return el}}
function render(){{root.replaceChildren();const needle=query.value.toLowerCase();for(const item of PACKET.review_items){{
const text=[item.sample_id,item.group_id,item.reference,...item.alternatives.map(x=>x.hypothesis)].join(' ').toLowerCase();if(needle&&!text.includes(needle))continue;
const visible=item.alternatives.filter(x=>!model.value||x.candidate_id===model.value);if(model.value&&!visible.length)continue;
const card=document.createElement('section');card.className='card';appendText(card,'h2',item.sample_id);appendText(card,'p',`${{item.group_id}} · ${{item.speaker_role}} · source interval ${{item.source_start_seconds.toFixed(3)}}–${{item.source_end_seconds.toFixed(3)}} s`,'meta');
const audio=document.createElement('audio');audio.controls=true;audio.preload='none';audio.src=item.audio_path;card.append(audio);const link=document.createElement('a');link.href=item.audio_path;link.textContent='Open exact clip';card.append(link);appendText(card,'p',`Audio SHA-256: ${{item.audio_sha256}}`,'meta');appendText(card,'h3','Frozen reference');appendText(card,'div',item.reference,'reference');appendText(card,'h3','Candidate alternatives');
for(const candidate of visible){{const details=document.createElement('details');const summary=document.createElement('summary');summary.textContent=`${{candidate.candidate_id}} · ${{candidate.status}} · edits ${{candidate.normalized_edits}}`;details.append(summary);appendText(details,'p',`Model revision ${{candidate.model_revision}} · profile SHA-256 ${{candidate.profile_sha256}}`,'meta');appendText(details,'p',`Run ${{candidate.run_file}} · error ${{candidate.error_code??'none'}}`,'meta');appendText(details,'div',candidate.hypothesis,'hyp');appendText(details,'p','Model artifact digests','meta');const code=appendText(details,'code',JSON.stringify(candidate.artifact_digests));details.append(code);card.append(details)}}root.append(card)}}}}
query.addEventListener('input',render);model.addEventListener('change',render);render();</script></body></html>"""


def build_html(manifest_path, report_paths, audio_root, output_path):
    output_path = Path(output_path)
    payload = build_payload(manifest_path, report_paths, audio_root, output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8", newline="\n") as destination:
        destination.write(render_html(payload))
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--audio-root", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--reports", nargs="+", required=True)
    args = parser.parse_args()
    result = build_html(args.manifest, args.reports, args.audio_root, args.out)
    print(
        json.dumps(
            {
                "schema_version": result["schema_version"],
                "review_items": len(result["review_items"]),
                "candidates": len(result["report_provenance"]),
                "output": args.out,
            },
            separators=(",", ":"),
        )
    )
