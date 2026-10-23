"""Download and verify the OpenCV LBF model, only when it is not already present."""
import hashlib
from pathlib import Path
import urllib.request

MODEL=Path(__file__).resolve().parents[1]/'assets/models/lbfmodel.yaml'
URL='https://raw.githubusercontent.com/kurnianggoro/GSOC2017/master/data/lbfmodel.yaml'
SHA256='70dd8b1657c42d1595d6bd13d97d932877b3bed54a95d3c4733a0f740d1fd66b'


def ensure_model():
    if MODEL.exists() and hashlib.sha256(MODEL.read_bytes()).hexdigest()==SHA256:
        return
    MODEL.parent.mkdir(parents=True,exist_ok=True)
    temporary=MODEL.with_suffix('.yaml.download')
    try:
        print('Downloading OpenCV 68-point face landmark model (54 MB)…',flush=True)
        with urllib.request.urlopen(URL,timeout=30) as response, temporary.open('wb') as target:
            while True:
                chunk=response.read(1024*1024)
                if not chunk:
                    break
                target.write(chunk)
        if hashlib.sha256(temporary.read_bytes()).hexdigest()!=SHA256:
            raise RuntimeError('Face model checksum mismatch; source may have changed')
        temporary.replace(MODEL)
    finally:
        temporary.unlink(missing_ok=True)


if __name__=='__main__':
    ensure_model()
