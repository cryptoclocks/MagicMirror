# Lucy / AURA AI Studio investigation

Investigated 2026-10-24 using the installed REA skill from
[morluto/rea](https://github.com/morluto/rea).

## Observed and supported

- Fetching `https://lucy.decart.ai/` returned HTTP 429. No authenticated browser
  session or production inference was inspected. We did not recover that site's
  complete application or its server model.
- Instead, inspected the official published `@decartai/sdk@0.2.12` npm package,
  distributed from `https://registry.npmjs.org/@decartai/sdk/-/sdk-0.2.12.tgz`.
- REA statically parsed 50 JavaScript files without executing them. Its semantic
  graph is **partial** owing to analysis resource limits; dynamic reachability
  is unknown. This is SDK artifact evidence, not proof of the website's runtime.
- `dist/realtime/media-channel.js` contains LiveKit room setup, video track
  publication and subscriptions to returned inference video tracks.
- `dist/realtime/livekit.js` dynamically loads `livekit-client`.
- `dist/shared/model.js` defines Lucy 2.5 at 1280×720, up to 30 input FPS.
- `dist/tokens/client.js` mints tokens using `POST /v1/client/tokens` with
  `X-API-KEY`. A permanent key stays in Python; only a short-lived, model/origin
  scoped credential is returned to our local embedded page.

Evidence references retained by REA:

- Application parent: `ev_fdd40867011d65196a4ac993a8003cdcd4abdfc80d40d36abfd906be616e63d2`
- Summary: `ev_b259694b45697351daaa3b21d856a2f9e739ac25988bf0a60e32ea80cf024ea3`
- Module inventory: `ev_d2527e03e60f58e94f3ad85beb7dfd689140dab03e2192e8c7f1f96beac16c48`
- Selected media module view: `ev_b87bed5d23f917cacc33d6d22ff5089ca1521f06dc4e1b625755bff3ceca0868`
- Extracted tree SHA-256: `759f8e2c099d3aa9719cca0ebc955c0353a285a832a25cefa116a0074c0cbc7d`

Retained REA IDs are session references, not public URLs. Artifact facts above
also identify filenames so the investigation can be repeated from the versioned
npm package. No downloaded SDK analysis tree is required at runtime.

## Principle and remaining unknowns

The supported integration is: camera → WebRTC/LiveKit → Decart inference service
with a text prompt → transformed video → display. This differs from the mirror's
local OpenCV geometry/skin filters: the generative model can restyle clothing,
people and the scene rather than only deform existing pixels.

The cloud media flow is corroborated by the official
[Realtime documentation](https://docs.platform.decart.ai/sdks/python-realtime),
[SDK](https://github.com/DecartAI/sdk) and
[onboarding example](https://api-onboarding.decart.ai/).
Model weights, training data, denoising pipeline and exact server architecture
were not recovered. We cannot claim an offline clone or equivalent latency.

## Implementation and verification

AURA embeds its own local AI Studio UI and uses the official MIT-licensed SDK.
No Lucy website UI or private endpoints are copied. SDK dependencies and license
notices are bundled; Node is needed only when rebuilding frontend assets.
Python SDK integration was considered, but its Python >=3.10, websockets >=15
and opencv-python dependencies conflict with this app's existing Python 3.9 /
OpenCV contrib / websockets 13 environment. Embedded WebRTC avoids changing it.

- Start is manual, with an explicit cloud-video button; audio is never captured.
- Local preview is usable without a key and does not send video.
- Home/health/sales/dark transitions tear down the studio and release its camera.
- Stop invalidates late capture/connection completions and stops local tracks.
- A session stops after two minutes; setup timeout and stalled-video detection
  stop the camera. A fresh Start is required for another session.
- Credentials are excluded from Git. Loopback server serves an exact asset list,
  requires same-origin token requests and uses an unguessable studio URL.
- Automated checks cover lifecycle races, token scoping, cross-origin rejection,
  asset isolation, upstream error redaction and command gates.
- Embedded page loading/rendering and returning home were exercised offscreen.
- No Decart key was present, so authenticated video generation, real output
  quality, cost and end-to-end latency remain **unverified**.

## Follow-up: local operation (2026-10-24)

The broader DecartAI organization search found an important separate option:
[Lucy-Edit-ComfyUI](https://github.com/DecartAI/Lucy-Edit-ComfyUI) provides a
local Dev workflow, with downloadable
[Lucy Edit 1.1 Dev weights](https://huggingface.co/decart-ai/Lucy-Edit-1.1-Dev).
This is a 5B instruction-guided video editing model based on Wan2.2. It does
not establish that the website's Lucy 2.5 streaming model is available locally.
The repository distinguishes local Dev from Pro API, and states that the
weights permit non-commercial use; commercial use requires a separate arrangement.
The official [local cookbook](https://cookbook.decart.ai/lucy-edit-comfy)
lists CUDA hardware, 16 GB minimum GPU VRAM (24 GB recommended), and 32 GB
system RAM. This host reports Apple M1 Pro with 16 GB unified RAM, so the
published CUDA setup does not match it. We have not benchmarked that model on
Apple MPS, downloaded its multi-GB weights, or established realtime performance.

For the user's priority of a responsive local mirror, implemented a **separate
WebGL effects renderer**, selected by default. It uses compact edge-preserving
sampling, color quantization/edge lines for cartoon styling, neon grading,
watercolor styling, and animated holographic lines. These are deterministic
pixel effects, **not Lucy inference** or text-to-video generation. The prompt
box maps a small set of style keywords and rejects unsupported transformations.

The local renderer does not create a Decart client, request a token, open a
cloud session, or capture audio. It processes camera video locally at up to
720p and uses video-frame callbacks, avoiding an inference queue. Actual FPS
is displayed. A synthetic 640×360 video smoke test in the embedded WebEngine
reported about 30 FPS, zero token requests, and an ended camera track after
Stop. This does not measure camera latency or generative-model performance.
