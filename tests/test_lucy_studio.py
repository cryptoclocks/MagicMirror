import json
import unittest
import urllib.request
import urllib.error
from unittest.mock import patch
from assistant_logic import CommandEngine, classify_command
from lucy_studio import StudioServer, mint_token


class LucyTests(unittest.TestCase):
    def setUp(self):
        self.server=StudioServer()

    def tearDown(self):
        self.server.close()

    def test_only_exact_studio_assets_are_served(self):
        with urllib.request.urlopen(self.server.url) as response:
            self.assertIn(b'AI Studio',response.read())
        for path in ('../.secrets/decart-api-key','/../../README.md','app.js'):
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(self.server.url+path)

    def test_cross_origin_cannot_mint_tokens(self):
        request=urllib.request.Request(self.server.url+'token',data=b'',
            headers={'Origin':'https://untrusted.example'},method='POST')
        with patch('lucy_studio.mint_token') as mint:
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(request)
            self.assertEqual(caught.exception.code,403)
            mint.assert_not_called()

    def test_browser_receives_short_lived_token_not_permanent_key(self):
        with patch('lucy_studio.api_key',return_value='private-secret'),patch('lucy_studio.mint_token',return_value='short-token') as mint:
            request=urllib.request.Request(self.server.url+'token',data=b'',
                headers={'Origin':self.server.origin},method='POST')
            with urllib.request.urlopen(request) as response:
                data=response.read()
            self.assertNotIn(b'private-secret',data)
            self.assertEqual(json.loads(data),{'apiKey':'short-token'})
            mint.assert_called_once_with('private-secret',self.server.origin)

    def test_upstream_errors_do_not_expose_credentials(self):
        with patch('lucy_studio.api_key',return_value='private-secret'),patch('lucy_studio.mint_token',side_effect=RuntimeError('private-secret')):
            request=urllib.request.Request(self.server.url+'token',data=b'',headers={'Origin':self.server.origin})
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(request)
            self.assertNotIn(b'private-secret',caught.exception.read())

    def test_studio_command_preserves_startup_and_negation_guards(self):
        engine=CommandEngine()
        self.assertIsNone(engine.handle('เปิดลูซี่')[0])
        engine.handle('เข้าหน้าหลัก')
        self.assertEqual(engine.handle('เปิด AI Studio')[0],'studio')
        self.assertEqual(engine.state,'studio')
        self.assertEqual(classify_command('ไม่ต้องเปิดลูซี่')['reason'],'negated')
        engine.handle('กลับหน้าหลัก')
        self.assertEqual(engine.state,'home')

    def test_token_request_scopes_model_origin_and_lifetime(self):
        from unittest.mock import MagicMock
        response=MagicMock()
        response.__enter__.return_value.read.return_value=b'{"apiKey":"ephemeral"}'
        with patch('lucy_studio.urllib.request.urlopen',return_value=response) as opened:
            self.assertEqual(mint_token('permanent','http://127.0.0.1:1234'),'ephemeral')
        request=opened.call_args.args[0]
        self.assertEqual(request.full_url,'https://api.decart.ai/v1/client/tokens')
        self.assertEqual(json.loads(request.data),{'expiresIn':120,'allowedModels':['lucy-2.5'],'allowedOrigins':['http://127.0.0.1:1234'],'constraints':{'realtime':{'maxSessionDuration':120}}})
        self.assertNotIn(b'permanent',request.data)

    def test_tracking_models_and_wasm_are_local_assets(self):
        with urllib.request.urlopen(self.server.url+'tracking/wasm/vision_wasm_internal.wasm') as response:
            self.assertEqual(response.headers.get_content_type(),'application/wasm')
            self.assertEqual(response.read(4),b'\x00asm')
        for name in ('tracking/selfie_segmenter.tflite','tracking/face_landmarker.task','tracking/pose_landmarker_lite.task','tracking-worker.bundle.js'):
            with urllib.request.urlopen(self.server.url+name) as response:
                self.assertEqual(response.status,200)
                self.assertTrue(response.read(16))

    def test_animal_assets_have_valid_hashes_and_local_textures(self):
        import hashlib
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]/'web/lucy/animals'
        manifest=json.loads((root/'SOURCE.json').read_text())
        for name,digest in manifest['files'].items():
            with urllib.request.urlopen(self.server.url+'animals/'+name) as response:
                data=response.read()
                self.assertEqual(data[:4],b'glTF')
                self.assertEqual(hashlib.sha256(data).hexdigest(),digest)
        with urllib.request.urlopen(self.server.url+'animals/Textures/colormap.png') as response:
            self.assertEqual(response.headers.get_content_type(),'image/png')
            self.assertEqual(response.read(8),b'\x89PNG\r\n\x1a\n')

    def test_studio_offers_only_avatar_and_background(self):
        import re
        with urllib.request.urlopen(self.server.url) as response:
            html=response.read().decode()
        provider=re.search(r'<select id="provider"[^>]*>(.*?)</select>',html).group(1)
        self.assertEqual(re.findall(r'<option value="([^"]+)"',provider),['background','avatar'])
        self.assertNotIn('id="cloud-key"',html)
