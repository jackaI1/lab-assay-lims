"""FHIR R4 core Observations, retaining the original quantity and offset."""
from typing import Iterable
from .model import Reading


def observations(readings: Iterable[Reading]) -> list[dict]:
    """Export source rows, including duplicate timestamps. No fabricated patient.

    CodeableConcept.text describes the measurement without asserting an unverified
    terminology code or compliance with a clinical implementation profile.
    """
    return [{
        'resourceType': 'Observation', 'id': f'reading-{index}', 'status': 'final',
        'code': {'text': 'Interstitial glucose measured by continuous glucose monitor'},
        'effectiveDateTime': reading.timestamp.isoformat(),
        'valueQuantity': {'value': reading.value, 'unit': reading.unit,
                          'system': 'http://unitsofmeasure.org', 'code': reading.unit},
    } for index, reading in enumerate(readings, start=1)]
