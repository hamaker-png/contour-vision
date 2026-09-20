"""Generate and verify ten flat-object teaching families without an API key.

Run from the repository root: python scripts/build_object_examples_a.py
Writes only examples/object-tests/a-*.png and examples/object-tests-a.json.
These deterministic illustrations are development/teaching fixtures, not photos
or held-out reliability evidence. Boxes come from the exact rendered masks.
"""

import hashlib
import json
from pathlib import Path
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.engine import data_url, iou
from backend.models import Measurements, Sample
from backend.optimizer import score
from backend.search_execution import execute
from backend.timeline_exporter import TimelineExportRequest
from backend.timelines import Operation, Timeline, resolve_paths

WIDTH, HEIGHT = 480, 320
BACKGROUND = (246, 247, 245)
DEST = ROOT / 'examples/object-tests'


def op(kind, id=None, **params):
    return Operation(id=id or kind, kind=kind, params=params)


def polygon(n, radius, rotation=0):
    angle = np.arange(n) * 2 * np.pi / n + rotation
    return np.rint(np.column_stack([np.cos(angle), np.sin(angle)]) * radius + 100).astype(np.int32)


COLORS = {
    'washers': (140, 143, 147), 'hex-nuts': (147, 151, 155),
    'long-bolts': (90, 94, 100), 'keys': (30, 180, 225),
    'red-buttons': (40, 35, 230), 'blue-caps': (225, 105, 35),
    'yellow-pencils': (35, 210, 245), 'warning-triangles': (35, 30, 225),
    'gasket-rings': (24, 27, 26), 'orange-packages': (35, 130, 235),
}


def object_patch(family):
    image = np.zeros((201, 201, 3), np.uint8)
    mask = np.zeros((201, 201), np.uint8)
    color = COLORS[family]

    def disk(center, radius, value=color):
        cv2.circle(image, center, radius, value, -1)
        cv2.circle(mask, center, radius, 255, -1)

    def rectangle(a, b, value=color):
        cv2.rectangle(image, a, b, value, -1)
        cv2.rectangle(mask, a, b, 255, -1)

    def poly(points, value=color):
        points = np.array(points, np.int32)
        cv2.fillPoly(image, [points], value)
        cv2.fillPoly(mask, [points], 255)

    if family == 'washers':
        disk((100, 100), 33)
        cv2.circle(mask, (100, 100), 15, 0, -1)
        cv2.circle(image, (100, 100), 30, (123, 127, 133), 2)
    elif family == 'hex-nuts':
        poly(polygon(6, 39, np.pi / 6))
        cv2.polylines(image, [polygon(6, 34, np.pi / 6)], True, (112, 117, 122), 2)
        cv2.circle(mask, (100, 100), 14, 0, -1)
    elif family == 'long-bolts':
        rectangle((25, 79), (48, 121))
        rectangle((46, 92), (174, 108))
        for x in range(65, 168, 9):
            rectangle((x, 89), (x + 4, 111))
        cv2.line(image, (29, 92), (44, 92), (125, 127, 130), 2)
    elif family == 'keys':
        disk((58, 100), 26)
        rectangle((79, 93), (175, 107))
        rectangle((130, 104), (141, 120))
        rectangle((152, 104), (164, 119))
        cv2.circle(mask, (58, 100), 12, 0, -1)
    elif family == 'red-buttons':
        disk((100, 100), 29)
        cv2.circle(image, (100, 100), 26, (30, 28, 187), 2)
        cv2.circle(image, (91, 90), 5, (130, 130, 250), -1)
    elif family == 'blue-caps':
        disk((100, 100), 31)
        cv2.circle(image, (100, 100), 25, (239, 139, 68), 2)
        for angle in np.arange(12) * np.pi / 6:
            a = tuple(np.rint([100 + 27 * np.cos(angle), 100 + 27 * np.sin(angle)]).astype(int))
            b = tuple(np.rint([100 + 30 * np.cos(angle), 100 + 30 * np.sin(angle)]).astype(int))
            cv2.line(image, a, b, (153, 65, 27), 2)
    elif family == 'yellow-pencils':
        rectangle((27, 90), (157, 110))
        rectangle((15, 90), (28, 110), (141, 112, 206))
        rectangle((27, 90), (34, 110), (155, 158, 162))
        poly([[157, 90], [180, 100], [157, 110]], (126, 187, 223))
        poly([[172, 96], [180, 100], [172, 104]], (32, 33, 32))
        cv2.line(image, (37, 93), (154, 93), (55, 184, 215), 1)
    elif family == 'warning-triangles':
        poly([[100, 57], [144, 135], [56, 135]])
        # The label covers the sign's complete outer footprint, including white interior.
        cv2.fillPoly(image, [np.array([[100, 77], [128, 126], [72, 126]], np.int32)], BACKGROUND)
        cv2.line(image, (100, 95), (100, 110), (28, 29, 28), 5)
        cv2.circle(image, (100, 119), 3, (28, 29, 28), -1)
    elif family == 'gasket-rings':
        cv2.ellipse(image, (100, 100), (39, 29), 0, 0, 360, color, -1)
        cv2.ellipse(mask, (100, 100), (39, 29), 0, 0, 360, 255, -1)
        cv2.ellipse(mask, (100, 100), (25, 16), 0, 0, 360, 0, -1)
    elif family == 'orange-packages':
        rectangle((50, 68), (150, 132))
        cv2.line(image, (100, 69), (100, 131), (28, 92, 182), 3)
        cv2.rectangle(image, (71, 86), (125, 114), (243, 244, 242), -1)
        for y in [92, 99, 106]:
            cv2.line(image, (77, y), (116 - (y % 3) * 5, y), (50, 55, 58), 2)
    else:
        raise ValueError(family)
    return image, mask


