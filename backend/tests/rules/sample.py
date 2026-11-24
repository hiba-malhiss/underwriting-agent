"""A small rulebook like the one the LLM would build from health underwriting guidelines."""

from app.rules.models import Rulebook

GUIDE = "health-underwriting-guidelines.pdf"


def source(quote: str, page: int = 1) -> dict:
    return {"document": GUIDE, "page": page, "quote": quote}


def sample_rulebook() -> Rulebook:
    return Rulebook.model_validate(
        {
            "parameters": [
                {
                    "name": "age",
                    "value_type": "number",
                    "unit": "years",
                    "description": "Age",
                    "source": source("Applicants over 65 years of age are not eligible"),
                },
                {
                    "name": "bmi",
                    "value_type": "number",
                    "description": "Body mass index",
                    "source": source("A BMI above 35 requires review", 2),
                },
                {
                    "name": "smoker",
                    "value_type": "boolean",
                    "description": "Smokes tobacco",
                    "source": source("Smokers are referred for review", 2),
                },
                {
                    "name": "conditions",
                    "value_type": "list",
                    "description": "Known conditions",
                    "allowed_values": ["diabetes_type_2", "heart_disease", "asthma"],
                    "source": source("Applicants with type 2 diabetes and a BMI above 30", 2),
                },
            ],
            "rules": [
                {
                    "name": "max_age",
                    "description": "Over 65 is not eligible",
                    "rule_type": "automatic",
                    "conditions": {
                        "all_of": [{"parameter": "age", "operator": "greater_than", "value": 65}]
                    },
                    "outcome": "decline",
                    "source": source("Applicants over 65 years of age are not eligible"),
                },
                {
                    "name": "smoker_review",
                    "description": "Smokers are referred for review",
                    "rule_type": "automatic",
                    "conditions": {
                        "all_of": [{"parameter": "smoker", "operator": "equals", "value": True}]
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
                        "all_of": [
                            {
                                "parameter": "conditions",
                                "operator": "contains",
                                "value": "diabetes_type_2",
                            },
                            {
                                "any_of": [
                                    {"parameter": "bmi", "operator": "greater_than", "value": 30},
                                    {"parameter": "smoker", "operator": "equals", "value": True},
                                ]
                            },
                        ]
                    },
                    "outcome": "refer",
                    "source": source("Applicants with type 2 diabetes and a BMI above 30", 2),
                },
                {
                    "name": "heart_review",
                    "description": "Heart conditions at the underwriter's discretion",
                    "rule_type": "judgment",
                    "outcome": "refer",
                    "source": source("Heart conditions are at the underwriter's discretion", 3),
                },
            ],
        }
    )
