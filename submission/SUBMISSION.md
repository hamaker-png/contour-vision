# Contour — submission draft

The sections below follow the submission form. The video link can be added after recording and uploading the demo.

## Project name

Contour

## Project description

A visual workbench for CPU-only computer vision: inspect transforms, compare branches, measure objects, and export C++.

## Inspiration

For a simple inspection task, a color mask and a few geometry checks can be enough. The hard part is often choosing the right steps and understanding where they fail. I wanted a visual way to explore those choices, with a lightweight result that can run without a GPU or a hosted model.

## What it does

Contour turns a set of images into an editable computer vision workspace. Each pipeline shows the actual image after every transform. Users can compare branches, change parameters, rearrange compatible operations, and inspect measurements such as length, area, orientation, and color.

Twenty ready-to-run object trees make it possible to start without an API key. Users can label targets and negatives, compare results across images, and export a selected pipeline as C++. Optional OpenAI integration asks for context and proposes editable approaches; the human chooses what to keep. The exported program runs locally without Python, a GPU, or a model.

## How we built it

The browser interface uses JavaScript and CSS, with a Python/FastAPI backend. OpenCV supplies the main image operations, CImg handles connected regions and distance maps, and ZXing-C++ reads barcodes. A typed graph describes each pipeline, its shared steps, and its supporting branches.

The same validated operation settings drive the preview and C++ export. AI suggestions are structured configuration, rather than arbitrary executable code. The project includes automated tests, generated teaching images, attributed photo examples, and comparisons between Python results and compiled exports. Development used substantial AI coding assistance.

## Individual contributions

I defined the product direction and the human-guided workflow, including the editable timelines, object measurements and lightweight C++ output. I used Codex extensively for implementation, debugging, testing and documentation.

## Challenges we ran into

Keeping the visual pipeline and exported program consistent was harder than simply adding filters. Shared branches need to run in the correct order, image types constrain which edits are valid, and a useful measurement must keep its meaning after a transform.

Testing also exposed subtle problems: a correct object count can hide a distorted shape, and image orientation or color decoding can change a detector's result. Those cases led to explicit measurement definitions, input checks, and comparisons with compiled C++ output.

## Accomplishments that we're proud of

The complete loop is working: load images, inspect transforms, compare approaches, measure objects, and export C++. Contour includes 30 CPU operations and 20 example trees that work without an API key. Shared branches make it easy to try an idea without rebuilding the whole pipeline, and paired Python/C++ checks help keep the exported result consistent with the workbench.

## What we learned

A correct count is only one part of a useful vision system. The shape, measured area, lighting conditions, negative examples, and input decoder all matter. Agreement between methods can be useful, but it is not a confidence score. I also learned how much clearer the workflow becomes when every transform is visible and every proposed change remains editable.

## What's next for our project

I want to test on more independent camera captures, benchmark exports on low-power devices, and improve physical calibration. I also want to evaluate how useful the AI suggestions are on new tasks. As public hosting grows, the next step is isolated user workspaces and stronger multi-user controls.

## Code link

https://github.com/hamaker-png/contour-vision

## Other links

Example projects: https://github.com/hamaker-png/contour-vision/tree/main/examples/packs

Deployment guide: https://github.com/hamaker-png/contour-vision/blob/main/DEPLOYMENT.md

A public app URL can be added after creating and checking the hosted service.

## Video demo

Add the YouTube URL after recording and uploading the demo. The form shown requires a YouTube link. Use [DEMO_SCRIPT.md](DEMO_SCRIPT.md) as an optional recording outline; no video has been generated or uploaded.

## Thumbnail

Upload [thumbnail.png](thumbnail.png), a 1440 × 1000 capture of the actual app. It shows the same image processed by a color-based pipeline and a grayscale alternative, including intermediate results and detected objects.

## Suggested tags, if requested

Computer vision, developer tools, image processing, C++, Python, OpenCV, education.

## Notes for the submitter — not form text

- Copy only the prose for each corresponding field; omit editorial notes.
- Paste full `https://` links. The form indicates that its Code Link must be a GitHub repository and its Video Demo must be YouTube.
- Live OpenAI proposal quality, cost, and latency have not been evaluated with a real key. Do not describe mocked-provider tests as live AI use.
- The 20 example sets are practice data. Generated scenes and rotations of a photograph are not independent camera captures or a deployment accuracy estimate.
- Timing estimates for another CPU are planning aids, not measured performance on that hardware. Physical units require calibration.
- Sponsor challenges, track selection, and power/outlet needs should reflect the actual submission and demonstration setup.
