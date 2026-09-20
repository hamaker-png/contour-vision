# 20 offline object trees

Choose a tree under **Images → Example trees · no API key** in the app. Each has two positive practice images, one labeled negative, and editable alternatives. All three images run automatically.

These are known teaching examples. Photo variants reuse the same capture; generated 2D objects do not establish performance on real-world photographs. Alternative paths may intentionally detect extra objects or use different measurement definitions.

| Object | Starting pipeline | Measurements |
|---|---|---|
| Red candies · photo | Red hue + contours | length, width, area, color, center |
| Coins · photo | Local bright coins | length, width, area, color, center |
| Red apple · photo | Red apple hue | length, width, area, color, center |
| Tennis ball · photo | Yellow-green ball mask | length, width, area, color, center |
| Washers with through-holes · 2D | Objects with enclosed openings | length, width, area, center |
| Hex nuts with center openings · 2D | Objects with enclosed openings | length, width, area, color |
| Long bolts and short metal parts · 2D | Complete silhouette length | length, width, angle, area |
| Brass keys with ring holes · 2D | Objects with enclosed openings | length, width, angle, color |
| Red push-button faces · 2D | Color and round outline | length, width, color, center |
| Blue bottle-cap faces · 2D | Color and round outline | length, width, color, area |
| Yellow pencils: full and painted length · 2D | Complete silhouette length | length, width, angle, color |
| Red warning triangles with open centers · 2D | Objects with enclosed openings | length, width, area, center |
| Black gasket rings and open gaps · 2D | Objects with enclosed openings | length, width, area, center |
| Orange rectangular packages · 2D | Package outer rectangle | length, width, area, angle, color |
| Green leaves · 2D | Green hue + elongated shape | length, width, color, area |
| Elongated tablets · 2D | Bright elongated tablets | length, width, angle, color |
| Connector pin lengths · 2D | Dark elongated pins | length, width, angle, center |
| Bright solder pads · 2D | Top-hat solder-pad detail | length, width, area, center |
| Dark print marks · 2D | Black-hat dark print detail | length, width, angle, center |
| Square fiducial outlines · 2D | Dark square marker outlines | length, width, center, angle |

The companion ZIP contains 20 saved projects with embedded images. Extract it and use **Open project**. No API key is included or required. The intended starting pipeline is selected on import; use **Run all images**.

Sources and licenses: see [image sources](../SOURCES.md) and [third-party notices](../../THIRD_PARTY_NOTICES.md). Photo credits:
- [Red candies · photo](https://github.com/opencv/opencv/blob/4.x/samples/data/smarties.png): OpenCV sample image
- [Coins · photo](https://scikit-image.org/docs/stable/api/skimage.data.html#skimage.data.coins): Brooklyn Museum / scikit-image · no known copyright restrictions
- [Red apple · photo](https://commons.wikimedia.org/wiki/File:Red_Apple.jpg): Abhijit Tembhekar · CC BY 2.0
- [Tennis ball · photo](https://commons.wikimedia.org/wiki/File:Tennisball2.png): KS / Christian VisualBeo Horvat · CC BY-SA 3.0

Download [20 saved projects](20-object-trees.zip). Extract the ZIP and open an individual JSON project in Contour. The archive also includes image attribution and license information.