def place(canvas, patch, mask, center, angle, scale, interpolation=cv2.INTER_NEAREST):
    matrix = cv2.getRotationMatrix2D((100, 100), angle, scale)
    matrix[:, 2] += np.array(center) - np.array([100, 100])
    rendered = cv2.warpAffine(patch, matrix, (WIDTH, HEIGHT), flags=interpolation)
    target = cv2.warpAffine(mask, matrix, (WIDTH, HEIGHT), flags=interpolation)
    target = np.where(target >= 127, 255, 0).astype(np.uint8)
    canvas[target > 0] = rendered[target > 0]
    return target


def distractors(image, family, negative):
    color = COLORS[family]
    if not negative:
        # A same-color solid disk challenges the hole/elongation examples.
        if family in ('red-buttons', 'blue-caps'):
            cv2.rectangle(image, (218, 144), (250, 176), color, -1)
        else:
            cv2.circle(image, (235, 160), 17, color, -1)
        return
    if family in ('washers', 'hex-nuts', 'gasket-rings', 'keys', 'warning-triangles'):
        cv2.circle(image, (85, 100), 28, color, -1)
        cv2.rectangle(image, (198, 76), (280, 121), color, -1)
        if family in ('washers', 'hex-nuts', 'gasket-rings'):
            cv2.ellipse(image, (385, 222), (35, 28), 0, 35, 325, color, 12)
        elif family == 'keys':
            cv2.circle(image, (350, 219), 24, color, -1)
            cv2.rectangle(image, (365, 212), (435, 226), color, -1)
        else:
            cv2.fillPoly(image, [np.array([[375, 177], [418, 251], [332, 251]], np.int32)], color)
    elif family in ('red-buttons', 'blue-caps'):
        cv2.rectangle(image, (58, 73), (112, 127), color, -1)
        cv2.ellipse(image, (244, 99), (43, 19), 18, 0, 360, color, -1)
        other = COLORS['blue-caps'] if family == 'red-buttons' else COLORS['red-buttons']
        cv2.circle(image, (387, 221), 29, other, -1)
    elif family == 'long-bolts':
        cv2.circle(image, (83, 97), 29, color, -1)
        cv2.rectangle(image, (210, 74), (266, 128), color, -1)
        cv2.rectangle(image, (340, 202), (417, 234), color, -1)
        cv2.rectangle(image, (335, 196), (354, 240), color, -1)
    elif family == 'yellow-pencils':
        cv2.circle(image, (83, 97), 30, color, -1)
        cv2.rectangle(image, (202, 82), (277, 112), color, -1)
        cv2.rectangle(image, (353, 193), (413, 251), COLORS['blue-caps'], -1)
    elif family == 'orange-packages':
        cv2.circle(image, (83, 97), 31, color, -1)
        cv2.rectangle(image, (181, 91), (300, 109), color, -1)
        cv2.rectangle(image, (340, 190), (433, 253), COLORS['blue-caps'], -1)


