"""All DOM knowledge lives here, following Selenium's page object pattern."""

from collections.abc import Callable
from math import isfinite
from typing import Literal

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from .models import InstrumentError, OperationTimeout, Settings

Fault = Literal[
    "normal", "timeout", "bad-reading", "non-finite", "wrong-unit", "drift", "error", "stale"
]


class SupplyPage:
    def __init__(self, driver: WebDriver, url: str, timeout: float = 3.0) -> None:
        if not isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and positive")
        self.driver = driver
        self.url = url
        self.wait = WebDriverWait(driver, timeout, poll_frequency=0.05)

    def _wait(self, condition: Callable[[WebDriver], object], operation: str) -> None:
        try:
            self.wait.until(condition)
        except TimeoutException as exc:
            raise OperationTimeout(f"Timed out waiting for {operation}") from exc

    def _text(self, name: str) -> str:
        return self.driver.find_element(By.ID, name).text

    def _attribute(self, name: str) -> str:
        value = self.driver.find_element(By.ID, "device").get_attribute(f"data-{name}")
        if value is None:
            raise InstrumentError(f"Missing instrument attribute: {name}")
        return value

    def open(self) -> None:
        self.driver.get(self.url)
        self._wait(EC.element_to_be_clickable((By.ID, "apply")), "control page")

    def configure(self, settings: Settings) -> int:
        previous = int(self._attribute("revision"))
        for name, value in (
            ("voltage", settings.voltage_v),
            ("resistance", settings.resistance_ohm),
        ):
            field = self.driver.find_element(By.ID, name)
            field.clear()
            field.send_keys(str(value))
        self.driver.find_element(By.ID, "apply").click()
        self._wait(
            lambda _: (
                int(self._attribute("revision")) > previous
                and self._text("status") == "Ready"
                and self._attribute("output") == "on"
            ),
            "settings acknowledgement",
        )
        return int(self._attribute("revision"))

    def acquire(self) -> dict[str, str]:
        previous = int(self._attribute("sequence"))
        self.driver.find_element(By.ID, "measure").click()

        def completed(_: WebDriver) -> bool:
            if self._text("status") == "Error":
                raise InstrumentError(self._text("message"))
            return int(self._attribute("sequence")) > previous and self._text("status") == "Ready"

        self._wait(completed, "a fresh measurement")
        return {
            "voltage": self._text("voltage-reading"),
            "current": self._text("current-reading"),
            "voltage_unit": self._text("voltage-unit"),
            "current_unit": self._text("current-unit"),
            "sequence": self._attribute("sequence"),
            "revision": self._attribute("reading-revision"),
        }

    def output_off(self) -> None:
        self.driver.find_element(By.ID, "off").click()
        self._wait(lambda _: self._attribute("output") == "off", "output shutdown")

    def select_fault(self, fault: Fault) -> None:
        """Simulator control only; never needed for normal instrument operation."""
        Select(self.driver.find_element(By.ID, "fault")).select_by_value(fault)
