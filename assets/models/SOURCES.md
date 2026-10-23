# OpenCV LBF face landmarks model

- Runtime file: `lbfmodel.yaml` (68-point facial landmarks)
- Source: https://github.com/kurnianggoro/GSOC2017/blob/master/data/lbfmodel.yaml
- Download: https://raw.githubusercontent.com/kurnianggoro/GSOC2017/master/data/lbfmodel.yaml
- SHA-256: `70dd8b1657c42d1595d6bd13d97d932877b3bed54a95d3c4733a0f740d1fd66b`
- Algorithm: OpenCV `cv2.face.createFacemarkLBF`, with optical flow between model fits.
- OpenCV reference: https://docs.opencv.org/4.x/d5/d47/tutorial_table_of_content_facemark.html

This is a required runtime model, not a temporary download. Installation and
checksum verification are in `tools/setup_landmarks.py`. Camera images are
processed locally and are not uploaded by this feature.