def make_scene(family, variant):
    image = np.full((HEIGHT, WIDTH, 3), BACKGROUND, np.uint8)
    masks = []
    if variant != 'negative':
        patch, mask = object_patch(family)
        poses = [((122, 98), 0, 1), ((350, 226), -7, .88)] if variant == 'base' else [
            ((124, 226), 21, .94), ((341, 94), -23, 1.04)]
        for center, angle, scale in poses:
            interpolation = cv2.INTER_LINEAR if family in ('red-buttons', 'blue-caps') else cv2.INTER_NEAREST
            masks.append(place(image, patch, mask, center, angle, scale, interpolation))
    distractors(image, family, variant == 'negative')
    if variant == 'variation':
        image = np.rint(image.astype(np.float64) * .85).astype(np.uint8)
    labels = []
    for mask in masks:
        x, y, w, h = cv2.boundingRect(cv2.findNonZero(mask))
        labels.append(dict(x=x / WIDTH, y=y / HEIGHT, width=w / WIDTH, height=h / HEIGHT))
    return image, labels, masks


def hsv(id, low, high, saturation=100, value=60):
    return op('hsv_mask', id, hue_low=low, hue_high=high, saturation_low=saturation, value_low=value)


def hole_graphs(family):
    prefix = [op('resize', 'input_resize', max_side=480)]
    material = family in ('washers', 'hex-nuts', 'gasket-rings')
    if family in ('washers', 'hex-nuts'):
        prefix += [op('grayscale', 'gray'), op('range_mask', 'object_mask', low=80, high=190)]
    elif family == 'gasket-rings':
        prefix += [op('grayscale', 'gray'), op('range_mask', 'object_mask', low=0, high=70)]
    elif family == 'keys':
        prefix += [hsv('object_mask', 16, 35)]
    else:
        prefix += [hsv('object_mask', 170, 12)]
    detector = op('cimg_components', 'primary', min_pixels=300, max_pixels=15000) if material else op(
        'contours', 'primary', min_area=.003, max_area=.1,
        min_aspect=1.8 if family == 'keys' else 1, max_aspect=5,
        min_solidity=.45 if family == 'keys' else .85)
    main = Timeline(id='main', name='Material pixels' if material else 'Outer object dimensions', operations=prefix + [detector],
                    rationale='Select the visible material and measure it. Solid same-color distractors can also survive this first detector.')
    holes = Timeline(id='holes', name='Enclosed openings', parent_id='main', fork_after='object_mask',
                     rationale='Invert the mask, then reject the border-connected outside background. Only enclosed openings remain; an open ring has no enclosed opening.',
                     operations=[op('invert', 'inside_background'), op('cimg_components', 'hole_regions', min_pixels=100, max_pixels=10000)])
    confirmed = Timeline(id='confirmed', name='Objects with enclosed openings', parent_id='main', fork_after='primary',
                         rationale='Require a matching interior opening. Keep the original object bounds and material measurements. This tests the illustrated feature, not a learned object category.',
                         operations=[op('confirm', 'agreement', pipeline_ids='holes', iou=.02 if family == 'keys' else .08)])
    return [main, holes, confirmed], 'confirmed'


def graphs_for(family):
    if family in ('washers', 'hex-nuts', 'keys', 'warning-triangles', 'gasket-rings'):
        return hole_graphs(family)
    start = op('resize', 'input_resize', max_side=480)
    if family in ('red-buttons', 'blue-caps'):
        low, high = (170, 12) if family == 'red-buttons' else (98, 124)
        geometry = dict(min_area=.004, max_area=.04, min_circularity=.84, min_solidity=.93, max_aspect=1.2)
        main = Timeline(id='main', name='Color and round outline', operations=[start, hsv('color_mask', low, high), op('median_blur', 'smooth_color_mask', kernel=3), op('contours', 'round_faces', **geometry)],
                        rationale='Select the object color, smooth single-pixel raster irregularities, then reject same-color squares and elongated pieces. Diameter is the outer face outline, not a fitted Hough circle.')
        alternative = Timeline(id='brightness', name='Brightness-only comparison', parent_id='main', fork_after='input_resize',
                               rationale='A dark-object threshold discards the hue information. Inspect the other-colored circle in the negative image to see why color matters.',
                               operations=[op('grayscale', 'gray'), op('range_mask', 'dark_mask', low=0, high=160), op('median_blur', 'smooth_dark_mask', kernel=3), op('contours', 'dark_round_faces', **geometry)])
        return [main, alternative], 'main'
    if family in ('long-bolts', 'yellow-pencils'):
        aspect = 3 if family == 'long-bolts' else 5
        geometry = dict(min_area=.003, max_area=.08, min_aspect=aspect, max_aspect=15, min_solidity=.5 if family == 'long-bolts' else .88)
        main = Timeline(id='main', name='Complete silhouette length', operations=[start, op('grayscale', 'gray'), op('otsu', 'light_mask'), op('invert', 'body_mask'), op('contours', 'long_objects', **geometry)],
                        rationale='Separate the silhouette from the plain background with Otsu, then require an elongated shape. Rotated rectangle measurements include the full tip or bolt head.')
        if family == 'yellow-pencils':
            alternative = Timeline(id='paint', name='Yellow painted section', parent_id='main', fork_after='input_resize',
                                   rationale='Compare the painted-body length with the complete pencil silhouette. The wood point and eraser are deliberately excluded here.',
                                   operations=[hsv('yellow_mask', 18, 38), op('contours', 'painted_bodies', **geometry)])
        else:
            alternative = Timeline(id='edges', name='Edge outline comparison', parent_id='main', fork_after='gray',
                                   rationale='Compare thin edges with the filled silhouette. Small teeth make the edge path more fragmented; inspect its intermediate mask.',
                                   operations=[op('canny', 'outline_edges', low=40, high=110), op('morph_close', 'closed_edges', kernel=3), op('contours', 'edge_objects', **geometry)])
        return [main, alternative], 'main'
    main = Timeline(id='main', name='Package outer rectangle', operations=[start, hsv('orange_mask', 6, 25, saturation=110),
                    op('contours', 'outer_boxes', min_area=.015, max_area=.1, min_solidity=.96, min_aspect=1.3, max_aspect=2.5)],
                    rationale='Measure the complete outer package footprint, including the printed label. Aspect filtering rejects disks and long orange strips.')
    alternative = Timeline(id='material', name='Visible orange material', parent_id='main', fork_after='orange_mask',
                           rationale='Connected pixels exclude the pale label from area. Compare this painted-material area with the outer rectangular area.',
                           operations=[op('cimg_components', 'painted_regions', min_pixels=400, max_pixels=15000)])
    return [main, alternative], 'main'


