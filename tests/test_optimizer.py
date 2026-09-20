"""Behavioral contracts for training-only search, cache reuse, and AI evidence.

Fixtures are tiny synthetic objects. No provider requests or optional native
libraries are needed, and controlled clocks make budget checks deterministic.
"""
import asyncio
import copy
import json
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from backend import optimizer, search_execution, timeline_ai
from backend.ai_evidence import prepare_evidence
from backend.cpu_work import WorkCancelled
from backend.engine import data_url
from backend.graph_exporter import validate_export_graph
from backend.models import Measurements, Sample
from backend.search_execution import FrameCache, SearchDeadline, execute
from backend.timelines import Frame, Timeline, TimelineSuggestRequest, execution_plan


def operation(id, kind, params=None):
    return {"id": id, "kind": kind, "params": params or {}}


def pipeline(id="main", operations=None, parent=None, fork=None):
    if operations is None:
        operations = [operation(id + "-g", "grayscale"), operation(id + "-t", "threshold"),
                      operation(id + "-d", "contours")]
    return Timeline.model_validate({"id": id, "name": id, "parent_id": parent,
                                    "fork_after": fork, "operations": operations})


def image(positive=True):
    source = np.zeros((64, 64, 3), np.uint8)
    if positive:
        source[16:40, 16:40] = (255, 255, 255)
    return source


def sample(id="positive", positive=True):
    return Sample(id=id, name=id + ".png", data=data_url(image(positive)), labeled=True,
                  boxes=[{"x": .25, "y": .25, "width": .375, "height": .375}] if positive else [])


def request(**changes):
    body = {"samples": [sample()], "timelines": [pipeline()], "selected_timeline_id": "main",
            "max_trials": 4, "budget_seconds": 2, "measurements": Measurements(fields=[])}
    body.update(changes)
    return optimizer.OptimizeRequest.model_validate(body)


def test_invalid_selected_and_seed_ids_have_readable_validation_errors():
    with pytest.raises(ValueError, match="existing pipeline"):
        request(selected_timeline_id="missing")
    with pytest.raises(ValueError, match="existing pipeline"):
        request(seeds=[{"timelines": [pipeline()], "selected_timeline_id": "missing"}])


@pytest.mark.parametrize("samples", [[sample().model_copy(update={"labeled": False})],
                                    [sample("negative", False)]])
def test_search_requires_complete_labels_and_a_positive_target(samples):
    with pytest.raises(ValueError):
        request(samples=samples)


def test_validation_poison_is_never_decoded_or_scored_and_baseline_stays_unchanged():
    poison = Sample(id="held", name="SECRET-VALIDATION", data="must never decode this",
                    split="validation", labeled=False)
    body = request(samples=[sample(), sample("negative", False), poison])
    original = body.model_dump()
    result = optimizer.optimize(body)
    assert body.model_dump() == original
    assert result["candidates"][0]["baseline"]
    assert not result["candidates"][0]["recommended"]
    assert result["candidates"][0]["metrics"] == {"tp": 1, "fp": 0, "fn": 0,
                                                "f1": 1.0, "localization_iou": 1.0}
    for candidate in result["candidates"]:
        assert [row["sample_id"] for row in candidate["per_image"]] == ["positive", "negative"]
        assert candidate["no_training_regression"]


def test_compaction_keeps_empty_alias_used_as_confirmation_support():
    support = pipeline("support")
    alias = pipeline("alias", [], "support", "support-d")
    main = pipeline(operations=[operation("g", "grayscale"), operation("t", "threshold"),
                               operation("d", "contours"),
                               operation("confirm", "confirm", {"pipeline_ids": "alias"})])
    compact = optimizer.compact_graph([support, alias, main], "main")
    assert {graph.id for graph in compact} == {"support", "alias", "main"}
    validate_export_graph(SimpleNamespace(timelines=compact, selected_timeline_id="main"))
    final, _ = execute(image(), compact, "main", Measurements(fields=[]))
    assert final.details["count"] == 1


