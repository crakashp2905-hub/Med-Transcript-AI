"""Build an English terminology candidate list from licensed dev references."""

import argparse
import hashlib
import json
import re
from pathlib import Path

from services.terminology_hints import LOCAL_LEXICON


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _source_rows(manifest):
    if isinstance(manifest.get("cases"), list):
        for case in manifest["cases"]:
            group_id = case.get("foreground_id", case.get("group_id"))
            for index, turn in enumerate(case.get("reference_turns", [])):
                yield (
                    case.get("group_id", group_id),
                    group_id,
                    index,
                    turn.get("reference"),
                    turn.get("uncertain_reference", False),
                    turn.get("role"),
                )
    if isinstance(manifest.get("samples"), list):
        for sample in manifest["samples"]:
            yield (
                sample.get("sample_id"),
                sample.get("group_id"),
                0,
                sample.get("reference"),
                sample.get("reference_uncertain", False),
                sample.get("speaker_role"),
            )


def build_lexicon(manifest_paths, reservation_path, output_path):
    reserved_body = json.loads(Path(reservation_path).read_text(encoding="utf-8"))
    reserved = set(reserved_body.get("reserved_groups", []))
    candidates = sorted(LOCAL_LEXICON)
    occurrences = {term: [] for term in candidates}
    seen_occurrences = {term: set() for term in candidates}
    manifest_receipts = []
    for manifest_path in manifest_paths:
        manifest_file = Path(manifest_path)
        body = json.loads(manifest_file.read_text(encoding="utf-8"))
        if (
            body.get("data_class") != "approved_public"
            or body.get("rights_reviewed") is not True
            or "acceptance"
            in str(body.get("split", body.get("split_role", ""))).lower()
            and "not" not in str(body.get("split", body.get("split_role", ""))).lower()
        ):
            raise ValueError("rights_reviewed_development_manifest_required")
        lock_file = manifest_file.parent / "lock.json"
        if not lock_file.is_file():
            raise ValueError("frozen_dataset_lock_required")
        lock = json.loads(lock_file.read_text(encoding="utf-8"))
        if any(
            case.get("donor_id") in reserved
            for case in body.get("cases", [])
            if isinstance(case, dict)
        ):
            raise ValueError("reserved_acceptance_group_in_lexicon_source")
        manifest_digest = _sha256(manifest_file)
        if lock.get("manifest_sha256") != manifest_digest:
            raise ValueError("frozen_manifest_lock_mismatch")
        count = 0
        for record_id, group_id, row_index, reference, uncertain, role in _source_rows(
            body
        ):
            if not isinstance(record_id, str) or not record_id:
                raise ValueError("reference_record_id_required")
            if not isinstance(group_id, str) or not group_id:
                raise ValueError("reference_group_id_required")
            if group_id in reserved:
                raise ValueError("reserved_acceptance_group_in_lexicon_source")
            if uncertain is True or not isinstance(reference, str):
                continue
            count += 1
            reference_digest = hashlib.sha256(reference.encode("utf-8")).hexdigest()
            for term in candidates:
                pattern = re.compile(
                    rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", re.I
                )
                for match in pattern.finditer(reference):
                    key = (
                        manifest_digest,
                        record_id,
                        row_index,
                        reference_digest,
                        match.start(),
                        match.end(),
                    )
                    if key in seen_occurrences[term]:
                        continue
                    seen_occurrences[term].add(key)
                    occurrences[term].append(
                        {
                            "manifest_sha256": manifest_digest,
                            "dataset_id": body["dataset_id"],
                            "record_id": record_id,
                            "group_id": group_id,
                            "reference_row_index": row_index,
                            "reference_sha256": reference_digest,
                            "start_char": match.start(),
                            "end_char": match.end(),
                            "role": role,
                        }
                    )
        manifest_receipts.append(
            {
                "dataset_id": body["dataset_id"],
                "manifest_path": manifest_file.as_posix(),
                "manifest_sha256": manifest_digest,
                "lock_sha256": _sha256(lock_file),
                "license": body.get("license_id", body.get("license")),
                "source_revision": body.get("source_revision"),
                "eligible_reference_rows": count,
            }
        )
    entries = [
        {
            "term": term,
            "language": "en",
            "provenance": occurrences[term],
        }
        for term in candidates
        if occurrences[term]
    ]
    if not entries:
        raise ValueError("no_candidate_terms_found_in_licensed_references")
    payload = {
        "schema_version": "clinical_english_lexicon_v1",
        "lexicon_id": "licensed_development_mock_terms_v1",
        "source_policy": "terms are a fixed subset of pre-existing generic opt-in hints and are retained only when found in rights-reviewed development references",
        "acceptance_data_used": False,
        "patient_specific_terms_added": False,
        "candidate_terms": candidates,
        "entries": entries,
        "source_manifests": manifest_receipts,
        "reservation_sha256": _sha256(reservation_path),
        "uncertain_reference_rows_excluded": True,
        "clinical_validation": "not_established",
        "automatic_transcript_mutation": False,
    }
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as destination:
        json.dump(payload, destination, ensure_ascii=False, indent=2)
        destination.write("\n")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifests", nargs="+", required=True)
    parser.add_argument(
        "--reservation", default="evaluation/acceptance-reservation-v1.json"
    )
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = build_lexicon(args.manifests, args.reservation, args.out)
    print(
        json.dumps(
            {
                "lexicon_id": result["lexicon_id"],
                "entry_count": len(result["entries"]),
                "occurrence_count": sum(
                    len(row["provenance"]) for row in result["entries"]
                ),
            },
            indent=2,
        )
    )
