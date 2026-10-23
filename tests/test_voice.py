import unittest
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np
import speech_recognition as sr
from voice_io import VoiceInput


class FakeStream:
    def __init__(self,**kwargs):
        self.callback=kwargs['callback']
        self.rate=kwargs['samplerate']

    def __enter__(self):
        # Calibration silence, speech, then trailing silence at a native 48 kHz.
        for i in range(55):
            signal=np.zeros((2400,1),np.int16)
            if 8<=i<26:
                signal[:]=7000*np.sin(np.arange(2400)[:,None]*.2)
            self.callback(signal,2400,None,None)
        return self

    def __exit__(self,*args):
        pass


class VoiceTests(unittest.TestCase):
    def test_capture_resamples_and_dispatches_thai_over_https(self):
        device=SimpleNamespace(query_devices=lambda **kwargs:{'default_samplerate':48000}, InputStream=FakeStream)
        voice=VoiceInput()
        heard=[]
        states=[]
        voice.heard.connect(heard.append)
        voice.status.connect(states.append)
        with patch.dict('sys.modules',{'sounddevice':device}), patch.object(sr.Recognizer,'recognize_google',return_value='เข้าหน้าหลัก') as recognize:
            voice.run()
        self.assertEqual(heard,['เข้าหน้าหลัก'])
        self.assertEqual(states,['listening','thinking'])
        audio=recognize.call_args.args[0]
        self.assertEqual(audio.sample_rate,16000)
        self.assertEqual(recognize.call_args.kwargs['language'],'th-TH')
        self.assertTrue(recognize.call_args.kwargs['endpoint'].startswith('https://'))

    def test_network_failure_is_actionable_and_no_command_runs(self):
        device=SimpleNamespace(query_devices=lambda **kwargs:{'default_samplerate':48000}, InputStream=FakeStream)
        voice=VoiceInput()
        failures=[]
        heard=[]
        voice.failed.connect(failures.append)
        voice.heard.connect(heard.append)
        with patch.dict('sys.modules',{'sounddevice':device}), patch.object(sr.Recognizer,'recognize_google',side_effect=sr.RequestError('offline')):
            voice.run()
        self.assertEqual(heard,[])
        self.assertEqual(len(failures),1)
        self.assertIn('อินเทอร์เน็ต',failures[0])


if __name__=='__main__':
    unittest.main()