def test_signature_distinguishes_shared_and_duplicated_computation():
    main = pipeline(operations=[operation("g", "grayscale"), operation("t", "threshold"),
                               operation("d", "contours"),
                               operation("confirm", "confirm", {"pipeline_ids": "support"})])
    duplicated = [main, pipeline("support", [operation("sg", "grayscale"),
                                             operation("st", "otsu"), operation("sd", "contours")])]
    shared = [main, pipeline("support", [operation("st", "otsu"), operation("sd", "contours")], "main", "g")]
    assert len(execution_plan(duplicated, "main")[0]) == 7
    assert len(execution_plan(shared, "main")[0]) == 6
    assert optimizer.signature(duplicated, "main") != optimizer.signature(shared, "main")


def test_no_regression_is_per_image_per_target_and_limits_overlap_loss():
    row = {"matched_targets": [0], "matched_overlaps": {"0": .9}, "fp": 0}
    assert optimizer.no_regression([copy.deepcopy(row)], [row])
    small_loss = {**row, "matched_overlaps": {"0": .881}}
    assert optimizer.no_regression([small_loss], [row])
    for changed in ({**row, "matched_targets": [1], "matched_overlaps": {"1": .99}},
                    {**row, "fp": 1}, {**row, "matched_overlaps": {"0": .879}}):
        assert not optimizer.no_regression([changed], [row])
    negative = {"matched_targets": [], "matched_overlaps": {}, "fp": 0}
    # Equal family totals cannot exchange a miss/false positive between images.
    assert not optimizer.no_regression([negative, row], [row, negative])
    assert not optimizer.no_regression([row], [row, negative])


def test_localization_score_counts_missed_targets_as_zero_overlap():
    positive = sample()
    positive.boxes.append(type(positive.boxes[0])(x=.7, y=.7, width=.1, height=.1))
    frame = Frame(np.zeros((64, 64), np.uint8), "mask",
                  details={"detections": [{"normalized_box": [.25, .25, .375, .375]}]})
    row = optimizer.score(frame, positive)
    metrics = optimizer.aggregate([row])
    assert row["mean_iou"] == 1.0
    assert metrics["localization_iou"] == .5 and metrics["fn"] == 1


def test_equal_f1_candidates_rank_and_recommend_real_box_localization_gains():
    seeds = [{"name": name, "timelines": [pipeline(name)], "selected_timeline_id": name}
             for name in ("minor", "better", "fast")]
    for value, seed in enumerate(seeds, 130):
        seed["timelines"][0].operations[1].params["value"] = value
    overlap = {"main": .8, "minor": .82, "better": .95, "fast": .8}
    elapsed = {"main": 10, "minor": 10, "better": 20, "fast": 1}
    def controlled_execute(source, graphs, selected, measurements, *args, **kwargs):
        box = [.25, .25, .375 * overlap[selected], .375]
        return Frame(np.zeros(source.shape[:2], np.uint8), "mask",
                     details={"detections": [{"normalized_box": box}],
                              "measurement_basis": "same"}), elapsed[selected]
    with patch("backend.optimizer.execute", controlled_execute):
        result = optimizer.optimize(request(seeds=seeds))
    assert result["candidates"][1]["selected_timeline_id"] == "better"
    selected = {candidate["selected_timeline_id"]: candidate for candidate in result["candidates"]}
    assert {candidate["metrics"]["f1"] for candidate in selected.values()} == {1.0}
    assert selected["better"]["localization_improved"] and selected["better"]["recommended"]
    assert not selected["minor"]["localization_improved"] and not selected["minor"]["recommended"]
    assert selected["fast"]["recommended"] and not selected["fast"]["localization_improved"]


