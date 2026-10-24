"""Scripted Thai command handling and consistent fictional sales figures."""
import unicodedata
from difflib import SequenceMatcher
import re
from hat_catalog import HATS, parse_hat_choice
from daily_tasks import DailyTasks

COMMANDS = {
    'studio': {
        'phrase':'เปิดเอไอสตูดิโอ',
        'aliases':('เปิดเอไอสตูดิโอ','เปิด AI Studio','เปิดลูซี่','เปิด Lucy','เปลี่ยนสไตล์กระจก','เปิดสตูดิโอ'),
        'state':'studio',
        'replies':('เปิดเอไอสตูดิโอให้แล้วค่ะ เลือกสไตล์แล้วกดเริ่มได้เลยค่ะ',
                   'พร้อมสร้างสรรค์แล้วค่ะ เลือกเอฟเฟกต์ที่ชอบได้เลยค่ะ'),
    },
    'enter': {
        'phrase': 'เข้าหน้าหลัก',
        'aliases': ('เข้าหน้าหลัก', 'เปิดหน้าหลัก', 'เริ่มต้นระบบ'),
        'state': 'home',
        'replies': (
            'สวัสดีค่ะ ออร่าพร้อมแล้ว วันนี้เริ่มภารกิจอะไรกันดีคะ',
            'ยินดีต้อนรับกลับมาค่ะ เปิดกระจกให้แล้ว พร้อมลุยกันเลยค่ะ',
        ),
    },
    'sales': {
        'phrase': 'เช็คยอดขายนาฬิกาคริปโต',
        'aliases': ('เช็คยอดขายนาฬิกาคริปโต', 'เช็กยอดขายนาฬิกาคริปโต', 'เช็คยอดขาย', 'เช็กยอดขาย', 'ดูยอดขาย', 'ตรวจยอดขาย'),
        'state': 'sales',
        'replies': (
            'ยอดขายวันนี้ {today} บาท เดือนนี้ {month} บาท และปีนี้ {year} บาทค่ะ',
            'วันนี้ขายได้ {today} บาท เดือนนี้ {month} บาท และยอดขายปีนี้ {year} บาทค่ะ',
        ),
    },
    'home': {
        'phrase': 'กลับหน้าหลัก',
        'aliases': ('กลับหน้าหลัก', 'กลับไปหน้าหลัก', 'กลับหน้า'),
        'state': 'home',
        'replies': (
            'กลับหน้าหลักให้แล้วค่ะ กระจกพร้อม รอคำสั่งต่อไปนะคะ',
            'เรียบร้อยค่ะ กลับมากระจกส่วนตัวของคุณแล้ว',
        ),
    },
    'health': {
        'phrase': 'ตรวจสุขภาพ',
        'aliases': ('ตรวจสุขภาพ', 'ตรวจสอขภาพ', 'เช็คสุขภาพ', 'เช็กสุขภาพ', 'สแกนสุขภาพ'),
        'state': 'health',
        'replies': (
            'เปิดโหมดสุขภาพแล้วค่ะ มองตรงนิดนึงนะคะ กราฟกับจุดบนใบหน้ากำลังมา',
            'พร้อมแล้วค่ะ เปิดกราฟสุขภาพให้แล้ว หายใจสบายสบายได้เลยนะคะ',
        ),
    },
    'dark': {
        'phrase': 'ขอส่องกระจก',
        'aliases': ('ขอส่องกระจก', 'ส่องกระจก', 'โหมดกระจก', 'ปิดหน้าจอ'),
        'state': 'dark',
        'replies': (
            'ได้เลยค่ะ ปิดกล้องแล้ว พักหน้าจอให้ ส่องกระจกได้เลยนะคะ',
            'โหมดกระจกมาแล้วค่ะ คิดถึงออร่าเมื่อไหร่ กดไมค์เรียกกลับมาได้เลยนะคะ',
        ),
    },
    'tasks': {
        'phrase':'ขอสิ่งที่ต้องทำวันนี้',
        'aliases':('ขอสิ่งที่ต้องทำวันนี้','วันนี้ต้องทำอะไร','งานวันนี้','ตารางงานวันนี้','ขอรายการงานวันนี้'),
        'state':'today',
        'replies':('สิ่งที่ต้องทำวันนี้ค่ะ','มาดูงานวันนี้กันค่ะ'),
    },
    'health_report': {
        'phrase':'รายงานสุขภาพ',
        'aliases':('รายงานสุขภาพ','สรุปสุขภาพ','สรุปผลสุขภาพ','รายงานผลสุขภาพ'),
        'state':'health',
        'replies':(
            'รายงานสุขภาพเดโมวันนี้ อดนอนมากไปหน่อยนะคะ คืนนี้ลองนอนให้ครบอย่างน้อยเจ็ดชั่วโมง และจิบน้ำบ่อยบ่อยระหว่างวันค่ะ',
            'สรุปสุขภาพเดโมวันนี้ พักผ่อนน้อยไปหน่อยค่ะ คืนนี้พักให้เต็มที่ นอนให้ครบเจ็ดชั่วโมง และอย่าลืมดื่มน้ำระหว่างวันนะคะ',
        ),
    },
    'hats': {
        'phrase':'เลือกหมวก', 'aliases':('เลือกหมวก','ลองหมวก','ใส่หมวก','เปิดหมวก'), 'state':'home',
        'replies':('เลือกหมวกได้เลยค่ะ มีห้าแบบ ลองกดรูป หรือบอกหมวกเบอร์หนึ่งถึงห้าได้เลย',
                   'ห้องลองหมวกพร้อมแล้วค่ะ เลือกแบบที่ชอบ หมวกจะขยับตามศีรษะให้นะคะ'),
    },
    'hat_select': {
        'phrase':'หมวกเบอร์สอง', 'aliases':('หมวกเบอร์หนึ่ง','หมวกเบอร์สอง','ใส่หมวกแก๊ป','ใส่มงกุฎ'), 'state':'home',
        'replies':('ใส่หมวกให้แล้วค่ะ','แบบนี้น่ารักเลยค่ะ'),
    },
    'hat_off': {
        'phrase':'เอาหมวกออก', 'aliases':('เอาหมวกออก','ถอดหมวก','ปิดหมวก','เลิกใส่หมวก'), 'state':None,
        'replies':('ถอดหมวกให้แล้วค่ะ กลับมาเป็นภาพปกติแล้วนะคะ','เอาหมวกออกเรียบร้อยค่ะ'),
    },

}


