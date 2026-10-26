import wave
import pytest
np=pytest.importorskip('numpy')
from services.channel_signal_audit import audit


def test_distinct_channels_pass_but_swap_and_crosstalk_fail(tmp_path):
    rate=16000;time=np.arange(rate*2)/rate
    samples=np.stack([.3*np.sin(2*np.pi*f*time) for f in (220,440,660)],axis=1)
    def write(name,values):
        path=tmp_path/name
        with wave.open(str(path),'wb') as audio:audio.setparams((3,2,rate,0,'NONE','not compressed'));audio.writeframes((values*32767).astype('<i2').tobytes())
        return path
    report=audit(write('clean.wav',samples),[220,440,660],-30,2)
    assert report['signal_checks_pass'] and not report['physical_hardware_validated']
    assert not audit(write('swapped.wav',samples[:,[1,0,2]]),[220,440,660],-30)['signal_checks_pass']
    contaminated=samples.copy();contaminated[:,0]+=samples[:,1]*.5
    assert not audit(write('leak.wav',contaminated),[220,440,660],-30)['signal_checks_pass']
