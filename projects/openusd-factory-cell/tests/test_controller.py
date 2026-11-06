import asyncio
import importlib
import sys

import pytest
from pxr import Usd, UsdGeom

import factory_cell as fc


class Context:
    """Only Kit's external boundary is doubled; files and stages stay real."""

    def __init__(self):
        self.stage = None
        self.error = None
        self.gate = None

    async def open_stage_async(self, path):
        if self.gate:
            await self.gate.wait()
        if self.error:
            return False, self.error
        self.stage = Usd.Stage.Open(path)
        return True, ""

    def get_stage(self):
        return self.stage


class Timeline:
    def __init__(self):
        self.playing = False
        self.current = 99
        self.start = None
        self.end = None
        self.stops = 0

    def set_start_time(self, value):
        self.start = value

    def set_end_time(self, value):
        self.end = value

    def set_current_time(self, value):
        self.current = value

    def play(self):
        self.playing = True

    def stop(self):
        self.playing = False
        self.stops += 1


@pytest.fixture
def controls():
    return Context(), Timeline()


def controller(*controls):
    return fc.CellController(*controls)


async def test_load_validate_start_and_stop_use_seconds(tmp_path, controls):
    path = fc.build_cell(tmp_path / "cell", seconds=12, fps=30)
    context, timeline = controls
    tool = controller(context, timeline)
    report = await tool.load_stage(path)
    assert report.valid
    assert tool.start().valid
    assert timeline.playing
    assert timeline.start == timeline.current == 0
    assert timeline.end == 12  # 360 time codes at 30/s, not 360 seconds.
    tool.stop()
    assert not timeline.playing
    assert context.get_stage().GetRootLayer().realPath == str(path)


async def test_invalid_stage_blocks_start(stage_path, controls):
    context, timeline = controls
    tool = controller(context, timeline)
    await tool.load_stage(stage_path)
    UsdGeom.SetStageMetersPerUnit(context.stage, 0.01)
    report = tool.start()
    assert not report.valid
    assert not timeline.playing


async def test_stage_swap_preserves_other_scene_and_playback(stage_path, controls):
    context, timeline = controls
    tool = controller(context, timeline)
    await tool.load_stage(stage_path)
    tool.start()
    context.stage = Usd.Stage.CreateInMemory()
    before = timeline.stops
    assert not tool.start().valid
    assert not tool.validate().valid
    tool.stop()
    tool.shutdown()
    assert timeline.stops == before
    assert timeline.playing


async def test_load_failure_is_reported(stage_path, controls):
    context, timeline = controls
    context.error = "could not open stage"
    tool = controller(context, timeline)
    report = await tool.load_stage(stage_path)
    assert not report.valid
    assert report.issues[0].code == "LOAD"
    assert not tool.start().valid
    assert not timeline.playing


async def test_preflight_failure_does_not_replace_current_scene(tmp_path, controls):
    context, timeline = controls
    original = Usd.Stage.CreateInMemory()
    context.stage = original
    tool = controller(context, timeline)
    report = await tool.load_stage(tmp_path / "missing.usda")
    assert not report.valid
    assert context.stage == original
    assert not timeline.playing


async def test_shutdown_stops_owned_playback_and_cannot_restart(stage_path, controls):
    context, timeline = controls
    tool = controller(context, timeline)
    await tool.load_stage(stage_path)
    tool.start()
    tool.shutdown()
    assert not timeline.playing
    assert not tool.start().valid
    assert not (await tool.load_stage(stage_path)).valid
    assert context.get_stage()  # Disabling the extension keeps the user's stage open.


async def test_unstarted_controller_does_not_stop_existing_playback(stage_path, controls):
    context, timeline = controls
    tool = controller(context, timeline)
    await tool.load_stage(stage_path)
    timeline.playing = True  # Playback started by another tool.
    tool.shutdown()
    assert timeline.playing
    assert timeline.stops == 0


async def test_overlapping_loads_are_rejected_and_cancellation_releases_busy(stage_path, controls):
    context, timeline = controls
    context.gate = asyncio.Event()
    tool = controller(context, timeline)
    pending = asyncio.create_task(tool.load_stage(stage_path))
    await asyncio.sleep(0)
    assert not (await tool.load_stage(stage_path)).valid
    assert not tool.start().valid
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    context.gate.set()
    assert (await tool.load_stage(stage_path)).valid


def test_plain_core_never_imports_kit():
    importlib.reload(fc)
    assert not any(name == "omni" or name.startswith("omni.") for name in sys.modules)