SPECS = [
    ('washers', 'Washers with through-holes', ['length', 'width', 'area', 'center'],
     'Find the two gray washers with enclosed holes; reject the solid disk and open-ring distractors.',
     'Material area excludes each hole. The opening branch distinguishes enclosed holes from a C-shaped gap; connected-region width and length are axis-aligned extents.'),
    ('hex-nuts', 'Hex nuts with center openings', ['length', 'width', 'area', 'color'],
     'Find the two illustrated metal hex nuts with central openings; reject solid metal pieces.',
     'Compare the cornered silhouettes and the enclosed-opening evidence. This fixture tests gray material plus an opening; it does not claim to count polygon vertices or distinguish every washer from a nut.'),
    ('long-bolts', 'Long bolts and short metal parts', ['length', 'width', 'angle', 'area'],
     'Find the two long bolts; ignore compact metal pieces. Measure full head-to-tip extent and orientation.',
     'The elongated silhouette includes the bolt head and coarse illustrated thread teeth. Otsu follows the uniform brightness change; the edge alternative reveals tooth fragmentation.'),
    ('keys', 'Brass keys with ring holes', ['length', 'width', 'angle', 'color'],
     'Find the two brass keys with enclosed head holes; ignore solid brass shapes.',
     'Color proposes brass silhouettes, aspect keeps long candidates, and an enclosed head opening supplies confirmation. Length is the rotated outer extent, not a key-cut specification.'),
    ('red-buttons', 'Red push-button faces', ['length', 'width', 'color', 'center'],
     'Find the two red circular button faces; reject red squares, stretched pieces and a blue circle.',
     'The object is the illustrated red face. Compare hue plus circularity with a brightness-only branch; these measurements describe the face outline, not a mechanical housing.'),
    ('blue-caps', 'Blue bottle-cap faces', ['length', 'width', 'color', 'area'],
     'Find the two blue round caps; ignore blue squares, elongated blue pieces and a red circle.',
     'Cap highlights and radial grooves remain inside the blue hue range. The contour reports an outer face footprint; color plus roundness is not a general cap classifier.'),
    ('yellow-pencils', 'Yellow pencils: full and painted length', ['length', 'width', 'angle', 'color'],
     'Find the two complete pencils, including their erasers and points; ignore short yellow objects.',
     'Compare whole-silhouette length against the shorter yellow painted-body branch. The plain-background Otsu path includes eraser, ferrule, wood and graphite.'),
    ('warning-triangles', 'Red warning triangles with open centers', ['length', 'width', 'area', 'center'],
     'Find the two outlined warning signs; reject filled red triangles, disks and blocks.',
     'The red border encloses a white sign interior with an exclamation mark. Hole confirmation rejects filled shapes here; it does not prove that every accepted outline has exactly three corners. Outer area includes the interior.'),
    ('gasket-rings', 'Black gasket rings and open gaps', ['length', 'width', 'area', 'center'],
     'Find the two closed black gasket rings; ignore solid pieces and the open C-shaped gasket.',
     'The selected path preserves material pixels and excludes openings from area. Inverting the mask demonstrates why an open gap connects the interior to the outside background.'),
    ('orange-packages', 'Orange rectangular packages', ['length', 'width', 'area', 'angle', 'color'],
     'Find the two orange packages with pale shipping labels; reject circles, long strips and blue boxes.',
     'Outer contours include the shipping-label hole when measuring package footprint. Compare the connected-region alternative to see how visible orange material area differs.'),
]


