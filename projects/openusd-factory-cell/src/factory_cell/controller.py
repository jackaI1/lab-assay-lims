"""Kit-independent lifecycle controller with injected context and timeline APIs."""

from pathlib import Path

from .validation import ValidationReport, validate_stage


def _failure(code, message):
    report = ValidationReport()
    report.add(code, "/", message)
    return report


class CellController:
    def __init__(self, context, timeline):
        self._context = context
        self._timeline = timeline
        self._stage = None
        self._busy = False
        self._closed = False
        self._playing = False

    def _owns_stage(self):
        return self._stage is not None and self._context.get_stage() == self._stage

    async def load_stage(self, path: str | Path) -> ValidationReport:
        if self._closed:
            return _failure("CLOSED", "Controller has been shut down.")
        if self._busy:
            return _failure("BUSY", "A stage load is already in progress.")
        self._busy = True
        try:
            path = str(Path(path).expanduser().absolute())
            report = validate_stage(path)
            if not report.valid:
                return report
            self.stop()
            self._stage = None
            success, error = await self._context.open_stage_async(path)
            if self._closed:
                return _failure("CLOSED", "Controller shut down during load.")
            if not success:
                return _failure("LOAD", error or "Kit could not open the stage.")
            self._stage = self._context.get_stage()
            return self.validate()
        except (OSError, ValueError, RuntimeError) as exc:
            return _failure("LOAD", str(exc))
        finally:
            self._busy = False

    def validate(self) -> ValidationReport:
        if self._closed:
            return _failure("CLOSED", "Controller has been shut down.")
        if not self._owns_stage():
            return _failure("STAGE_OWNERSHIP", "Load a cell here before controlling its timeline.")
        return validate_stage(self._stage)

    def start(self) -> ValidationReport:
        if self._busy:
            return _failure("BUSY", "Wait for the stage load to finish.")
        report = self.validate()
        if report.valid:
            rate = self._stage.GetTimeCodesPerSecond()
            self._timeline.set_start_time(self._stage.GetStartTimeCode() / rate)
            self._timeline.set_end_time(self._stage.GetEndTimeCode() / rate)
            self._timeline.set_current_time(self._stage.GetStartTimeCode() / rate)
            self._timeline.play()
            self._playing = True
        else:
            self.stop()
        return report

    def stop(self):
        if self._playing and self._owns_stage():
            self._timeline.stop()
        self._playing = False

    def shutdown(self):
        self.stop()
        self._closed = True
        self._stage = None
