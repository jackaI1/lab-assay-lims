"""Exercise the actual IExt adapter without claiming a native Kit GUI run."""

import asyncio
import importlib
import sys
import tomllib
import types
from pathlib import Path

import pytest
from test_controller import Context, Timeline


class Widget:
    def __init__(self, *args, **kwargs):
        self.text = args[0] if args else ""
        self.model = self
        self.frame = self
        self.value = ""
        self.destroyed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def set_value(self, value):
        self.value = value

    def get_value_as_string(self):
        return self.value

    def destroy(self):
        self.destroyed = True


@pytest.fixture
def host(monkeypatch):
    # Reproduce only unavailable host interfaces; use the real core and USD throughout.
    context, timeline = Context(), Timeline()
    omni = types.ModuleType("omni")
    for name, attributes in {
        "ext": {"IExt": object},
        "ui": {
            name: Widget
            for name in ["Window", "VStack", "HStack", "Label", "StringField", "Button"]
        },
        "usd": {"get_context": lambda: context},
        "timeline": {"get_timeline_interface": lambda: timeline},
    }.items():
        module = types.ModuleType("omni." + name)
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, "omni." + name, module)
        setattr(omni, name, module)
    monkeypatch.setitem(sys.modules, "omni", omni)
    manifest_path = Path("exts/jack.factory.cell/config/extension.toml")
    manifest = tomllib.loads(manifest_path.read_text())
    # Resolve precisely the module path that Kit is told to import.
    module_config = manifest["python"]["module"][-1]
    python_path = manifest_path.parent.parent / module_config.get("path", ".")
    monkeypatch.syspath_prepend(str(python_path))
    module = importlib.import_module(module_config["name"])
    extension = module.FactoryCellExtension()
    extension.on_startup("jack.factory.cell")
    try:
        yield extension, context, timeline
    finally:
        extension.on_shutdown()
        sys.modules.pop("factory_cell_kit", None)
        sys.modules.pop("factory_cell_kit.extension", None)


async def test_manifest_adapter_loads_stage_and_exposes_working_controls(stage_path, host):
    extension, context, timeline = host
    extension._path.model.set_value(str(stage_path))
    extension._queue_load()
    await extension._load_task
    assert context.stage
    assert "PASS" in extension._status.text
    extension._start()
    assert timeline.playing
    extension._stop()
    assert not timeline.playing
    context.stage.GetPrimAtPath("/World/Cell/Part").SetActive(False)
    extension._validate()
    assert "HIERARCHY" in extension._status.text
    extension._start()
    assert not timeline.playing


async def test_adapter_cancels_owned_load_and_destroys_window(stage_path, host):
    extension, context, timeline = host
    context.gate = asyncio.Event()
    extension._path.model.set_value(str(stage_path))
    extension._queue_load()
    task = extension._load_task
    await asyncio.sleep(0)
    window = extension._window
    extension.on_shutdown()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert window.destroyed
    assert not timeline.playing
    assert extension._window is None


async def test_malformed_transform_is_reported_by_validate_and_start(stage_path, host):
    from pxr import Sdf

    extension, context, timeline = host
    extension._path.model.set_value(str(stage_path))
    extension._queue_load()
    await extension._load_task
    prim = context.stage.GetPrimAtPath("/World/Cell/Part")
    prim.CreateAttribute("xformOp:scale:bad", Sdf.ValueTypeNames.String).Set("oops")
    order = prim.GetAttribute("xformOpOrder")
    order.Set([*order.Get(), "xformOp:scale:bad"])
    extension._validate()
    assert "TRANSFORM" in extension._status.text
    extension._start()
    assert "FAIL" in extension._status.text
    assert not timeline.playing
