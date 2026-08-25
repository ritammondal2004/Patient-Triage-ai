
# Shared synthetic ED patient source for seeding and simulation.

from synthetic.generator import (
    ESI_CUTOFFS,
    CHIEF_COMPLAINTS,
    ENGINE_INPUT_FIELDS,
    SyntheticPatient,
    acuity_mix,
    generate_patients,
    showcase_patients,
)

__all__ = [
    "ESI_CUTOFFS",         
    "CHIEF_COMPLAINTS",  
    "ENGINE_INPUT_FIELDS",
    "SyntheticPatient",
    "acuity_mix",
    "generate_patients",
    "showcase_patients",
]