def normalize(text):
    text = unicodedata.normalize('NFC', text.casefold())
    value = ''.join(c for c in text if unicodedata.category(c)[0] not in ('P','S','Z','C'))
    for source,target in (('เช็ก','ตรวจ'),('เช็ค','ตรวจ'),('เชค','ตรวจ'),
                          ('สุกภาพ','สุขภาพ'),('สุขภาบ','สุขภาพ'),('สุขะภาพ','สุขภาพ'),
                          ('สอขภาพ','สุขภาพ'),('ยอดข่าย','ยอดขาย'),('ย่อดขาย','ยอดขาย'),
                          ('หน้าแรก','หน้าหลัก'),('หน้าโฮม','หน้าหลัก'),('เลือกหมวด','เลือกหมวก'),('ถอดหมวด','ถอดหมวก')):
        value = value.replace(source,target)
    return value


def classify_command(text):
    """Return one unambiguous intent; preserve Thai vowels and reject negation first."""
    value = normalize(text)
    if not value:
        return {'key':None,'reason':'unknown','method':'none'}
    if any(word in value for word in ('ไม่','ห้าม','ยกเลิก')) or re.search(r'อย่า(?!ง)',value):
        return {'key':None,'reason':'negated','method':'guard'}
    if any(word in value for word in ('แปลว่า','หมายความว่า','ตัวอย่างประโยค','ตัวอย่างคำสั่ง')):
        return {'key':None,'reason':'unknown','method':'guard'}
    actions = ('ตรวจ','ดู','เปิด','ขอ','แสดง','สแกน','วัด','เริ่ม','สรุป','เช็ค','เช็ก','รายงาน','เข้า','ไป','กลับ')
    has_action = any(word in value for word in actions)
    candidates = set()
    if any(word in value for word in ('เอไอสตูดิโอ','เปิดสตูดิโอ','aistudio','ลูซี่','ลูซี','lucy','เปลี่ยนสไตล์กระจก')) and (has_action or value in ('ลูซี่','ลูซี','lucy','aistudio','เอไอสตูดิโอ')):
        candidates.add('studio')
    if any(word in value for word in ('สิ่งที่ต้องทำ','ต้องทำวันนี้','วันนี้ต้องทำอะไร','งานวันนี้','ตารางวันนี้')):
        candidates.add('tasks')
    if ('หมวก' in value or 'มงกุฎ' in value) and (any(word in value for word in ('ถอด','ปิด','เลิกใส่')) or ('เอา' in value and 'ออก' in value)):
        candidates.add('hat_off')
    elif parse_hat_choice(value) is not None and ('หมวก' in value or 'มงกุฎ' in value):
        candidates.add('hat_select')
    elif 'หมวก' in value and (any(word in value for word in ('เลือก','ลอง','ใส่','เปิด','ขอ','เปลี่ยน')) or value=='หมวก'):
        candidates.add('hats')
    if ('ยอดขาย' in value or 'รายรับ' in value or 'รายได้' in value) and (has_action or value in ('ยอดขาย','รายรับ','รายได้')):
        candidates.add('sales')
    if 'สุขภาพ' in value and (has_action or value=='สุขภาพ'):
        candidates.add('health_report' if any(word in value for word in ('รายงาน','สรุป','ผลสุขภาพ')) else 'health')
    if any(word in value for word in ('ส่องกระจก','โหมดกระจก','ปิดหน้าจอ','พักหน้าจอ','จอดำ','หน้าจอดำ')) or value=='กระจก':
        candidates.add('dark')
    if 'หน้าหลัก' in value or 'หน้าปกติ' in value:
        if any(word in value for word in ('กลับ','ย้อน','คืน')):
            candidates.add('home')
        elif has_action or value in ('หน้าหลัก','หน้าปกติ'):
            candidates.add('enter')
    if 'เริ่มต้นระบบ' in value or 'เริ่มระบบ' in value or 'เปิดระบบ' in value:
        candidates.add('enter')
    if value=='กลับหน้า':
        candidates.add('home')
    if len(candidates)>1:
        return {'key':None,'reason':'ambiguous','method':'keywords'}
    if candidates:
        return {'key':candidates.pop(),'reason':'matched','method':'keywords'}
    # Remove conversational padding before conservative, whole-phrase fuzzy matching.
    compact=value
    for filler in ('ออร่า','จาร์วิส','ช่วย','ให้หน่อย','ได้ไหม','หน่อย','ครับ','ค่ะ','นะคะ','นะ','ด้วย','กรุณา'):
        compact=compact.replace(filler,'')
    scores=[]
    for key,command in COMMANDS.items():
        score=max((SequenceMatcher(None,compact,normalize(alias)).ratio()
                   for alias in command['aliases']
                   if len(compact)>=5 and .7<=len(compact)/len(normalize(alias))<=1.4),default=0)
        scores.append((score,key))
    scores.sort(reverse=True)
    best,key=scores[0]
    if best>=.84 and best-scores[1][0]>=.12:
        return {'key':key,'reason':'matched','method':'fuzzy'}
    return {'key':None,'reason':'unknown','method':'none'}


