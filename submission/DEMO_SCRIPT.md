# Contour — optional 2½-minute demo outline

This is a recording guide for the user, not a generated video. The core demonstration needs no API key. Rehearse with the real local application and keep the claims tied to what is visible.

## Before recording

1. Start the app using the repository's run instructions and open it in a browser.
2. Hide unrelated tabs, notifications, bookmarks, personal file paths, and credential settings. Leave API key fields empty.
3. Use **Washers with through-holes · 2D** from **Example trees · no API key**. It loads two positive images and one distractor-only negative. These are generated teaching illustrations.
4. Run all three images once and confirm the intended pipeline is **Objects with enclosed openings**. On the supplied practice set, the two positive images each contain two targets and the negative contains none.
5. Keep a backup recording of a successful run. If an action fails while recording, show or correct it honestly; do not replace it with fabricated output.

## Recording sequence

| Time | Show | Suggested narration |
|---|---|---|
| 0:00–0:15 | Project name, then the workspace | “Contour is a visual workbench for simple computer vision. The aim is to help a person choose a small CPU pipeline and understand what each step is doing.” |
| 0:15–0:35 | Load the washer example; show the image list | “There are twenty example trees to try without an API key. This one asks for washers with enclosed holes, with two positive images and a negative containing distractors.” |
| 0:35–1:00 | Select the input, material mask, and connected-region steps | “Each step shows a real intermediate image. This mask finds gray material, but color alone also admits the solid distractor. The measurements distinguish visible material area from a filled outer silhouette.” |
| 1:00–1:25 | Open the enclosed-opening branch, then the confirmed result | “A second branch checks for an enclosed opening. It rejects the outside background, and confirmation keeps the matching original objects. The branches share their preprocessing. This is a feature check, not a confidence probability.” |
| 1:25–1:45 | Inspect a step's parameters and move controls; show per-step timing | “The graph stays editable. I can adjust parameters or rearrange compatible operations, then rerun the same pipeline across the image family. The timings shown are local CPU measurements; estimates for another device are labeled separately.” |
| 1:45–2:05 | Switch to the moved/dimmed sample and distractor-only negative; open results | “The same parameters run on every image. Here the two practice objects are still found, while the negative has no final detections. These small teaching examples are useful for inspection, but do not establish real-world reliability.” |
| 2:05–2:25 | Export the selected C++ pipeline and show the downloaded source/configuration | “Once a pipeline is useful, Contour exports its selected operations and required branches as C++. The runtime needs a compiler and OpenCV libraries, but no Python interpreter, model, API key, or GPU.” |
| 2:25–2:40 | Return to the pipeline view | “AI is an optional assistant for asking about the task and suggesting editable approaches. The working offline path is already available. The next step is testing on more independent images and the actual target hardware.” |

## Optional short inserts

- **Measurement contrast:** load **Yellow pencils: full and painted length · 2D** and compare the full-silhouette path with the yellow painted-section branch. Explain that a measurement depends on which pixels represent the object.
- **Compiled execution:** include a terminal shot only if that exact downloaded export has actually been built and run. Show the real executable output; do not imply a source ZIP is already a platform-independent executable.
- **AI:** if a live key is available and the user chooses to demonstrate it, record an actual response and its resulting transforms. Otherwise explain the optional integration without staging a response or showing test doubles as live output.

## Closing and upload

Keep the final frame readable: project name, selected pipeline, and actual result. Add the verified GitHub link and the uploaded YouTube link to the submission. Check the video is accessible to judges without access to the recording machine or a private account.

No screen recording, voiceover, upload, or account action is performed by this document.
