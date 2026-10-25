"""Optional real diarization adapter; local approved artifacts only, roles never guessed."""
import wave
from services.api.ingest import file_sha256


def diarize(audio, manifest):
    if not manifest.get("license_approved") or not manifest.get("enabled"):
        raise ValueError("Explicit model license/access approval and enablement required")
    for key in ("segmentation", "embedding"):
        item = manifest[key]
        if file_sha256(item["path"]) != item["sha256"]:
            raise ValueError("Diarization artifact integrity failure")
    import numpy as np
    import sherpa_onnx as so
    config = so.OfflineSpeakerDiarizationConfig(
        segmentation=so.OfflineSpeakerSegmentationModelConfig(
            pyannote=so.OfflineSpeakerSegmentationPyannoteModelConfig(model=manifest["segmentation"]["path"])),
        embedding=so.SpeakerEmbeddingExtractorConfig(model=manifest["embedding"]["path"]),
        clustering=so.FastClusteringConfig(num_clusters=-1, threshold=.5),
        min_duration_on=.3, min_duration_off=.5)
    if not config.validate():
        raise ValueError("Invalid diarization configuration")
    engine = so.OfflineSpeakerDiarization(config)
    with wave.open(str(audio), "rb") as source:
        if (source.getnchannels(),source.getsampwidth(),source.getframerate()) != (1,2,16000):
            raise ValueError("Validated mono 16kHz PCM16 required")
        duration = source.getnframes()/16
        pcm = np.frombuffer(source.readframes(source.getnframes()),dtype="<i2").astype(np.float32)/32768
    rows = []
    for segment in engine.process(pcm).sort_by_start_time():
        a,b = round(segment.start*1000), round(segment.end*1000)
        if not 0 <= a < b <= duration:
            raise ValueError("Invalid diarization timestamp")
        rows.append({"start_ms":a,"end_ms":b,"speaker_id":f"speaker_{segment.speaker}",
            "role":"unknown","role_status":"unconfirmed"})
    return {"segments": rows, "role_assignment": "clinician_confirmation_required",
        "overlap_pairs": [[i,j] for i,a in enumerate(rows) for j,b in enumerate(rows) if i<j and max(a['start_ms'],b['start_ms'])<min(a['end_ms'],b['end_ms'])],
        "clinical_validation":"not_validated", "artifacts":manifest}


def confirm_roles(segments, assignments, *, clinician_confirmed=False):
    if not clinician_confirmed:
        raise ValueError("Clinician confirmation required")
    speakers = {s["speaker_id"] for s in segments}
    if set(assignments) != speakers or any(v not in ("patient","clinician","caregiver","unknown") for v in assignments.values()):
        raise ValueError("Explicit assignment required for every observed speaker")
    return [{**s,"role":assignments[s["speaker_id"]],"role_status":"clinician_confirmed"} for s in segments]