def test_cache_invalidates_same_ids_for_parameters_measurements_and_new_source():
    source = image(); graphs = [pipeline()]; cache = FrameCache()
    empty = Measurements(fields=[])
    first, _ = execute(source, graphs, "main", empty, cache)
    assert first.details["count"] == 1
    before = cache.executed
    repeated, _ = execute(source, graphs, "main", empty, cache)
    assert repeated.details == first.details and cache.executed == before and cache.hits >= 3
    altered = copy.deepcopy(graphs)
    altered[0].operations[1].params["value"] = 255
    result, _ = execute(source, altered, "main", empty, cache)
    assert result.details["count"] == 0
    colored, _ = execute(source, graphs, "main", Measurements(fields=["color"]), cache)
    assert colored.details["detections"][0]["measurements"]["mean_rgb"] == [255, 255, 255]
    new_source = image(False)
    blank, _ = execute(new_source, graphs, "main", empty, cache)
    assert blank.details["count"] == 0 and cache.source is new_source


def test_lru_cache_byte_limit_does_not_change_detection_results():
    cache = FrameCache(max_bytes=20_000); source = image(); graphs = [pipeline()]
    expected, _ = execute(source, graphs, "main", Measurements(fields=[]))
    actual, _ = execute(source, graphs, "main", Measurements(fields=[]), cache)
    assert actual.details == expected.details
    assert 0 < cache.peak <= cache.limit and cache.bytes <= cache.limit
    assert sum(entry[2] for entry in cache.entries.values()) == cache.bytes


def test_cancel_before_search_and_evidence_skips_image_decoding():
    stop = threading.Event(); stop.set()
    with patch("backend.optimizer.decode_image") as decode, pytest.raises(WorkCancelled):
        optimizer.optimize(request(), cancel_event=stop)
    decode.assert_not_called()
    body = TimelineSuggestRequest(samples=[sample()], timelines=[pipeline()], description="white square")
    with patch("backend.ai_evidence.decode_image") as decode, pytest.raises(WorkCancelled):
        prepare_evidence(body, cancel_event=stop)
    decode.assert_not_called()


def test_single_pass_executor_stops_after_native_call_before_next_node():
    stop = threading.Event(); calls = []; apply = search_execution.apply_operation
    def cancelling_apply(*args):
        calls.append(args[1].kind)
        result = apply(*args)
        stop.set()
        return result
    with patch("backend.search_execution.apply_operation", cancelling_apply), pytest.raises(WorkCancelled):
        execute(image(), [pipeline()], "main", Measurements(fields=[]), cancel_event=stop)
    assert calls == ["grayscale"]


def test_incomplete_final_timing_remains_unknown_and_has_a_separate_bound():
    clock = [0.0]
    def controlled_execute(source, graphs, selected, measurements, cache=None,
                           cancel_event=None, deadline=None, **kwargs):
        if deadline is not None and clock[0] > deadline:
            raise SearchDeadline()
        clock[0] += 1.0
        return Frame(np.zeros(source.shape[:2], np.uint8), "mask",
                     details={"detections": [{"normalized_box": [.25, .25, .375, .375]}],
                              "measurement_basis": "same"}), 1.0
    with patch("backend.optimizer.execute", controlled_execute), \
         patch("backend.optimizer.time.monotonic", side_effect=lambda: clock[0]):
        result = optimizer.optimize(request())
    assert result["timing_incomplete"]
    assert result["wall_ms"] <= 6000  # two budgets, each with at most one native-call overrun
    assert result["candidates"][0]["baseline"]
    for candidate in result["candidates"]:
        assert candidate["local_ms"] is None and candidate["local_range_ms"] is None
        assert candidate["target"] is None and not candidate["recommended"]


