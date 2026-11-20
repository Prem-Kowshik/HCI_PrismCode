from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ParticipantCreate(BaseModel):
    consent_given: bool
    programming_experience: str = Field(..., description="e.g., <1 year, 1-2 years, 3+ years")
    cpp_familiarity: int = Field(..., ge=1, le=5)
    ai_tool_frequency: str = Field(..., description="e.g., Never, Rarely, Weekly, Daily")


class TaskResponseCreate(BaseModel):
    participant_id: str
    task_id: str
    condition: str = Field(..., pattern="^(standard|explanation|verification_guided)$")
    order_index: int = Field(..., ge=0)
    user_verdict: str = Field(..., pattern="^(correct|incorrect)$")
    suspected_error_line: Optional[int] = None
    suspected_error_description: Optional[str] = None
    confidence: int = Field(..., ge=1, le=5)
    time_taken_ms: int = Field(..., ge=0)
    checklist_checked: List[int] = Field(default_factory=list)
    edge_cases_checked: List[int] = Field(default_factory=list)
    expanded_hints_count: int = Field(default=0, ge=0)


class ConditionRatingCreate(BaseModel):
    participant_id: str
    condition: str = Field(..., pattern="^(standard|explanation|verification_guided)$")
    task_set: str = Field(default="core", pattern="^(core|systems_challenge)$")
    mental_demand: int = Field(..., ge=1, le=7)
    effort: int = Field(..., ge=1, le=7)
    frustration: int = Field(..., ge=1, le=7)
    helpfulness: int = Field(..., ge=1, le=7)
    distraction: int = Field(..., ge=1, le=7)
    overall_usability: int = Field(..., ge=1, le=7)
    useful_features: Optional[str] = ""
    confusing_features: Optional[str] = ""
    comments: Optional[str] = ""


class AnalyzeCodeRequest(BaseModel):
    title: str = "Custom C++ Snippet"
    problem_statement: str
    code: str


class GenerateTaskRequest(BaseModel):
    topic: str = Field(..., description="e.g., Sliding window, State machine, Memory pool")
    difficulty: str = Field(default="Medium", pattern="^(Easy|Medium|Hard)$")
    should_contain_bug: bool = True


class CustomTaskCreate(BaseModel):
    title: str = Field(..., min_length=3)
    difficulty: str = Field(default="Medium", pattern="^(Easy|Medium|Hard)$")
    problem_statement: str = Field(..., min_length=5)
    code: str = Field(..., min_length=10)
    ground_truth_correct: bool = True
    ground_truth_error_line: Optional[int] = None
    ground_truth_error_description: Optional[str] = None
    explanation_notes: Optional[List[Dict[str, Any]]] = None
    verification_guided: Optional[Dict[str, Any]] = None
    is_active: bool = True


class SolveProblemRequest(BaseModel):
    problem_statement: str = Field(..., min_length=5)
    language: str = Field(default="C++")
    preferred_interface: str = Field(
        default="verification_guided",
        pattern="^(standard|explanation|verification_guided)$",
    )
