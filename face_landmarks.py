"""OpenCV LBF 68-point fitting with optical flow between detector frames."""
import time
from pathlib import Path
import cv2
import numpy as np

MODEL = Path(__file__).resolve().parent/'assets/models/lbfmodel.yaml'


def mesh_edges(points):
    points = np.asarray(points,dtype=np.float32).reshape(-1,2)
    low = np.floor(points.min(axis=0))-2
    high = np.ceil(points.max(axis=0))+2
    subdivision = cv2.Subdiv2D((int(low[0]),int(low[1]),int(high[0]-low[0]),int(high[1]-low[1])))
    for point in points:
        subdivision.insert(tuple(float(v) for v in point))
    edges=set()
    for triangle in subdivision.getTriangleList():
        vertices=triangle.reshape(3,2)
        ids=[int(np.argmin(np.sum((points-v)**2,axis=1))) for v in vertices]
        if any(np.linalg.norm(points[i]-v)>.1 for i,v in zip(ids,vertices)):
            continue
        for a,b in ((ids[0],ids[1]),(ids[1],ids[2]),(ids[2],ids[0])):
            if a!=b:
                edges.add(tuple(sorted((a,b))))
    # Keep the anatomical contours explicit, including closed eyelids and lips.
    for start,end,closed in ((0,16,False),(17,21,False),(22,26,False),(27,30,False),
                             (31,35,False),(36,41,True),(42,47,True),(48,59,True),(60,67,True)):
        edges.update((i,i+1) for i in range(start,end))
        if closed:
            edges.add((start,end))
    return tuple(sorted(edges))


def map_to_view(points,frame_size,view_size=(1440,900)):
    """Map normalized source coordinates through the same center-crop as the video."""
    iw,ih=frame_size
    vw,vh=view_size
    scale=max(vw/iw,vh/ih)
    return [(float(x)*iw*scale+(vw-iw*scale)/2,
             float(y)*ih*scale+(vh-ih*scale)/2) for x,y in points]


class LandmarkTracker:
    def __init__(self,model=MODEL):
        if not hasattr(cv2,'face'):
            raise RuntimeError('Install opencv-contrib-python for facial landmarks')
        if not Path(model).is_file():
            raise RuntimeError('Landmark model missing: run tools/setup_landmarks.py')
        self.facemark=cv2.face.createFacemarkLBF()
        self.facemark.loadModel(str(model))
        self.reset()

    def reset(self):
        self.points=None
        self.previous_gray=None
        self.last_fit=-100.
        self.last_detection=-100.
        self.last_attempt=-100.
        self.edges=()

    def process(self,gray,box=None,now=None):
        now=time.monotonic() if now is None else now
        flowed=None
        if self.points is not None and self.previous_gray is not None:
            previous=self.points.astype(np.float32).reshape(-1,1,2)
            current,status,_=cv2.calcOpticalFlowPyrLK(self.previous_gray,gray,previous,None,
                                                   winSize=(21,21),maxLevel=3)
            if current is not None:
                backward,reverse_status,_=cv2.calcOpticalFlowPyrLK(gray,self.previous_gray,current,None,
                                                               winSize=(21,21),maxLevel=3)
                if backward is not None:
                    error=np.linalg.norm(backward-previous,axis=2).ravel()
                    good=(status.ravel()>0)&(reverse_status.ravel()>0)&(error<2.5)
                    # Jaw/eyebrow points often have little texture. Recover their motion
                    # from reliable face points rather than dropping all 68 points.
                    if np.count_nonzero(good)>=24:
                        moved=current.reshape(-1,2)
                        transform,inliers=cv2.estimateAffinePartial2D(
                            self.points[good],moved[good],method=cv2.RANSAC,
                            ransacReprojThreshold=2.5)
                        if transform is not None and inliers is not None and inliers.sum()>=18:
                            scale=float(np.hypot(transform[0,0],transform[1,0]))
                            if .8<scale<1.25:
                                flowed=cv2.transform(self.points[None],transform)[0]
                                reliable=np.flatnonzero(good)[inliers.ravel().astype(bool)]
                                # Keep expression motion, but suppress noisy local flow.
                                flowed[reliable]+=(moved[reliable]-flowed[reliable])*.45
        fitted=None
        if box is not None:
            self.last_detection=now
        elif (flowed is not None and now-self.last_detection<1.0
              and now-self.last_attempt>=.18):
            # Haar can miss a moving or slightly turned face. Fit the current
            # tracked ROI, never a stale rectangle or an indefinitely held pose.
            low=flowed.min(axis=0)
            high=flowed.max(axis=0)
            span=high-low
            box=(max(0,int(low[0]-span[0]*.10)),
                 max(0,int(low[1]-span[1]*.35)),
                 int(span[0]*1.20),int(span[1]*1.50))
            box=(box[0],box[1],min(box[2],gray.shape[1]-box[0]),
                 min(box[3],gray.shape[0]-box[1]))
            if box[2]<20 or box[3]<20:
                box=None
        if box is not None:
            self.last_attempt=now
            rect=np.asarray([box],dtype=np.int32)
            ok,landmarks=self.facemark.fit(gray,rect)
            if ok and len(landmarks):
                candidate=np.asarray(landmarks[0],dtype=np.float32).reshape(-1,2)
                x,y,w,h=box
                if candidate.shape==(68,2) and np.isfinite(candidate).all():
                    within=((candidate[:,0]>x-w*.25)&(candidate[:,0]<x+w*1.25)&
                            (candidate[:,1]>y-h*.25)&(candidate[:,1]<y+h*1.4))
                    agrees=(flowed is None or
                            np.median(np.linalg.norm(candidate-flowed,axis=1))<w*.16)
                    if within.all() and agrees:
                        fitted=candidate
        if fitted is not None:
            # Flow already follows this frame's head movement. Smooth only the
            # fit correction, avoiding the lag of averaging old screen positions.
            self.points=fitted if flowed is None else fitted*.30+flowed*.70
            self.last_fit=now
            if not self.edges:
                self.edges=mesh_edges(self.points)
        elif (flowed is not None and now-self.last_fit<=1.0
              and now-self.last_detection<=1.2):
            self.points=flowed
        else:
            self.points=None
            self.edges=()
        self.previous_gray=gray.copy()
        if self.points is None:
            return None
        height,width=gray.shape[:2]
        normalized=self.points/np.array((width,height),np.float32)
        return {'points':normalized.tolist(),'edges':self.edges}
