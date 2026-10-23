"""Head-anchored hat drawing from measured OpenCV facial landmarks."""
import math
from pathlib import Path
import numpy as np
from PySide6.QtCore import QRectF,Qt
from PySide6.QtGui import QImage,QPainter,QColor
from face_landmarks import map_to_view
from hat_catalog import HATS


class HatArt:
    """Preserve photo proportions and crop only unused transparent padding at render time."""
    def __init__(self,path):
        self.image=QImage(str(path)).convertToFormat(QImage.Format.Format_RGBA8888)
        if not self.image.isNull():
            raw=np.frombuffer(self.image.constBits(),np.uint8).reshape(self.image.height(),self.image.bytesPerLine()//4,4)
            yy,xx=np.where(raw[:,:self.image.width(),3]>220)
            if len(xx):
                left,right=max(0,int(xx.min())-2),min(self.image.width(),int(xx.max())+3)
                top,bottom=max(0,int(yy.min())-2),min(self.image.height(),int(yy.max())+3)
                self.image=self.image.copy(left,top,right-left,bottom-top)

    def isValid(self):
        return not self.image.isNull()

    def render(self,p,bounds):
        if not self.isValid():
            return
        scale=min(bounds.width()/self.image.width(),bounds.height()/self.image.height())
        width,height=self.image.width()*scale,self.image.height()*scale
        target=QRectF(bounds.center().x()-width/2,bounds.center().y()-height/2,width,height)
        p.save()
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform,True)
        p.drawImage(target,self.image)
        p.restore()


class HatRenderer:
    def __init__(self):
        root=Path(__file__).resolve().parent/'assets/hats'
        self.art=[HatArt(root/(hat['id']+'.png')) for hat in HATS]

    def draw(self,p,index,pose,scale=1.,offset=0.):
        if pose is None or not 0<=index<len(HATS):
            return
        hat=HATS[index]
        width=pose['width']*hat['width']*scale
        art=self.art[index]
        if not art.isValid():
            return
        height=width*art.image.height()/art.image.width()
        p.save()
        p.translate(*pose['anchor'])
        p.rotate(pose['angle'])
        p.translate(0,pose['width']*offset)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0,0,0,25))
        p.drawEllipse(QRectF(-width*.27,-2,width*.54,9))
        ax,ay=hat['anchor']
        self.art[index].render(p,QRectF(-width*ax,-height*ay,width,height))
        p.restore()


def head_pose(landmarks,frame_size):
    """Use eyes for roll, chin for vertical scale, jaw for width; no box guessing."""
    if not landmarks or not landmarks.get('points'):
        return None
    points=np.asarray(map_to_view(landmarks['points'],frame_size),dtype=np.float64)
    if points.shape!=(68,2) or not np.isfinite(points).all():
        return None
    left,right=points[36:42].mean(axis=0),points[42:48].mean(axis=0)
    axis=right-left
    distance=np.linalg.norm(axis)
    if distance<8:
        return None
    axis/=distance
    down=np.array([-axis[1],axis[0]])
    eyes=(left+right)/2
    chin_distance=float(np.dot(points[8]-eyes,down))
    if chin_distance<distance*.4:
        return None
    width=max(float(np.linalg.norm(points[16]-points[0])),distance*2.05)
    anchor=eyes-down*chin_distance*.46
    return {'anchor':tuple(anchor),'width':width,'angle':math.degrees(math.atan2(axis[1],axis[0]))}
