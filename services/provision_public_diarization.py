"""Download bounded public artifacts with pinned hashes; never downloads gated models."""
import json
import shutil
import urllib.request
from pathlib import Path
from services.api.ingest import file_sha256

ROOT=Path('data/models/public-diarization-v1')
ARTIFACTS={
    'vad':('silero_vad.onnx','asr-models','9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6','MIT'),
    'embedding':('wespeaker_en_voxceleb_resnet34_LM.onnx','speaker-recongition-models','e9848563da86f263117134dfd7ad63c92355b37de492b55e325400c9d9c39012','CC-BY-4.0'),
}


def provision():
    ROOT.mkdir(parents=True,exist_ok=True)
    manifest={'engine':'vad_embeddings_v1','enabled':True,'license_approved':True,
        'scope':'public_mock_development_only','runtime_version':'2.0.0',
        'clustering_threshold':.65,'window_seconds':1.5,
        'attribution':'Silero Team, Silero VAD; WeSpeaker team, English VoxCeleb ResNet34 LM; ONNX exports distributed by k2-fsa/sherpa-onnx.',
        'weight_license_evidence':'https://github.com/wenet-e2e/wespeaker/blob/master/docs/pretrained.md'}
    for key,(name,tag,digest,license_id) in ARTIFACTS.items():
        path=ROOT/name
        url=f'https://github.com/k2-fsa/sherpa-onnx/releases/download/{tag}/{name}'
        if not path.exists():
            urllib.request.urlretrieve(url,path)
        if file_sha256(path)!=digest:
            raise ValueError('Public artifact hash mismatch; refuse changed upstream bytes')
        manifest[key]={'path':str(path.resolve()),'sha256':digest,'source':url,'license':license_id}
    licenses={
        'SILERO-LICENSE':'https://raw.githubusercontent.com/snakers4/silero-vad/master/LICENSE',
        'WESPEAKER-SOURCE-LICENSE':'https://raw.githubusercontent.com/wenet-e2e/wespeaker/master/LICENSE',
        'WESPEAKER-MODEL-LICENSE-EVIDENCE.md':manifest['weight_license_evidence'].replace('github.com','raw.githubusercontent.com').replace('/blob/','/'),
    }
    for name,url in licenses.items():
        urllib.request.urlretrieve(url,ROOT/name)
    # Same unmodified CC BY 4.0 legal code already retained with the public corpus.
    shutil.copyfile('evaluation/datasets/primock57-full-v1/LICENSE.md',ROOT/'WESPEAKER-MODEL-LICENSE.txt')
    (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':
    provision()
