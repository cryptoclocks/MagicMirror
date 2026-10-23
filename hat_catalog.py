"""Photorealistic transparent PNG hats and per-asset forehead fitting anchors."""
import re

HATS=(
    {'id':'cap','name':'หมวกแก๊ป','aliases':('แก๊ป','แก๊บ','แคป','เบสบอล'),'width':1.18,'anchor':(.50,.76)},
    {'id':'top-hat','name':'หมวกทรงสูง','aliases':('ทรงสูง','ท็อปแฮท','มายากล'),'width':1.55,'anchor':(.50,.87)},
    {'id':'sun-hat','name':'หมวกปีกกว้าง','aliases':('ปีกกว้าง','หมวกฟาง','หมวกกันแดด'),'width':1.95,'anchor':(.50,.75)},
    {'id':'graduation','name':'หมวกรับปริญญา','aliases':('ปริญญา','บัณฑิต'),'width':1.85,'anchor':(.50,.81)},
    {'id':'crown','name':'มงกุฎ','aliases':('มงกุฎ','เจ้าหญิง','ราชา'),'width':1.12,'anchor':(.50,.95)},
)


def parse_hat_choice(value):
    for index,hat in enumerate(HATS):
        if any(alias in value for alias in hat['aliases']):
            return index
    number=re.search(r'หมวก(?:ใบ)?(?:เบอร์|หมายเลข|แบบที่|ที่|แบบ)?([1-5๑-๕]|หนึ่ง|สอง|สาม|สี่|ห้า)',value)
    if number:
        token=number.group(1)
        numbers={'หนึ่ง':0,'สอง':1,'สาม':2,'สี่':3,'ห้า':4}
        if token in numbers:
            return numbers[token]
        return int(token)-1
    return None
