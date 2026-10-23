# Health demo consistency audit

All displayed values are scripted data. Camera processing locates a face and
landmarks; it does not measure vital signs, sleep, hydration or fatigue.
These values cannot establish whether the person in the camera is healthy.

| Demo field | Value | Context |
|---|---:|---|
| Pulse | 72 BPM | Inside a typical resting adult reference interval of 60–100 BPM |
| Respiratory rate | 16/min | Inside a typical resting adult reference interval of 12–18/min |
| Oxygen saturation | 98% | Inside the typical reference interval of 95–100% |
| Temperature | 36.6 °C | Inside the cited typical resting adult interval of 36.5–37.3 °C |
| Sleep | 5.5 hours | Intentionally short of the 7-hour goal; matches the short-sleep demo narration |
| Energy | 86/100 | Fictional visual score, not a clinical measurement or validated medical scale |

Do not describe the entire profile as a fully rested person: the sleep scenario
is intentionally below goal. Adult reference ranges vary with context and do
not diagnose the health of an individual.

`health_profile.py` is the shared source for numeric readouts and animation
rates. Heart animation and the ECG sweep both use 72 BPM; lung animation and
its trace both use 16/min. Bars and arcs use the displayed oxygen/energy
percentages. The ECG is stylized artwork, not a recorded or validated tracing.

Reference pages checked 22 October 2026:

- MedlinePlus, Vital signs: https://medlineplus.gov/ency/article/002341.htm
- MedlinePlus, Pulse oximetry: https://medlineplus.gov/lab-tests/pulse-oximetry/
- American Heart Association, All about heart rate: https://www.heart.org/en/health-topics/high-blood-pressure/the-facts-about-high-blood-pressure/all-about-heart-rate-pulse
- CDC, About sleep (adults 18–60: 7 or more hours): https://www.cdc.gov/sleep/about/index.html
