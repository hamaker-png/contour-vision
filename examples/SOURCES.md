# Internet image fixtures

These files are actual downloaded images, not generated substitutes. Labels are manually
specified approximate boxes, independent of the tested detector outputs. Examples are
for functional testing, not a representative reliability benchmark.

- `smarties.png`: [OpenCV sample](https://github.com/opencv/opencv/blob/4.x/samples/data/smarties.png).
  Distributed in the OpenCV repository; see [OpenCV's license](https://github.com/opencv/opencv/blob/4.x/LICENSE).
  Four red candies are labeled, excluding orange and other colors and clipped objects.
- `green-shapes.png`: [Green shapes on Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Green_shapes.png).
  The file's licensing section identifies simple geometry as public domain; its structured
  metadata also lists Neha Chandrasekaran and CC BY-SA 4.0. Attribution retained here under
  [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) conservatively. Original PNG
  is unchanged. Transparency is composited onto white during processing. Both shapes touch
  the frame, so only visible extents can be measured.
- `coins.png`: [scikit-image coins](https://scikit-image.org/docs/stable/api/skimage.data.html#skimage.data.coins),
  originally from the Brooklyn Museum collection. No known copyright restrictions according
  to scikit-image. Downloaded from scikit-image v0.25.2. Twenty-four coins are manually labeled.
  This is an intentionally harder comparison with uneven lighting.

Additional independent critic-review fixtures (original files unchanged):

- `red-apple.jpg`: [Red Apple on Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Red_Apple.jpg),
  Abhijit Tembhekar, [CC BY 2.0](https://creativecommons.org/licenses/by/2.0/).
  Downloaded original 2418×2192 photograph. One manually boxed apple body, excluding its shadow.
- `tennis-ball.png`: [Tennisball2 on Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Tennisball2.png),
  KS, derived from Christian “VisualBeo” Horvat, [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/).
  The actual image has a background and a partial distant ball; the large foreground ball is the target.
  It nearly fills the frame, so successful box IoU alone is weak evidence about segmentation quality.
  Any redistributed image derivatives retain this attribution and share-alike license.
- `horse.png`: [scikit-image horse](https://scikit-image.org/docs/stable/api/skimage.data.html#skimage.data.horse),
  Andreas Preuss (“marauder”), CC0 per the dataset documentation. Downloaded from the official
  v0.25.2 repository. One manual box covers the irregular 2D silhouette; narrow legs and tail
  make shape loss visible even when box detection succeeds.

The critic benchmark preserves the originals on disk. Its optional derived stress cases
are labeled as derived, including an artificial same-color distractor and partial occlusion.
Very large in-memory variants use JPEG quality 95 to fit the app's upload limit; the report
records this encoding. They are not additional independent scenes.

Re-download with `python scripts/download_examples.py`. The script reports SHA-256 hashes.
Brightness/rotation/noise variants created by tests are perturbation checks of these same
sources, not independent validation photographs. These fixture scripts save no user
images or API keys.

The expansion examples in `vision-fixtures.json` reuse the original OpenCV `smarties.png`
photograph for branch confirmation. It is the same training image, not a new validation
scene. `qr-code.png` is a synthetic 2D test graphic generated with ZXing-C++ 2.3.0 and
contains the literal text `Contour sample 42`; it is not an internet photograph.
Reproduce both presets and that graphic with `python scripts/build_vision_examples.py`.


The bright/dark local-detail and circle-shape-confirmation examples are analytic 2D
teaching images created in `scripts/build_classical_examples.py`. They are constructed
development fixtures, not internet photographs or held-out accuracy evidence. The
first pair places three radius-6 spots on a known brightness gradient. The circle scene
contains two filled disks and two rectangular outlines; its confirmation design used
a previously observed rectangle false positive. No source photographs were altered.

The later independent apple and tennis photographs are retained as consumed validation
evidence under `artifacts/night-review/vision/`, rather than added to the fitted example
menu. Their source URLs, photographer attribution, licenses, original hashes and boxes
are in [the apple manifest](../artifacts/night-review/vision/heldout-apples.json) and
[the sealed tennis plan](../artifacts/night-review/vision/tennis-heldout/sealed-tennis-plan.json).
Derived previews and stress images retain the corresponding originals' attribution and
license. These four images were not used to tune their frozen presets.

## Offline object-tree pack

The 20 object tests add four photo trees using the already attributed red-candy, coin,
apple and tennis images above, plus 16 generated 2D object families. Each tree loads
three labeled training images. The photo sets use a size-limited copy, a derived
180-degree rotation and an explicitly artificial blank negative; these are not three
independent photographs. Derivatives retain the original source's credit and license.
The original files remain unchanged. `scripts/build_object_examples_photos.py` creates
these sets; source URLs and credits are also embedded in `object-tests-photos.json`.

`scripts/build_object_examples_a.py` and `scripts/build_object_examples_b.py` construct
the flat 2D objects, distractors, exact labels and branched pipelines without any model
or external image. They depict washers, nuts, bolts, keys, buttons, caps, pencils,
triangles, gaskets, packages, leaves, tablets, pins, solder pads, print marks and square
fiducials. Object names describe simplified teaching silhouettes, not camera photographs.
All test images are practice data; their success does not establish deployment accuracy.
