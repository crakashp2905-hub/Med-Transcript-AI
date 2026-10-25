"""Optional real diarization adapter; local approved artifacts only, roles never guessed."""
import wave
import time
from services.api.ingest import file_sha256


def diarize(audio, manifest, checkpoint=lambda: None):
    if not manifest.get("license_approved") or not manifest.get("enabled"):
        raise ValueError("Explicit model license/access approval and enablement required")
    for key in (("vad", "embedding") if manifest.get("engine") == "vad_embeddings_v1" else ("segmentation", "embedding")):
        item = manifest[key]
        if file_sha256(item["path"]) != item["sha256"]:
            raise ValueError("Diarization artifact integrity failure")
    import numpy as np
    import sherpa_onnx as so
    if so.__version__ != manifest.get('runtime_version', so.__version__):
        raise ValueError('Diarization runtime/profile mismatch')
    if manifest.get("engine") == "vad_embeddings_v1":
        last_check = 0.0
        def bounded_checkpoint():
            nonlocal last_check
            now = time.monotonic()
            if now-last_check >= 1:
                checkpoint()
                last_check = now
        return vad_embeddings(audio, manifest, so, np, bounded_checkpoint)
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


def vad_embeddings(audio, manifest, so, np, checkpoint):
    """Public-model development baseline. Does not detect overlapping speakers."""
    with wave.open(str(audio), 'rb') as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (1, 2, 16000):
            raise ValueError('Validated mono 16kHz PCM16 required')
        samples = np.frombuffer(source.readframes(source.getnframes()), dtype='<i2').astype(np.float32)/32768
    config = so.VadModelConfig()
    config.silero_vad.model = manifest['vad']['path']
    config.silero_vad.min_silence_duration = .25
    config.silero_vad.min_speech_duration = .25
    config.sample_rate = 16000
    vad = so.VoiceActivityDetector(config, buffer_size_in_seconds=30)
    extractor = so.SpeakerEmbeddingExtractor(so.SpeakerEmbeddingExtractorConfig(
        model=manifest['embedding']['path'], num_threads=2, provider='cpu'))
    window = int(16000*manifest.get('window_seconds', 1.5))
    if not 8000 <= window <= 64000:
        raise ValueError('Bounded embedding window required')
    spans, vectors = [], []
    def drain():
        while not vad.empty():
            speech = vad.front
            start, values = speech.start, np.array(speech.samples, dtype=np.float32)
            for offset in range(0, len(values), window):
                checkpoint()
                piece = values[offset:offset+window]
                a, b = start+offset, min(start+offset+len(piece), len(samples))
                if a >= b:
                    continue
                spans.append({'start_ms':round(a/16), 'end_ms':round(b/16),
                    'speaker_id': None, 'role':'unknown', 'role_status':'unconfirmed'})
                if len(piece) < 6400:
                    vectors.append(None)
                    continue
                stream = extractor.create_stream()
                stream.accept_waveform(sample_rate=16000, waveform=piece)
                stream.input_finished()
                if not extractor.is_ready(stream):
                    vectors.append(None)
                    continue
                vector = np.array(extractor.compute(stream), dtype=np.float32)
                norm = np.linalg.norm(vector)
                vectors.append(vector/norm if np.isfinite(norm) and norm > 0 else None)
            vad.pop()
    for pos in range(0, len(samples), 512):
        checkpoint()
        vad.accept_waveform(np.pad(samples[pos:pos+512], (0,max(0,512-len(samples[pos:pos+512])))))
        drain()
    vad.flush()
    drain()
    indices = [i for i,v in enumerate(vectors) if v is not None]
    if len(indices) > 3000:
        raise ValueError('Development clustering budget exceeded')
    if indices:
        matrix = np.stack([vectors[i] for i in indices])
        similarities = matrix @ matrix.T
        np.fill_diagonal(similarities, -np.inf)
        groups = {i:[indices[i]] for i in range(len(indices))}
        threshold = manifest.get('clustering_threshold', .65)
        if not .1 <= threshold <= .95:
            raise ValueError('Invalid clustering threshold')
        while len(groups)>1:
            checkpoint()
            a,b = np.unravel_index(np.argmax(similarities), similarities.shape)
            if similarities[a,b] < threshold:
                break
            na,nb = len(groups[a]),len(groups[b])
            valid = list(groups)
            scores = (similarities[a,valid]*na+similarities[b,valid]*nb)/(na+nb)
            similarities[a,valid] = scores
            similarities[valid,a] = scores
            similarities[b,:] = similarities[:,b] = -np.inf
            similarities[a,a] = -np.inf
            groups[a].extend(groups.pop(b))
        for label, members in enumerate(sorted(groups.values(), key=min)):
            for index in members:
                spans[index]['speaker_id'] = f'speaker_{label}'
    merged=[]
    for row in spans:
        if merged and row['speaker_id']==merged[-1]['speaker_id'] and row['start_ms']==merged[-1]['end_ms']:
            merged[-1]['end_ms']=row['end_ms']
        else:
            merged.append(dict(row))
    return {'segments':merged, 'engine':'vad_embeddings_v1', 'runtime_version':so.__version__,
        'role_assignment':'clinician_confirmation_required', 'clinical_validation':'not_validated',
        'overlap_detection':'unsupported', 'short_windows':'unknown_speaker',
        'limitations':['Fixed windows can straddle speaker changes', 'No overlapping-speaker detection',
            'Clustering threshold is a development parameter, not clinically calibrated'],
        'artifacts':manifest}


def attach_speakers(transcript, report):
    """Assign only a single unambiguous cluster covering >=80% of a text segment."""
    for segment in transcript['segments']:
        overlaps={}
        for turn in report['segments']:
            if turn.get('speaker_id') is None:
                continue
            n=max(0,min(segment['end_ms'],turn['end_ms'])-max(segment['start_ms'],turn['start_ms']))
            if n:
                overlaps[turn['speaker_id']]=overlaps.get(turn['speaker_id'],0)+n
        if len(overlaps)==1 and max(overlaps.values())>=.8*(segment['end_ms']-segment['start_ms']):
            segment['speaker_id']=next(iter(overlaps))
        else:
            segment['uncertainties'].append('speaker_boundary_or_coverage_uncertain')
    transcript['diarization']=report
    transcript['review_flags'].append('speaker_clusters_require_clinician_confirmation')
    return transcript


def confirm_roles(segments, assignments, *, clinician_confirmed=False):
    if not clinician_confirmed:
        raise ValueError("Clinician confirmation required")
    speakers = {s["speaker_id"] for s in segments}
    if set(assignments) != speakers or any(v not in ("patient","clinician","caregiver","unknown") for v in assignments.values()):
        raise ValueError("Explicit assignment required for every observed speaker")
    return [{**s,"role":assignments[s["speaker_id"]],"role_status":"clinician_confirmed"} for s in segments]
