import {FilesetResolver,ImageSegmenter,FaceLandmarker,PoseLandmarker} from '@mediapipe/tasks-vision';
let files,segmenter,face,pose,mode='background';
self.onmessage=async event=>{
  const message=event.data;
  try{
    if(message.kind==='init'){
      mode=message.mode;
      files=await FilesetResolver.forVisionTasks(message.base+'tracking/wasm');
      if(mode==='background')segmenter=await ImageSegmenter.createFromOptions(files,{
        baseOptions:{modelAssetPath:message.base+'tracking/selfie_segmenter.tflite',delegate:'CPU'},runningMode:'VIDEO',outputConfidenceMasks:true,outputCategoryMask:false});
      else{
        face=await FaceLandmarker.createFromOptions(files,{baseOptions:{modelAssetPath:message.base+'tracking/face_landmarker.task',delegate:'CPU'},runningMode:'VIDEO',numFaces:1,outputFaceBlendshapes:true,outputFacialTransformationMatrixes:true});
        pose=await PoseLandmarker.createFromOptions(files,{baseOptions:{modelAssetPath:message.base+'tracking/pose_landmarker_lite.task',delegate:'CPU'},runningMode:'VIDEO',numPoses:1});
      }
      self.postMessage({kind:'ready',labels:segmenter?.getLabels()||[]});return;
    }
    if(message.kind==='frame'){
      const bitmap=message.bitmap,started=performance.now();
      try{
        if(segmenter){
          const result=segmenter.segmentForVideo(bitmap,message.time);
          const labels=segmenter.getLabels();
          let index=labels.findIndex(label=>/person|foreground|selfie/i.test(label));
          if(index<0)index=result.confidenceMasks.length===1?0:1;
          const mask=result.confidenceMasks[index];const pixels=mask.getAsFloat32Array().slice();
          self.postMessage({kind:'mask',width:mask.width,height:mask.height,pixels,ms:performance.now()-started},[pixels.buffer]);result.close();
        }else{
          const f=face.detectForVideo(bitmap,message.time),p=pose.detectForVideo(bitmap,message.time);
          self.postMessage({kind:'pose',landmarks:p.landmarks[0]||null,world:p.worldLandmarks[0]||null,
            face:f.faceLandmarks[0]||null,blendshapes:f.faceBlendshapes[0]?.categories||[],
            matrix:f.facialTransformationMatrixes[0]?.data||null,ms:performance.now()-started});
        }
      }finally{bitmap.close();}
    }
  }catch(error){self.postMessage({kind:'error',message:String(error?.message||error)});}
};
