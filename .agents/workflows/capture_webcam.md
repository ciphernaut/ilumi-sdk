---
description: Capturing images from the webcam
---

When accessing the webcam via `fswebcam`, you must execute the process within the `video` group in order to bypass docker permissions restrictions.
Use the following command pattern to wrap the execution:
`sg video -c "fswebcam --no-banner /projects/antigravity/ilumi/tests/webcam_snapshot.jpg"`