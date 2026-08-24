## Patient_Triage.AI
### Our repo structure


```
PatientTriage.ai/
│
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── routes_patients.py
│   │   ├── routes_triage.py
│   │   ├── routes_queue.py
│   │   └── routes_overrides.py
│   ├── core/
│   │   ├── config.py
│   │   └── database.py
│   ├── models/
│   │   ├── schemas.py          # Pydantic request/response models
│   │   └── orm.py               # SQLAlchemy table models (new — see note 1)
│   └── services/
│       ├── triage_service.py
│       ├── queue_service.py
│       └── audit_service.py
│
├── risk_engine/
│   ├── __init__.py               # new — see note 2
│   ├── predictor.py
│   ├── safety_rules.py
│   ├── config.py  
│   ├── uncertainty.py
│   ├── feature_engineering.py    # new — see note 3
│   └── artifacts/
│       ├── pipeline_xgboost.joblib
│       ├── engine_config.json
│       └── model_card.json
│       └── challengers/          # new — see note 4
│           ├── logistic_regression.joblib
│           ├── random_forest.joblib
│           ├── gradient_boosting.joblib
│           └── svm_rbf.joblib
│
├── simulation/ 
│   ├── ed_simulation.py
│   ├── arrivals.py
│   ├── resources.py
│   ├── queue.py
│   ├── reassessment.py           # new — see note 5
│   └── scenarios.py
│
├── database/
│   ├── schema.sql
│   ├── seed_data.py
│   └── README.md
│
├── frontend/
│   └── tsx , react frontend
│
├── tests/
│   ├── test_risk_engine.py
│   ├── test_api.py
│   └── test_simulation.py
│
├── scripts/
│   └── ...
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