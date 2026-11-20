from typing import List, Optional
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
    expanded_hints_count: int = Field(default=0, ge=0)


class ConditionRatingCreate(BaseModel):
    participant_id: str
    condition: str = Field(..., pattern="^(standard|explanation|verification_guided)$")
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
    topic: str = Field(..., description="e.g., Array traversal, String parsing, Binary search")
    difficulty: str = Field(default="Easy", pattern="^(Easy|Medium|Hard)$")
    should_contain_bug: bool = True


class SolveProblemRequest(BaseModel):
    problem_statement: str = Field(..., min_length=5)
    language: str = Field(default="C++")
    preferred_interface: str = Field(
        default="verification_guided",
        pattern="^(standard|explanation|verification_guided)$",
    )