def test_shortlist_keeps_a_fast_no_regression_alternative_beside_quality_gains():
    positive = sample()
    positive.boxes.append(type(positive.boxes[0])(x=.7, y=.7, width=.1, height=.1))
    seeds = [{"name": name, "timelines": [pipeline(name)], "selected_timeline_id": name}
             for name in ("quality-a", "quality-b", "fast")]
    def controlled_execute(source, graphs, selected, measurements, *args, **kwargs):
        boxes = [[.25, .25, .375, .375]]
        if selected.startswith("quality"):
            boxes.append([.7, .7, .1, .1])
        elapsed = {"main": 10, "quality-a": 100, "quality-b": 120, "fast": 1}[selected]
        return Frame(np.zeros(source.shape[:2], np.uint8), "mask",
                     details={"detections": [{"normalized_box": box} for box in boxes],
                              "measurement_basis": "same"}), elapsed
    # Distinct threshold constants stop semantic deduplication of these seed fixtures.
    for value, seed in enumerate(seeds, 130):
        seed["timelines"][0].operations[1].params["value"] = value
    with patch("backend.optimizer.execute", controlled_execute):
        result = optimizer.optimize(request(samples=[positive], seeds=seeds))
    selected = {candidate["selected_timeline_id"]: candidate for candidate in result["candidates"]}
    assert "quality-a" in selected and "fast" in selected
    assert selected["fast"]["metrics"]["f1"] == selected["main"]["metrics"]["f1"]
    assert selected["fast"]["recommended"]


def test_ai_evidence_uses_all_training_only_focus_first_and_at_most_nine_previews():
    poison = Sample(id="held", name="SECRET-VALIDATION", data="must never decode this", split="validation")
    body = TimelineSuggestRequest(samples=[sample(), sample("negative", False), poison],
                                  timelines=[pipeline(name) for name in ("a", "b", "c", "focus")],
                                  focus_timeline_id="focus", description="white square")
    evidence = prepare_evidence(body)
    assert [row["sample_id"] for row in evidence["family_summary"]] == ["positive", "negative"]
    assert all([p["id"] for p in row["pipelines"]] == ["focus", "a", "b"]
               for row in evidence["family_summary"])
    first = evidence["images"][0]
    assert len(first["stages"]) <= 9
    assert all(node in first["stages"] for path in first["timelines"] for node in path["path"][-3:])
    assert evidence["family_summary"][0]["pipelines"][0]["fit"]["tp"] == 1
    assert evidence["family_summary"][1]["pipelines"][0]["fit"]["fp"] == 0
    response = AsyncMock(return_value={"summary": "check", "timelines": [], "limitations": []})
    # Capture the actual provider content; deliberately empty output is rejected only after capture.
    with patch("backend.ai.response", response), pytest.raises(ValueError, match="invalid pipeline"):
        asyncio.run(timeline_ai.suggest(body, "test-key", evidence))
    content = response.call_args.args[2]
    assert "SECRET-VALIDATION" not in json.dumps(content)
    assert sum(item["type"] == "input_image" for item in content) <= 11  # 2 originals + 9 stages
    text_payloads = [json.loads(item["text"]) for item in content if item["type"] == "input_text"
                     and item["text"].startswith("{")]
    family = next(item["training_family_results"] for item in text_payloads if "training_family_results" in item)
    assert [row["sample_id"] for row in family] == ["positive", "negative"]


def test_ai_evidence_records_failed_experimental_path_without_losing_good_branch():
    broken = pipeline("broken", [operation("bad-threshold", "threshold")])
    body = TimelineSuggestRequest(samples=[sample(), sample("negative", False)],
                                  timelines=[broken, pipeline()], description="white square")
    evidence = prepare_evidence(body)
    for row in evidence["family_summary"]:
        bad, good = row["pipelines"]
        assert bad["id"] == "broken" and bad["status"] == "error"
        assert "needs gray or mask" in bad["error"] and bad["screen_ms"] is None
        assert good["id"] == "main" and good["status"] == "ok"
    assert "bad-threshold" not in evidence["images"][0]["stages"]
    assert "main-d" in evidence["images"][0]["stages"]
    response = AsyncMock(return_value={"summary": "check", "timelines": [], "limitations": []})
    with patch("backend.ai.response", response), pytest.raises(ValueError, match="invalid pipeline"):
        asyncio.run(timeline_ai.suggest(body, "test-key", evidence))
    assert "needs gray or mask" in json.dumps(response.call_args.args[2])