def match_command(text):
    return classify_command(text)['key']


def select_transcript(response):
    """Try recognizer alternatives only if the first transcript is not actionable."""
    if isinstance(response,str):
        return response
    alternatives=response.get('alternative',[]) if isinstance(response,dict) else []
    texts=[item.get('transcript','') for item in alternatives[:5] if item.get('transcript')]
    if not texts:
        return ''
    first=classify_command(texts[0])
    if first['key'] or first['reason'] in ('negated','ambiguous'):
        return texts[0]
    valid=[(text,classify_command(text)['key']) for text in texts[1:]]
    intents={key for text,key in valid if key}
    if len(intents)==1:
        return next(text for text,key in valid if key)
    return texts[0]


class CommandEngine:
    def __init__(self):
        self.state = 'standby'
        self.counts = {key: 0 for key in COMMANDS}
        self.hat_choice = None

    def handle(self, text):
        match = classify_command(text)
        key = match['key']
        self.hat_choice = None
        if match['reason'] == 'negated':
            return None, 'รับทราบค่ะ ยังไม่เปลี่ยนหน้านะคะ'
        if match['reason'] == 'ambiguous':
            return None, 'ได้ยินหลายคำสั่งค่ะ ขอทีละคำสั่งนะคะ เช่น ดูยอดขาย หรือ ตรวจสุขภาพ'
        if key is None:
            return None, ''
        if self.state == 'standby' and key not in ('enter', 'dark', 'hat_off'):
            return None, 'พูด เข้าหน้าหลัก เพื่อเริ่มกันก่อนนะคะ'
        if self.state == 'dark' and key not in ('enter', 'home', 'dark', 'hat_off'):
            return None, 'เรียกหน้าหลักก่อนนะคะ พูด เข้าหน้าหลัก หรือ กลับหน้าหลัก ได้เลยค่ะ'
        command = COMMANDS[key]
        reply = command['replies'][self.counts[key] % 2]
        self.counts[key] += 1
        if command['state'] is not None:
            self.state = command['state']
        if key == 'tasks':
            reply = DailyTasks().spoken_report()
        if key == 'sales':
            reply = sales_spoken_report((self.counts[key]-1)%2)
        if key == 'hat_select':
            self.hat_choice = parse_hat_choice(normalize(text))
            if self.hat_choice is not None:
                reply = 'ใส่'+HATS[self.hat_choice]['name']+'ให้แล้วค่ะ น่ารักเลยนะคะ'
        return key, reply


