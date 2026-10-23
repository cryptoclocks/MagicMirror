# Photorealistic AR hat assets

Five transparent PNG images generated with the built-in `image_gen` tool:
`cap.png`, `top-hat.png`, `sun-hat.png`, `graduation.png`, `crown.png`.

These replace the previous cartoon SVG assets. Full prompts, generation mode
and final output paths are recorded in `GENERATION.json`.

Original generated PNGs are preserved. The runtime uses their alpha channel,
ignores unused transparent padding for fitting, preserves aspect ratio, and
attaches a calibrated point on the forehead using OpenCV eye/chin/jaw landmarks.
