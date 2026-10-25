"""Provision the public CPU ASR extension from a pinned official archive."""
import json
import tarfile
from pathlib import Path
from services.api.ingest import file_sha256
from services.provision_public_diarization import fetch

ARCHIVE_SHA='393f8a14e2f5fb96746aaab342997a40641001fbd5bf9592a080a8329178ee96'
URL='https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25.tar.bz2'
FILES=('conv_frontend.onnx','encoder.int8.onnx','decoder.int8.onnx','tokenizer/merges.txt','tokenizer/tokenizer_config.json','tokenizer/vocab.json','README.md')


def provision():
    root=Path('data/models');root.mkdir(parents=True,exist_ok=True)
    archive=root/'qwen3-asr-int8.tar.bz2'
    if not archive.is_file():fetch(URL,archive,900000000)
    if file_sha256(archive)!=ARCHIVE_SHA:raise ValueError('Qwen archive integrity failure')
    with tarfile.open(archive,'r:bz2') as bundle:
        members=bundle.getmembers()
        if sum(m.size for m in members)>2200000000:raise ValueError('Archive expansion budget exceeded')
        for m in members:
            if m.issym() or m.islnk() or not (root/m.name).resolve().is_relative_to(root.resolve()):
                raise ValueError('Unsafe archive member')
        bundle.extractall(root,filter='data')
    model=root/'sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25'
    manifest={'candidate_id':'qwen3-asr-0.6b-int8','runtime':'sherpa-onnx','runtime_version':'2.0.0',
        'source':URL,'archive_sha256':ARCHIVE_SHA,'upstream':'Qwen/Qwen3-ASR-0.6B','license':'Apache-2.0',
        'artifacts':{name:file_sha256(model/name) for name in FILES}}
    fetch('https://raw.githubusercontent.com/QwenLM/Qwen3-ASR/main/LICENSE',model/'UPSTREAM-LICENSE',1000000)
    (model/'provisioning.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':provision()
