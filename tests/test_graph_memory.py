"""Image-buffer liveness and complete results across shared/erroring DAGs."""
import weakref
from unittest.mock import patch

import numpy as np

from backend import graph_execution, search_execution
from backend.engine import data_url, decode_image
from backend.models import Measurements, Sample
from backend.timelines import Operation, Timeline, TimelineRunRequest


def op(id, kind, params=None):
    return Operation(id=id, kind=kind, params=params or {})


def timeline(id, operations, parent=None, fork=None):
    return Timeline(id=id, name=id, operations=operations, parent_id=parent, fork_after=fork)


def request(graphs):
    source = np.zeros((64, 64, 3), np.uint8)
    source[16:40, 16:40] = (20, 140, 240)
    sample = Sample(id="object", name="object.png", data=data_url(source), labeled=True,
                    boxes=[{"x": .25, "y": .25, "width": .375, "height": .375}])
    return source, TimelineRunRequest(samples=[sample], timelines=graphs,
                                      measurements=Measurements(fields=["color", "area"]))


def track_arrays(module):
    actual = module.apply_operation
    references = []; peak = [0]
    def tracked(*args):
        result = actual(*args)
        references.append(weakref.ref(result.image))
        peak[0] = max(peak[0], sum(reference() is not None for reference in references))
        return result
    return tracked, references, peak


def test_full_workspace_releases_completed_paths_but_keeps_every_preview_and_summary():
    graphs = [timeline(f"p{i}", [op(f"n{i}_{j}", "invert") for j in range(8)]) for i in range(8)]
    source, body = request(graphs)
    tracked, references, peak = track_arrays(graph_execution)
    with patch.object(graph_execution, "apply_operation", tracked):
        result = graph_execution.run_graph(body)["images"][0]
    # At most current input + previous timing repeat + newly produced repeat.
    assert peak[0] <= 3
    assert all(reference() is None for reference in references)
    assert result["executed_nodes"] == 64 and len(result["stages"]) == 65
    assert all(stage["status"] == "ok" and stage["image"].startswith("data:image/")
               for stage in result["stages"].values())
    for i in range(8):
        for j in range(8):
            expected = 255 - source if j % 2 == 0 else source
            assert np.array_equal(decode_image(result["stages"][f"n{i}_{j}"]["image"]), expected)
    assert all(path["errors"] == 0 and path["local_ms"] is not None for path in result["timelines"])


def test_shared_detector_stays_alive_through_confirmation_and_later_fanout():
    graphs = [timeline("primary", [op("gray", "grayscale"), op("mask", "threshold", {"value": 60}),
                                    op("detector", "contours")]),
              timeline("support", [op("other-mask", "otsu"), op("other-detector", "contours")], "primary", "gray"),
              timeline("confirmed", [op("agreement", "confirm", {"pipeline_ids": "support"})], "primary", "detector"),
              timeline("later", [op("final-invert", "invert")], "primary", "detector")]
    _, body = request(graphs)
    tracked, references, _ = track_arrays(graph_execution)
    with patch.object(graph_execution, "apply_operation", tracked):
        result = graph_execution.run_graph(body)["images"][0]
    stages = result["stages"]
    assert result["executed_nodes"] == 7
    assert all(stage["status"] == "ok" for stage in stages.values())
    primary = stages["detector"]["details"]["detections"][0]
    confirmed = stages["agreement"]["details"]["detections"][0]
    assert confirmed["box"] == primary["box"]
    assert confirmed["measurements"] == {**primary["measurements"], "supporting_branches": 1}
    assert confirmed["measurements"]["mean_rgb"] == [240, 140, 20]
    assert all(reference() is None for reference in references)


def test_error_and_blocked_paths_release_their_dependency_turn_without_harming_sibling():
    graphs = [timeline("primary", [op("gray", "grayscale"), op("mask", "threshold", {"value": 60}),
                                    op("detector", "contours")]),
              timeline("bad", [op("invalid-color-step", "hsv_mask"), op("blocked-detector", "contours")], "primary", "gray"),
              timeline("blocked", [op("blocked-agreement", "confirm", {"pipeline_ids": "bad"})], "primary", "detector"),
              timeline("sibling", [op("last", "invert")], "primary", "detector"),
              timeline("independent", [op("probe", "invert")])]
    _, body = request(graphs)
    tracked, references, _ = track_arrays(graph_execution)
    last_outputs = {}
    def observe_release(*args):
        if args[1].id == "last":
            assert last_outputs["gray"]() is None  # failed child consumed the remaining reader
            assert last_outputs["detector"]() is not None  # healthy sibling still needs this input
        if args[1].id == "probe":
            assert last_outputs["detector"]() is None
            assert last_outputs["last"]() is None
        result = tracked(*args)
        last_outputs[args[1].id] = weakref.ref(result.image)
        return result
    with patch.object(graph_execution, "apply_operation", observe_release):
        result = graph_execution.run_graph(body)["images"][0]
    assert result["stages"]["invalid-color-step"]["status"] == "error"
    assert result["stages"]["blocked-detector"]["status"] == "blocked"
    assert result["stages"]["blocked-agreement"]["status"] == "blocked"
    assert result["stages"]["last"]["status"] == "ok"
    assert result["executed_nodes"] == 5
    assert all(reference() is None for reference in references)


def test_selected_search_releases_inputs_despite_consumers_in_unselected_branches():
    main = timeline("main", [op(f"step{i}", "invert") for i in range(8)])
    # Seven dormant branches would otherwise pin seven intermediate images.
    graphs = [main] + [timeline(f"unused{i}", [op(f"unused-step{i}", "invert")], "main", f"step{i}")
                       for i in range(7)]
    source, body = request(graphs)
    tracked, references, peak = track_arrays(search_execution)
    with patch.object(search_execution, "apply_operation", tracked):
        result, elapsed = search_execution.execute(source, graphs, "main", body.measurements)
    assert peak[0] <= 2
    assert np.array_equal(result.image, source) and elapsed >= 0
    assert sum(reference() is not None for reference in references) == 1
