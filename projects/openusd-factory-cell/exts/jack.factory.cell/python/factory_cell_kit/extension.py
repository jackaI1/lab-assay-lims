"""Thin Omniverse Kit adapter. The shared factory_cell core uses only pxr."""

import asyncio

import omni.ext
import omni.timeline
import omni.ui as ui
import omni.usd

from factory_cell import CellController


class FactoryCellExtension(omni.ext.IExt):
    def on_startup(self, ext_id):
        self._controller = CellController(
            omni.usd.get_context(), omni.timeline.get_timeline_interface()
        )
        self._load_task = None
        self._window = ui.Window("Factory Cell", width=580, height=380)
        with self._window.frame:
            with ui.VStack(spacing=8):
                ui.Label(
                    "Generate a cell with factory-cell, then enter its cell.usda path.", height=24
                )
                ui.Label(
                    "Save changes in your current scene before loading another stage.", height=24
                )
                self._path = ui.StringField(height=28)
                with ui.HStack(height=28, spacing=6):
                    ui.Button("Load stage", clicked_fn=self._queue_load)
                    ui.Button("Start", clicked_fn=self._start)
                    ui.Button("Stop", clicked_fn=self._stop)
                    ui.Button("Validate", clicked_fn=self._validate)
                self._status = ui.Label("Enter a local stage path to begin.", word_wrap=True)

    def _report(self, report):
        if self._status is None:
            return
        if report.valid:
            self._status.text = (
                f"PASS | {report.summary['fixture']} fixture | "
                f"{report.summary['cycle_seconds']:g} seconds | "
                f"{report.summary['part_samples']} part samples"
            )
        else:
            self._status.text = "FAIL\n" + "\n".join(
                f"{issue.code}: {issue.path}\n{issue.message}" for issue in report.issues
            )

    def _queue_load(self):
        if self._load_task and not self._load_task.done():
            self._status.text = "A stage load is already in progress."
            return
        path = self._path.model.get_value_as_string().strip()
        if not path:
            self._status.text = "Enter the full path to a generated cell.usda file."
            return
        self._load_task = asyncio.ensure_future(self._load(path))

    async def _load(self, path):
        report = await self._controller.load_stage(path)
        self._report(report)

    def _start(self):
        self._report(self._controller.start())

    def _stop(self):
        self._controller.stop()

    def _validate(self):
        self._report(self._controller.validate())

    def on_shutdown(self):
        if self._load_task and not self._load_task.done():
            self._load_task.cancel()
        self._load_task = None
        if self._controller:
            self._controller.shutdown()
        self._controller = None
        if self._window:
            self._window.destroy()
        self._window = None
        self._path = None
        self._status = None
