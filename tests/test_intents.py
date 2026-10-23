import unittest
from assistant_logic import match_command, classify_command, select_transcript, CommandEngine


class IntentTests(unittest.TestCase):
    def test_natural_thai_requests_and_transcription_errors(self):
        examples={
            'ออร่าช่วยพาเข้าหน้าหลักให้หน่อยครับ':'enter',
            'เปิดหน้าแรกให้หน่อยค่ะ':'enter',
            'เริ่มระบบเลย':'enter',
            'ช่วยดูยอดขายวันนี้ให้หน่อย':'sales',
            'ขอรายงานยอดขายนาฬิกาคริปโตหน่อยครับ':'sales',
            'สรุปรายรับเดือนนี้':'sales',
            'เชคยอดข่าย':'sales',
            'ยอดขาย':'sales',
            'เช็คสุขภาพให้หน่อย':'health',
            'ช่วยสแกนสุขภาพตอนนี้เลย':'health',
            'เช็กสุกภาพ':'health',
            'ตรวดสุขภาพ':'health',
            'สุขภาพ':'health',
            'กลับไปหน้าหลักได้ไหมครับ':'home',
            'ช่วยกลับหน้าปกติให้ที':'home',
            'ย้อนกลับหน้าแรก':'home',
            'กลับหน้า':'home',
            'ขอส่องกระจกหน่อยนะครับ':'dark',
            'ช่วยปิดหน้าจอให้หน่อย':'dark',
            'ขอเป็นจอดำ':'dark',
        }
        for text,expected in examples.items():
            with self.subTest(text=text):
                self.assertEqual(match_command(text),expected)

    def test_negation_ambiguity_and_smalltalk_do_not_change_mode(self):
        for text in ('ไม่ต้องตรวจสุขภาพ','อย่าเปิดยอดขาย','ยังไม่เข้าหน้าหลัก',
                     'ห้ามปิดหน้าจอ','ยกเลิกตรวจสุขภาพ','ตรวจสุขภาพแล้วดูยอดขาย',
                     'กลับหน้าหลักแล้วส่องกระจก','คำว่าตรวจสุขภาพแปลว่าอะไร',
                     'วันนี้สุขภาพดีมาก','ยอดขายเพิ่มขึ้นเยอะ','สวัสดีครับ','คริปโตวันนี้เป็นไง'):
            with self.subTest(text=text):
                self.assertIsNone(match_command(text))
                engine=CommandEngine();engine.handle('เข้าหน้าหลัก')
                engine.handle(text)
                self.assertEqual(engine.state,'home')
        self.assertEqual(classify_command('ตรวจสุขภาพกับดูยอดขาย')['reason'],'ambiguous')

    def test_recognition_alternatives_preserve_negation_and_avoid_guessing(self):
        def response(*texts):
            return {'alternative':[{'transcript':t} for t in texts]}
        self.assertEqual(select_transcript(response('เสียงอะไรสักอย่าง','ตรวจสุขภาพ')),'ตรวจสุขภาพ')
        self.assertEqual(select_transcript(response('ไม่ต้องตรวจสุขภาพ','ตรวจสุขภาพ')),'ไม่ต้องตรวจสุขภาพ')
        self.assertEqual(select_transcript(response('อะไรก็ได้','ตรวจสุขภาพ','ดูยอดขาย')),'อะไรก็ได้')
        self.assertEqual(select_transcript({'alternative':[]}),'')


if __name__=='__main__':
    unittest.main()
