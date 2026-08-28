
"""Seed the database with showcase patients for the PS edge-case walkthrough.

    python scripts/demo_showcase.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal, init_db
from app.models.schemas import PatientIn, VisitIntakeRequest, VitalsIn
from app.services import triage_service


SHOWCASE_CASES = [
    {
        "label": "Cardiac arrest — immediate resuscitation",
        "patient": PatientIn(age=58, gender="male", has_prior_history=True, prior_conditions_count=3),
        "chief_complaint": "cardiac_arrest",
        "symptom_text": "unresponsive, no pulse, found collapsed at home",
        "arrival_mode": "ambulance",
        "vitals": VitalsIn(heart_rate=25, systolic_bp=45, spo2=60, resp_rate=6, temperature_c=35.5, pain_score=0),
    },
    {
        "label": "Ambiguous — chest pain with normal vitals",
        "patient": PatientIn(age=42, gender="male"),
        "chief_complaint": "chest_pain",
        "symptom_text": "mild substernal pressure for 2 hours, no radiation",
        "arrival_mode": "walk-in",
        "vitals": VitalsIn(heart_rate=78, systolic_bp=128, spo2=98, resp_rate=16, temperature_c=36.8, pain_score=4),
        "is_ambiguous_case": True,
    },
    {
        "label": "Pediatric febrile seizure",
        "patient": PatientIn(age=3, gender="female"),
        "chief_complaint": "seizure",
        "symptom_text": "febrile seizure lasting 2 minutes, now post-ictal",
        "arrival_mode": "ambulance",
        "vitals": VitalsIn(heart_rate=155, systolic_bp=85, spo2=94, resp_rate=32, temperature_c=39.8, pain_score=8),
    },
    {
        "label": "Geriatric fall with altered consciousness",
        "patient": PatientIn(
            age=82, gender="female", has_prior_history=True,
            prior_conditions_count=5, prior_ed_visits=4,
        ),
        "chief_complaint": "trauma",
        "symptom_text": "fell at home, confused, large scalp laceration, bleeding",
        "arrival_mode": "ambulance",
        "vitals": VitalsIn(heart_rate=92, systolic_bp=100, spo2=93, resp_rate=22, temperature_c=36.2, pain_score=6),
    },
    {
        "label": "Low-acuity — minor laceration",
        "patient": PatientIn(age=28, gender="male"),
        "chief_complaint": "laceration",
        "symptom_text": "small cut on forearm from kitchen knife, bleeding controlled",
        "arrival_mode": "walk-in",
        "vitals": VitalsIn(heart_rate=72, systolic_bp=122, spo2=99, resp_rate=14, temperature_c=36.7, pain_score=3),
    },
    {
        "label": "Missing vitals — only age and complaint known",
        "patient": PatientIn(age=55, gender="other"),
        "chief_complaint": "shortness_of_breath",
        "symptom_text": "progressive dyspnea over 3 days, unable to walk upstairs",
        "arrival_mode": "referred",
        "vitals": VitalsIn(),  # all vitals missing — engine should escalate
    },
]


def main() -> int:
    init_db()
    db = SessionLocal()
    try:
        for i, case in enumerate(SHOWCASE_CASES, 1):
            req = VisitIntakeRequest(
                patient=case["patient"],
                chief_complaint=case["chief_complaint"],
                symptom_text=case["symptom_text"],
                arrival_mode=case["arrival_mode"],
                vitals=case["vitals"],
                is_ambiguous_case=case.get("is_ambiguous_case", False),
            )
            result = triage_service.intake(db, req)
            print(f"[{i}/{len(SHOWCASE_CASES)}] {case['label']}")
            print(f"  -> P{result.assessment.final_priority} "
                  f"({result.assessment.priority_label}) "
                  f"risk={result.assessment.risk_probability:.3f} "
                  f"confidence={result.assessment.confidence_label}")
            if result.assessment.safety_rules_triggered:
                print(f"  -> safety: {result.assessment.safety_rules_triggered}")
            print()     
    finally:          
        db.close()         
                        
    print(f"[ok] seeded {len(SHOWCASE_CASES)} showcase patients")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
