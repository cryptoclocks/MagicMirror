"""Local motion compensation for delayed AI keyframes; not generative video inference."""
import base64
import threading
import cv2
import numpy as np


def decode(value, grayscale=False):
    raw=base64.b64decode(value,validate=True)
    if len(raw)>2*1024*1024:raise ValueError('Frame too large')
    image=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_GRAYSCALE if grayscale else cv2.IMREAD_COLOR)
    if image is None or image.shape[:2]!=(512,512):raise ValueError('Expected 512x512 frame')
    return image


class MotionBuffer:
    def __init__(self):
        self.lock=threading.Lock();self.previous=None

    def reset(self):
        with self.lock:self.previous=None

    def begin(self, data):
        source=decode(data['image']);edited=decode(data['output']);mask=decode(data['mask'],True)
        with self.lock:
            self.previous=cv2.resize(cv2.cvtColor(source,cv2.COLOR_BGR2GRAY),(256,256))
            self.edited=edited
            self.mask=mask.astype(np.float32)/255.
            yy,xx=np.indices((512,512),dtype=np.float32)
            self.grid=np.stack((xx,yy),axis=-1)
            self.mapping=self.grid.copy();self.frames=0

    def step(self, data):
        frame=decode(data['image'])
        gray=cv2.resize(cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY),(256,256))
        with self.lock:
            if self.previous is None or self.frames>=128:raise ValueError('Motion buffer expired')
            # Backward flow maps each new pixel into the previous source frame.
            flow=cv2.calcOpticalFlowFarneback(gray,self.previous,None,.5,3,21,3,5,1.2,0)
            displacement=cv2.resize(flow,(512,512))*2.
            backward=self.grid+displacement
            self.mapping=cv2.remap(self.mapping,backward[:,:,0],backward[:,:,1],cv2.INTER_LINEAR,
                                   borderMode=cv2.BORDER_REPLICATE)
            mapped=cv2.remap(self.edited,self.mapping[:,:,0],self.mapping[:,:,1],cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_REFLECT_101)
            alpha=cv2.remap(self.mask,self.mapping[:,:,0],self.mapping[:,:,1],cv2.INTER_LINEAR,
                            borderMode=cv2.BORDER_CONSTANT)
            alpha=cv2.GaussianBlur(alpha,(0,0),1.2)[:,:,None]
            output=np.clip(mapped*alpha+frame*(1-alpha),0,255).astype(np.uint8)
            self.previous=gray;self.frames+=1
        return base64.b64encode(cv2.imencode('.jpg',output,[cv2.IMWRITE_JPEG_QUALITY,88])[1]).decode()
