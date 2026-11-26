"""A small rulebook like the one the LLM would build from health underwriting guidelines."""

from app.rules.domain.models import Rulebook

GUIDE = "health-underwriting-guidelines.pdf"


def source(quote: str, page: int = 1) -> dict:
    return {"document": GUIDE, "page": page, "quote": quote}


def sample_rulebook() -> Rulebook:
    return Rulebook.model_validate(
        {
            "parameters": [
                {
                    "name": "age",
                    "kind": "application",
                    "value_type": "number",
                    "unit": "years",
                    "description": "Age",
                },
                {
                    "name": "bmi",
                    "kind": "medical",
                    "value_type": "number",
                    "description": "Body mass index",
                },
                {
                    "name": "smoker",
                    "kind": "medical",
                    "value_type": "boolean",
                    "description": "Smokes tobacco",
                },
                {
                    "name": "conditions",
                    "kind": "medical",
                    "value_type": "list",
                    "description": "Known conditions",
                    "allowed_values": ["diabetes_type_2", "heart_disease", "asthma"],
                },
            ],
            "rules": [
                {
                    "name": "max_age",
                    "description": "Over 65 is not eligible",
                    "rule_type": "automatic",
                    "conditions": {
                        "match": "all",
                        "items": [{"parameter": "age", "operator": "greater_than", "value": 65}],
                    },
                    "outcome": "decline",
                    "source": source("Applicants over 65 years of age are not eligible"),
                },
                {
                    "name": "smoker_review",
                    "description": "Smokers are referred for review",
                    "rule_type": "automatic",
                    "conditions": {
                        "match": "all",
                        "items": [{"parameter": "smoker", "operator": "equals", "value": True}],
                    },
                    "outcome": "refer",
                    "source": source("Smokers are referred for review", 2),
                },
                # Nested: diabetes AND (BMI > 30 OR smoker)
                {
                    "name": "diabetes_review",
                    "description": "Diabetes with high BMI or smoking",
                    "rule_type": "automatic",
                    "conditions": {
                        "match": "all",
                        "items": [
                            {
                                "parameter": "conditions",
                                "operator": "contains",
                                "value": "diabetes_type_2",
                            },
                            {
                                "match": "any",
                                "items": [
                                    {"parameter": "bmi", "operator": "greater_than", "value": 30},
                                    {"parameter": "smoker", "operator": "equals", "value": True},
                                ],
                            },
                        ],
                    },
                    "outcome": "refer",
                    "source": source("Applicants with type 2 diabetes and a BMI above 30", 2),
                },
                {
                    "name": "heart_review",
                    "description": "Heart conditions at the underwriter's discretion",
                    "rule_type": "judgment",
                    # Who it's about; an underwriter decides for them
                    "conditions": {
                        "match": "all",
                        "items": [
                            {
                                "parameter": "conditions",
                                "operator": "contains",
                                "value": "heart_disease",
                            }
                        ],
                    },
                    "outcome": "refer",
                    "source": source("Heart conditions are at the underwriter's discretion", 3),
                },
            ],
        }
    )
