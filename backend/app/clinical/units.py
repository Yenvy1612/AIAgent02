from __future__ import annotations

from dataclasses import dataclass


MMOL_TO_MG_DL = 18.0182


@dataclass(frozen=True)
class GlucoseMeasurement:
    value: float
    unit: str
    measurement_type: str

    @property
    def mg_dl(self) -> float:
        return self.value if self.unit == "mg/dL" else self.value * MMOL_TO_MG_DL


def glucose_to_mg_dl(value: float, unit: str) -> float:
    if value <= 0:
        raise ValueError("Glucose must be greater than zero")
    if unit == "mg/dL":
        return value
    if unit == "mmol/L":
        return value * MMOL_TO_MG_DL
    raise ValueError("Unit must be mg/dL or mmol/L")

