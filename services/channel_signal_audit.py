"""Controlled test-tone channel audit. Generated fixtures never qualify physical hardware."""
import argparse
import json
import math
from pathlib import Path
import wave
from services.api.ingest import inspect_pcm_wav,file_sha256


def audit(audio,frequencies,maximum_crosstalk_db,expected_seconds=None):
    import numpy as np
    metadata=inspect_pcm_wav(audio);count=metadata['channels'];rate=metadata['sample_rate']
    if len(frequencies)!=count or len(set(frequencies))!=count or any(type(f) is not int or not 10<=f<rate/2-3 for f in frequencies):
        raise ValueError('One distinct integer calibration frequency per input channel required')
    if any(abs(a-b)<6 for i,a in enumerate(frequencies) for b in frequencies[i+1:]):raise ValueError('Calibration tones must be separated')
    if not math.isfinite(maximum_crosstalk_db) or maximum_crosstalk_db>0:raise ValueError('Explicit nonpositive measurement tolerance required')
    energies=np.zeros((count,count));squares=np.zeros(count);frames=0
    with wave.open(str(audio),'rb') as source:
        while data:=source.readframes(rate):
            samples=np.frombuffer(data,dtype='<i2').reshape(-1,count).astype(np.float64)/32768
            if len(samples)<rate:continue
            spectrum=np.abs(np.fft.rfft(samples,axis=0))**2
            for i,frequency in enumerate(frequencies):energies[:,i]+=spectrum[max(0,frequency-2):frequency+3].sum(axis=0)
            squares+=(samples*samples).sum(axis=0);frames+=len(samples)
    if not frames:raise ValueError('At least one complete second required')
    rows=[]
    for channel in range(count):
        own=float(energies[channel,channel]);other=float(sum(energies[channel,i] for i in range(count) if i!=channel))
        ratio=10*math.log10(max(other,1e-30)/max(own,1e-30))
        mapped=int(np.argmax(energies[channel]));silent=float(squares[channel]/frames)<1/32768**2
        rows.append({'channel_index':channel,'expected_frequency_hz':frequencies[channel],'strongest_frequency_hz':frequencies[mapped],
            'rms':float(math.sqrt(squares[channel]/frames)),'other_calibration_tones_db_relative_to_expected':ratio,
            'silent':silent,'mapping_matches':mapped==channel and not silent,'crosstalk_within_supplied_tolerance':not silent and ratio<=maximum_crosstalk_db})
    duration_ok=expected_seconds is None or abs(metadata['duration_ms']/1000-expected_seconds)<=.05
    return {'schema_version':'controlled_channel_signal_audit_v1','audio_sha256':file_sha256(audio),'duration_ms':metadata['duration_ms'],
        'maximum_crosstalk_db':maximum_crosstalk_db,'channels':rows,'duration_matches_supplied_expectation':duration_ok,
        'signal_checks_pass':duration_ok and all(r['mapping_matches'] and r['crosstalk_within_supplied_tolerance'] for r in rows),
        'physical_hardware_validated':False,'clinical_speaker_accuracy_established':False,
        'limitations':['Only known calibration tones; not clinical speech or diarization accuracy.','Input hardware, channel routing and independent timing require an observed physical test.','The supplied tolerance is an engineering parameter, not a clinically approved limit.']}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--audio',required=True);p.add_argument('--frequencies',nargs='+',type=int,required=True);p.add_argument('--maximum-crosstalk-db',type=float,required=True);p.add_argument('--expected-seconds',type=float);p.add_argument('--out',required=True);a=p.parse_args();r=audit(a.audio,a.frequencies,a.maximum_crosstalk_db,a.expected_seconds)
    with Path(a.out).open('x') as output:json.dump(r,output,indent=2)
    raise SystemExit(0 if r['signal_checks_pass'] else 2)
