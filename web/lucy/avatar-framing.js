// Require several consistent observations; missing landmarks never change framing.
export class AvatarFraming {
  constructor(){this.mode='half';this.candidate=null;this.since=0;}
  update(points,now){
    const visible=i=>points?.[i]&&points[i].visibility>.6&&points[i].y>.01&&points[i].y<.97;
    if(!visible(11)||!visible(12))return this.mode;
    const next=visible(27)&&visible(28)?'full':'half';
    if(next!==this.candidate){this.candidate=next;this.since=now;}
    if(now-this.since>450)this.mode=next;
    return this.mode;
  }
}