def build():
    DEST.mkdir(parents=True, exist_ok=True)
    entries = []
    total_targets = 0
    for family, title, fields, description, context in SPECS:
        graphs, selected = graphs_for(family)
        measures = Measurements(fields=fields)
        TimelineExportRequest(timelines=graphs, selected_timeline_id=selected, measurements=measures)
        assert max(map(len, resolve_paths(graphs).values())) <= 12
        samples = []
        for variant in ['base', 'variation', 'negative']:
            image, boxes, masks = make_scene(family, variant)
            id = f'a-{family}-{variant}'
            sample = Sample(id=id, name=id, data=data_url(image), boxes=boxes, labeled=True, split='train')
            final, _ = execute(image, graphs, selected, measures)
            result = score(final, sample)
            if result['tp'] != len(boxes) or result['fp'] or result['fn']:
                raise AssertionError(json.dumps(dict(family=family, variant=variant, result=result, detections=final.details['detections']), indent=2))
            material_area_exact = None
            if family in ('washers', 'hex-nuts', 'gasket-rings'):
                for box, target_mask in zip(boxes, masks):
                    normalized = [box[key] for key in ('x', 'y', 'width', 'height')]
                    detection = max(final.details['detections'], key=lambda d: iou(d['normalized_box'], normalized))
                    assert detection['measurements']['area'] == int(np.count_nonzero(target_mask)), (family, variant, 'material area')
                material_area_exact = True
            # All branches are runnable, including alternatives intended to expose failures.
            alternative_counts = {}
            for graph in graphs:
                other, _ = execute(image, graphs, graph.id, measures)
                alternative_counts[graph.id] = other.details.get('count', 0)
            filename = f'object-tests/{id}.png'
            path = ROOT / 'examples' / filename
            assert cv2.imwrite(str(path), image)
            expected = dict(count=len(boxes), min_iou=.5, max_false_positives=0)
            samples.append(dict(id=id, name={'base': 'Two objects with a distractor', 'variation': 'Moved, rotated and dimmed', 'negative': 'Distractors only'}[variant],
                                filename=filename, path='/examples/' + filename, boxes=boxes, labeled=True, split='train',
                                expected_count=len(boxes), expected=expected, source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                target_pixel_areas=[int(np.count_nonzero(mask)) for mask in masks],
                                teaching_check=dict(tp=result['tp'], fp=result['fp'], fn=result['fn'], mean_matched_iou=result.get('mean_iou'),
                                                    min_matched_iou=min(result['matched_overlaps'].values(), default=None),
                                                    material_area_exact=material_area_exact, branch_counts=alternative_counts)))
            total_targets += len(boxes)
        first = samples[0]
        entries.append(dict(id='a-' + family, title=title + ' · 2D', category='Object tests · 2D', collection='object-tests',
                            description=description, context='Generated flat 2D teaching images with exact rendered-mask boxes; not natural-image reliability evidence. ' + context,
                            source='', credit='Generated deterministic 2D teaching illustration · exact analytic-mask labels', workbench_only=True,
                            filename=first['filename'], path=first['path'], boxes=first['boxes'], labeled=True,
                            samples=samples, pipelines=[t.model_dump() for t in graphs], recommended_timeline_id=selected,
                            suggested_measurements=fields, expected=dict(recommended_timeline_id=selected, counts=[2, 2, 0], min_iou=.5, max_false_positives=0),
                            generation=dict(script='scripts/build_object_examples_a.py', deterministic=True, image_size=[WIDTH, HEIGHT], labels='Exact bounding boxes of rendered object masks', evidence='Teaching/development fixtures; no held-out accuracy claim')))
        print(f'{family}: 3/3 recommended-path checks passed; {len(graphs)} runnable branches', flush=True)
    (ROOT / 'examples/object-tests-a.json').write_text(json.dumps(entries, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Wrote {len(entries)} object families, {len(entries) * 3} images; {total_targets} targets and 10 distractor-only negatives passed.')


if __name__ == '__main__':
    build()
