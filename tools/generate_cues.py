"""Create two tiny synthesized UI cues, no downloaded audio."""
from pathlib import Path
import math
import struct
import wave
root=Path(__file__).resolve().parents[1]/'assets'
root.mkdir(exist_ok=True)
for name,notes in (('listen',(660,990)),('confirm',(880,1100,1320))):
    values=[]
    rate=24000
    for note in notes:
        length=int(rate*.065)
        for i in range(length):
            envelope=math.sin(math.pi*i/length)**2
            values.append(int(8000*envelope*math.sin(math.tau*note*i/rate)))
    with wave.open(str(root/f'{name}.wav'),'wb') as f:
        f.setparams((1,2,rate,len(values),'NONE','not compressed'))
        f.writeframes(struct.pack('<'+'h'*len(values),*values))
