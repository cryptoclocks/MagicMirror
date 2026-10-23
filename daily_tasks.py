"""Editable local agenda; completions are scoped to the date in Bangkok."""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parent


def today():
    return datetime.now(ZoneInfo('Asia/Bangkok')).date().isoformat()


class DailyTasks:
    def __init__(self,source=None,state=None):
        self.source=Path(source) if source else ROOT/'daily_tasks.json'
        self.state=Path(state) if state else ROOT/'.local/tasks-state.json'

    def data(self):
        return json.loads(self.source.read_text())

    def completed(self,date=None):
        try:
            return set(json.loads(self.state.read_text()).get(date or today(),[]))
        except (FileNotFoundError,ValueError):
            return set()

    def toggle(self,task_id,date=None):
        date=date or today()
        if task_id not in {task['id'] for task in self.data()['tasks']}:
            return
        try:
            state=json.loads(self.state.read_text())
        except (FileNotFoundError,ValueError):
            state={}
        done=set(state.get(date,[]))
        done.symmetric_difference_update({task_id})
        state[date]=sorted(done)
        self.state.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.state.with_suffix('.tmp')
        temporary.write_text(json.dumps(state,ensure_ascii=False,indent=2))
        temporary.replace(self.state)

    def spoken_report(self):
        data=self.data()
        done=self.completed()
        tasks=[task for task in data['tasks'] if task['id'] not in done]
        prefix='รายการเดโมวันนี้' if data.get('is_demo',False) else 'สิ่งที่ต้องทำวันนี้'
        if not tasks:
            return prefix+' ทำครบแล้วค่ะ เก่งมากเลย พักสักนิดได้นะคะ'
        items=[]
        for task in tasks:
            hour,minute=map(int,task['time'].split(':'))
            clock=f'{hour} นาฬิกา'+(f' {minute} นาที' if minute else '')
            items.append(clock+' '+task['title'])
        return prefix+' มี '+str(len(tasks))+' อย่างค่ะ '+ ' ต่อด้วย '.join(items)+'ค่ะ'
