# Images and API keys

Contour works without an API key. The supplied examples, image transforms,
measurements and C++ exports do not use a hosted AI model.

## Local and hosted processing

When you run Contour on your own computer, the Python server processes images there.
On a hosted deployment, images and pipeline settings are sent to that deployment's
server for processing. Timings refer to that server's CPU, not the visitor's device.

The application does not save uploaded images or projects to a server database or
image directory. Images are held in memory during processing, and the browser holds
the current project. **Save project** downloads images, labels, operations and
measurements to your computer. Project files do not contain API keys. Closing the
page without saving loses the project.

The hosting provider may retain normal request metadata under its own policies.
Self-hosting puts that infrastructure under your control. This prototype has no
user accounts or private cloud project storage.

## Optional AI

Connecting an OpenAI key enables image analysis and suggested pipelines. These
requests send the key, task description, training images and relevant intermediate
previews through the Contour server to OpenAI. Held-out validation images are excluded
from AI suggestions. The automatic inspection preference is visible in AI settings.
OpenAI API charges and data policies apply to the account providing the key.

In public mode (`CONTOUR_PUBLIC=1`), keys stay in page memory and are supplied with
individual AI requests. Contour does not persist them, and environment or locally
saved server keys are disabled. Reloading or closing the page clears the entered key.

When running locally, remembering a key is optional and stores it in `.local/`,
excluded from Git and deployment packages. Turn off **Remember on this computer**
and apply settings to remove a remembered local key.

## Exported programs

The generated C++ program contains the selected operations, parameters and build
files. It runs on local input images and needs no API key, Python interpreter,
hosted model or network connection for detection. Building it may download required
dependencies as described in its included instructions.
