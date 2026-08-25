## Patient_Triage.AI
### Our repo structure


```
PatientTriage.ai/
│
├── app/                              # FastAPI layer only: HTTP + orchestration
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py                   # DB session + auth dependencies
│   │   ├── routes_patients.py
│   │   ├── routes_triage.py
│   │   ├── routes_queue.py
│   │   ├── routes_overrides.py
│   │   ├── routes_simulation.py      # trigger normal / 3x surge runs
│   │   └── routes_audit.py           # DPDP audit trail read-back
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                 # pydantic-settings, reads .env
│   │   ├── database.py               # engine, SessionLocal, get_db
│   │   └── security.py               # API key, PII redaction helpers
│   ├── models/
│   │   ├── __init__.py
│   │   ├── orm.py                    # SQLAlchemy — authoritative schema
│   │   └── schemas.py                # Pydantic request/response
│   └── services/
│       ├── __init__.py
│       ├── triage_service.py
│       ├── queue_service.py
│       ├── reassessment_service.py   # live wait-time / worsening-vitals monitor
│       ├── simulation_service.py
│       └── audit_service.py
│
├── risk_engine/                      # zero framework deps: no FastAPI, no SimPy
│   ├── __init__.py
│   ├── config.py
│   ├── feature_engineering.py
│   ├── safety_rules.py
│   ├── uncertainty.py
│   ├── reassessment.py               # pure policy: is this patient due for re-triage?
│   ├── predictor.py
│   └── artifacts/
│       ├── pipeline_xgboost.joblib
│       ├── engine_config.json
│       ├── model_card.json      
│       └── challengers/
│           ├── logistic_regression.joblib
│           ├── random_forest.joblib
│           ├── gradient_boosting.joblib
│           └── svm_rbf.joblib
│
├── synthetic/                        # shared synthetic patient source
│   ├── __init__.py
│   └── generator.py   
│
├── simulation/                       # may import risk_engine + synthetic, never app
│   ├── __init__.py
│   ├── arrivals.py
│   ├── resources.py
│   ├── queue.py
│   ├── ed_simulation.py
│   └── scenarios.py                  # normal vs 3x surge configurations
│
├── database/
│   ├── __init__.py
│   ├── seed_data.py
│   ├── schema.sql                    # generated, not hand-edited
│   └── README.md
│
├── frontend/                         # built separately — placeholder + API contract only
│   └── README.md
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_risk_engine.py
│   ├── test_synthetic.py
│   ├── test_api.py
│   └── test_simulation.py
│    
├── scripts/
│   ├── export_schema.py              # ORM -> database/schema.sql
│   ├── run_simulation.py             # CLI: normal + surge, prints the comparison table
│   └── demo_showcase.py              # the PS edge-case walkthrough, ~20 records
│
├── notebooks/
│   └── PatientTriage_ai_Risk_Engine1.ipynb
│
├── docs/
│   ├── architecture.md
│   └── regulatory_dpdp.md            # jurisdiction assumption + what an override records
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore         
├── README.md
└── .github/
    └── workflows/
        └── ci-cd.yml
```