# THB, same current/comparison period length; these are seeded artwork data.
SALES = {
    'daily': {'title': 'รายวัน', 'subtitle': '7 DAYS / PREVIOUS 7 DAYS',
              'labels': ('MON','TUE','WED','THU','FRI','SAT','SUN'),
              'current': (12900,25800,19350,38700,32250,51600,45150),
              'previous': (9675,19350,16125,25800,29025,35475,32250)},
    'monthly': {'title': 'รายเดือน', 'subtitle': '6 MONTHS / PREVIOUS 6 MONTHS',
                'labels': ('MAY','JUN','JUL','AUG','SEP','OCT'),
                'current': (245100,296700,322500,387000,438600,516000),
                'previous': (193500,232200,270900,309600,335400,387000)},
    'yearly': {'title': 'รายปี', 'subtitle': '5 YEARS / MATCHED YEAR-AGO',
               'labels': ('2022','2023','2024','2025','2026'),
               'current': (1548000,2064000,2838000,3612000,4644000),
               'previous': (1290000,1548000,2064000,2838000,3612000)},
}


def sales_summary(period):
    data = SALES[period]
    current, previous = sum(data['current']), sum(data['previous'])
    return current, (current / previous - 1) * 100


def sales_snapshot(period):
    data=SALES[period]
    current,previous=data['current'][-1],data['previous'][-1]
    return current,(current/previous-1)*100


def sales_spoken_report(variant=0):
    today=sales_snapshot('daily')[0]
    month=sales_snapshot('monthly')[0]
    year=sales_snapshot('yearly')[0]
    template=COMMANDS['sales']['replies'][variant%2]
    return template.format(today=f'{today:,.0f}',month=f'{month:,.0f}',year=f'{year:,.0f}')
