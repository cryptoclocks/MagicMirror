"""Different procedural infographic animations for each simulated health metric."""
import math
from PySide6.QtCore import QPointF,QRectF,Qt
from PySide6.QtGui import QColor,QLinearGradient,QPainterPath
from health_profile import OXYGEN_PERCENT,RESPIRATIONS_PER_MINUTE,TEMPERATURE_C,ENERGY_VISUAL_SCORE,cycle


def stroke(view,p,path,shade,width=1.3):
    p.setPen(view.pen(shade,width+5,18));p.drawPath(path)
    p.setPen(view.pen(shade,width));p.drawPath(path)


def draw(view,p,x,y,shade,t,kind):
    from smartmirror import color
    p.save()
    p.setBrush(Qt.BrushStyle.NoBrush)
    cx,cy=x+205,y+62
    if kind=='oxygen':
        radius=26
        p.setPen(view.pen(shade,3,35))
        p.drawEllipse(QRectF(cx-radius,cy-radius,radius*2,radius*2))
        p.setPen(view.pen(shade,2,220))
        p.drawArc(QRectF(cx-radius,cy-radius,radius*2,radius*2),90*16,-int(360*OXYGEN_PERCENT/100*16))
        view.text(p,cx-11,cy+5,'O2',14,shade,0,True)
        for i in range(3):
            a=t*.9+i*math.tau/3
            px,py=cx+math.cos(a)*radius,cy+math.sin(a)*radius
            p.setPen(view.pen(shade,1,90));p.setBrush(color(shade,32))
            p.drawEllipse(QRectF(px-6,py-6,12,12))
            p.setBrush(color('#e7fff7'));p.drawEllipse(QRectF(px-2,py-2,4,4))
            p.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(29):
            light=180+65*math.sin(t*2-i*.3)
            fraction=max(0,min(1,OXYGEN_PERCENT/100*29-i))
            p.fillRect(QRectF(x+18+i*7.7,y+96,4,6),color(shade,30))
            p.fillRect(QRectF(x+18+i*7.7,y+96,4*fraction,6),color(shade,light))
    elif kind=='breath':
        breath=.96+.12*math.sin(math.tau*cycle(t,RESPIRATIONS_PER_MINUTE))
        p.save();p.translate(cx,cy);p.scale(breath,breath)
        for side in (-1,1):
            lung=QPainterPath(QPointF(side*4,-19))
            lung.cubicTo(side*17,-31,side*29,-5,side*27,13)
            lung.cubicTo(side*25,24,side*7,24,side*5,12)
            lung.lineTo(side*4,-19)
            p.fillPath(lung,color(shade,20+20*(breath-.84)))
            stroke(view,p,lung,shade)
            view.path(p,[(0,-25),(0,-9),(side*12,1),(side*18,12)],shade,1)
            view.path(p,[(side*12,1),(side*21,-4)],shade,.8,False)
        p.restore()
        view.path(p,[(x+18+i,y+99+4*math.sin(i/28-math.tau*cycle(t,RESPIRATIONS_PER_MINUTE))) for i in range(219)],shade,1)
        view.text(p,x+145,y+123,'INHALE' if math.cos(math.tau*cycle(t,RESPIRATIONS_PER_MINUTE))>0 else 'EXHALE',8,shade,.5)
    elif kind=='temp':
        p.setPen(view.pen(shade,1.2,210))
        p.drawRoundedRect(QRectF(cx-4,cy-27,8,44),4,4)
        p.drawEllipse(QRectF(cx-8,cy+12,16,16))
        fill=44*(TEMPERATURE_C-35)/5
        p.fillRect(QRectF(cx-2,cy+17-fill,4,fill),color(shade,180+70*math.sin(t*1.4)))
        p.setBrush(color(shade));p.drawEllipse(QRectF(cx-5,cy+15,10,10))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(5):
            view.path(p,[(cx+9,cy-23+i*8),(cx+15,cy-23+i*8)],shade,.8,False)
        gradient=QLinearGradient(x+18,0,x+237,0)
        gradient.setColorAt(0,QColor('#55bffe'));gradient.setColorAt(.5,QColor(shade));gradient.setColorAt(1,QColor('#ff6587'))
        p.fillRect(QRectF(x+18,y+98,219,4),gradient)
        position=x+18+219*(TEMPERATURE_C-35)/5
        view.path(p,[(position-4,y+109),(position,y+104),(position+4,y+109)],shade,1,False)
    elif kind=='energy':
        for radius,speed,span,alpha in ((27,24,int(360*ENERGY_VISUAL_SCORE/100),200),(20,-40,210,110)):
            p.setPen(view.pen(shade,2,alpha))
            p.drawArc(QRectF(cx-radius,cy-radius,radius*2,radius*2),int(t*speed*16),span*16)
        bolt=QPainterPath(QPointF(cx+4,cy-17))
        for px,py in ((cx-10,cy+2),(cx-1,cy+2),(cx-5,cy+17),(cx+11,cy-4),(cx+2,cy-4)):
            bolt.lineTo(px,py)
        bolt.closeSubpath()
        p.fillPath(bolt,color(shade,125+95*(.5+.5*math.sin(t*3))))
        stroke(view,p,bolt,shade,1)
        for i in range(12):
            fraction=max(0,min(1,ENERGY_VISUAL_SCORE/100*12-i))
            p.fillRect(QRectF(x+18+i*18.2,y+95,14,10),color(shade,30))
            p.fillRect(QRectF(x+18+i*18.2,y+95,14*fraction,10),color(shade,185+65*math.sin(t*2-i*.3)))
        view.text(p,x+155,y+123,'VISUAL INDEX',8,shade,.5)
    p.restore()


def sleep(view,p,x,y,t,shade):
    from smartmirror import color
    cx,cy=x+205,y+64
    moon=QPainterPath();moon.addEllipse(QRectF(cx-20,cy-20,40,40))
    cut=QPainterPath();cut.addEllipse(QRectF(cx-7,cy-27,39,39))
    moon=moon.subtracted(cut)
    p.save();p.setBrush(Qt.BrushStyle.NoBrush)
    p.fillPath(moon,color(shade,28));stroke(view,p,moon,shade,1.4)
    for i in range(3):
        yy=cy-18-i*10-3*math.sin(t+i)
        view.text(p,cx+12+i*4,yy,'z',8+i*2,shade,.1)
    p.restore()
