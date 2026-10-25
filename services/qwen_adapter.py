"""Public sherpa Qwen3 CPU text-only benchmark adapter; no clinical promotion."""
import json
import wave
from pathlib import Path
from services.api.ingest import file_sha256


class QwenPredictor:
    def __init__(self,root,revision):
        import sherpa_onnx as so
        import numpy as np
        self.np=np
        root=Path(root)
        manifest=json.loads((root/'provisioning.json').read_text(encoding='utf-8'))
        if so.__version__!='2.0.0' or manifest['archive_sha256']!=revision:
            raise ValueError('Qwen ASR runtime/artifact revision mismatch')
        for name,sha in manifest['artifacts'].items():
            path=(root/name).resolve()
            if not path.is_relative_to(root.resolve()) or file_sha256(path)!=sha:
                raise ValueError('Qwen ASR artifact integrity failure')
        self.artifacts=manifest['artifacts']
        self.recognizer=so.OfflineRecognizer.from_qwen3_asr(
            conv_frontend=str(root/'conv_frontend.onnx'),encoder=str(root/'encoder.int8.onnx'),
            decoder=str(root/'decoder.int8.onnx'),tokenizer=str(root/'tokenizer'),
            num_threads=4,provider='cpu',max_total_len=512,max_new_tokens=256,
            temperature=.000001,top_p=.8,seed=42)

    def __call__(self,path):
        with wave.open(str(path),'rb') as source:
            if (source.getnchannels(),source.getsampwidth(),source.getframerate())!=(1,2,16000):
                raise ValueError('Mono 16k PCM16 required')
            pcm=self.np.frombuffer(source.readframes(source.getnframes()),dtype='<i2').astype(self.np.float32)/32768
        stream=self.recognizer.create_stream()
        stream.accept_waveform(16000,pcm)
        self.recognizer.decode_stream(stream)
        return stream.result.text
