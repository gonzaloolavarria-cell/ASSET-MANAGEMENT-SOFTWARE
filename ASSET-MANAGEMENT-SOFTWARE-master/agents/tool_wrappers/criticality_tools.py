"""MCP tool wrappers for CriticalityEngine."""

import json
from agents.tool_wrappers.registry import tool
from tools.engines.criticality_engine import CriticalityEngine
from tools.models.schemas import CriticalityAssessment, CriteriaScore


@tool(
    "assess_criticality",
    'Run full criticality assessment — computes overall_score and risk_class automatically. '
    'Input: JSON string with fields: '
    'assessment_id (str), node_id (str — must match a hierarchy node), '
    'criteria_scores (list of {"category": str, "score": int 1-5} — 11 categories: '
    'SAFETY, HEALTH, ENVIRONMENT, PRODUCTION, OPERATING_COST, CAPITAL_COST, SCHEDULE, REVENUE, COMMUNICATIONS, COMPLIANCE, REPUTATION), '
    'probability (int 1-5). '
    'Optional: assessed_by (default "reliability_agent"), assessed_at (default now), method (default "FULL_MATRIX"). '
    'Example: {"assessment_id": "CA-001", "node_id": "JFC-MI-001", '
    '"criteria_scores": [{"category": "SAFETY", "score": 4}, {"category": "HEALTH", "score": 3}, '
    '{"category": "ENVIRONMENT", "score": 2}, {"category": "PRODUCTION", "score": 5}, '
    '{"category": "OPERATING_COST", "score": 3}, {"category": "CAPITAL_COST", "score": 4}, '
    '{"category": "SCHEDULE", "score": 3}, {"category": "REVENUE", "score": 5}, '
    '{"category": "COMMUNICATIONS", "score": 2}, {"category": "COMPLIANCE", "score": 4}, '
    '{"category": "REPUTATION", "score": 3}], "probability": 3}',
    {"type": "object", "properties": {"input_json": {"type": "string"}}, "required": ["input_json"]},
)
def assess_criticality(input_json: str) -> str:
    data = json.loads(input_json)
    assessment = CriticalityAssessment(**data)
    result = CriticalityEngine.assess(assessment)
    return json.dumps(result.model_dump(), default=str)


@tool(
    "calculate_criticality_score",
    'Calculate raw criticality score from criteria scores and probability. Returns {"overall_score": float}. '
    'criteria_scores: JSON string array of objects, each with "category" (str) and "score" (int 1-5). '
    'All 11 categories required: SAFETY, HEALTH, ENVIRONMENT, PRODUCTION, OPERATING_COST, CAPITAL_COST, SCHEDULE, REVENUE, COMMUNICATIONS, COMPLIANCE, REPUTATION. '
    'probability: int 1-5. Formula: max(all consequence scores) * probability. '
    'Example: criteria_scores=\'[{"category": "SAFETY", "score": 4}, {"category": "HEALTH", "score": 3}, '
    '{"category": "ENVIRONMENT", "score": 2}, {"category": "PRODUCTION", "score": 5}, '
    '{"category": "OPERATING_COST", "score": 3}, {"category": "CAPITAL_COST", "score": 4}, '
    '{"category": "SCHEDULE", "score": 3}, {"category": "REVENUE", "score": 5}, '
    '{"category": "COMMUNICATIONS", "score": 2}, {"category": "COMPLIANCE", "score": 4}, '
    '{"category": "REPUTATION", "score": 3}]\', probability=3',
    {"type": "object", "properties": {"criteria_scores": {"type": "string"}, "probability": {"type": "integer"}}, "required": ["criteria_scores", "probability"]},
)
def calculate_criticality_score(criteria_scores: str, probability: int) -> str:
    scores = [CriteriaScore(**s) for s in json.loads(criteria_scores)]
    result = CriticalityEngine.calculate_overall_score(scores, probability)
    return json.dumps({"overall_score": result})


@tool(
    "determine_risk_class",
    "Determine risk class (I/II/III/IV) from an overall criticality score.",
    {"type": "object", "properties": {"overall_score": {"type": "number"}}, "required": ["overall_score"]},
)
def determine_risk_class(overall_score: float) -> str:
    risk_class = CriticalityEngine.determine_risk_class(overall_score)
    return json.dumps({"risk_class": risk_class.value})


@tool(
    "validate_criticality_matrix",
    "Validate that all 11 criteria categories are covered. Returns list of validation errors.",
    {"type": "object", "properties": {"criteria_scores": {"type": "string"}}, "required": ["criteria_scores"]},
)
def validate_criticality_matrix(criteria_scores: str) -> str:
    scores = [CriteriaScore(**s) for s in json.loads(criteria_scores)]
    errors = CriticalityEngine.validate_full_matrix(scores)
    return json.dumps({"errors": errors, "valid": len(errors) == 0})
