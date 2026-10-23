import json
import base64
import unittest
from unittest.mock import patch
from gemini_voice import stream_speech, setup_message, settings, ENDPOINT


class FakeWebSocket:
    def __init__(self,messages):
        self.messages=list(messages)
        self.sent=[]
    async def __aenter__(self): return self
    async def __aexit__(self,*args): pass
    async def send(self,message): self.sent.append(json.loads(message))
    async def recv(self): return json.dumps(self.messages.pop(0))


class GeminiVoiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_live_audio_consumes_all_parts_and_uses_header_auth(self):
        pcm1=b'\x01\x00\x02\x00'
        pcm2=b'\x03\x00\x04\x00'
        ws=FakeWebSocket([{'setupComplete':{}},{'serverContent':{
            'modelTurn':{'parts':[{'inlineData':{'mimeType':'audio/pcm;rate=24000','data':base64.b64encode(pcm).decode()}} for pcm in (pcm1,pcm2)]},
            'turnComplete':True}}])
        chunks=[]
        with patch('websockets.connect',return_value=ws) as connect:
            count=await stream_speech('สวัสดีค่ะ','unit-test-key',settings(),chunks.append)
        self.assertEqual(chunks,[pcm1,pcm2])
        self.assertEqual(count,8)
        self.assertEqual(connect.call_args.args[0],ENDPOINT)
        self.assertNotIn('unit-test-key',connect.call_args.args[0])
        self.assertEqual(connect.call_args.kwargs['extra_headers']['x-goog-api-key'],'unit-test-key')
        config=ws.sent[0]['setup']
        self.assertEqual(config['generationConfig']['speechConfig']['voiceConfig']['prebuiltVoiceConfig']['voiceName'],'Leda')
        self.assertTrue(ws.sent[1]['clientContent']['turnComplete'])

    async def test_empty_audio_is_failure_so_ui_can_fall_back(self):
        ws=FakeWebSocket([{'setupComplete':{}},{'serverContent':{'turnComplete':True}}])
        with patch('websockets.connect',return_value=ws):
            with self.assertRaisesRegex(RuntimeError,'GEMINI_EMPTY_AUDIO'):
                await stream_speech('test','unit-test-key',settings(),lambda chunk:None)

    async def test_missing_credentials_never_open_network(self):
        with patch('websockets.connect') as connect:
            with self.assertRaisesRegex(RuntimeError,'GEMINI_KEY_MISSING'):
                await stream_speech('test','',settings(),lambda chunk:None)
            connect.assert_not_called()


if __name__=='__main__':
    unittest.main()
