"""Verify the map scorer distinguishes accurate walls from displaced/missing ones."""
from pathlib import Path
import pytest
from lab_patrol.metrics import map_accuracy


def raster_map(directory, shift=0, unknown=False):
    boxes = [[-4.1, 0, .2, 8.4, 1], [4.1, 0, .2, 8.4, 1],
             [0, -4.1, 8, .2, 1], [0, 4.1, 8, .2, 1], [0, 0, 1, 1, 1]]
    # Include cells on both sides of each wall; mimic a learned occupancy map.
    pixels = []
    for row in range(180):
        for col in range(180):
            x, y = -4.5+(col+.5)*.05, -4.5+(180-row-.5)*.05
            solid = any(abs(x-bx-shift) <= w/2 and abs(y-by) <= d/2 for bx,by,w,d,_ in boxes)
            pixels.append(205 if unknown and x > 0 else (0 if solid else 254))
    (directory/'map.pgm').write_bytes(b'P5\n180 180\n255\n'+bytes(pixels))
    (directory/'map.yaml').write_text('image: map.pgm\nresolution: 0.05\norigin: [-4.5, -4.5, 0]\n')
    return map_accuracy(directory/'map.yaml', boxes)


def test_correct_map_passes_boundary_metrics(tmp_path):
    metrics = raster_map(tmp_path)
    # Only visible surfaces, rather than the solid bench interior, match boundaries.
    assert metrics['boundary_recall_12cm'] > .95
    assert metrics['known_cell_accuracy'] == pytest.approx(1)
    assert metrics['known_fraction'] == pytest.approx(1)


def test_displaced_map_is_not_aligned_to_hide_error(tmp_path):
    good = raster_map(tmp_path)
    bad = raster_map(tmp_path, shift=.4)
    assert bad['occupied_precision_12cm'] < good['occupied_precision_12cm']
    assert bad['boundary_recall_12cm'] < .75


def test_unknown_space_reduces_coverage_and_recall(tmp_path):
    metrics = raster_map(tmp_path, unknown=True)
    assert metrics['known_fraction'] == pytest.approx(.5)
    assert metrics['boundary_recall_12cm'] < .7
