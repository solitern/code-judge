"""Pydantic request/response schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator



class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Public schemas ----------
class PublicSample(BaseModel):
    id: int
    input: str
    output: str
    explanation: str = ""


class PublicProblem(BaseModel):
    id: int
    title: str
    description: str
    input_format: str
    output_format: str
    hint: str
    template: str
    time_limit_ms: int
    memory_limit_mb: int
    output_limit_kb: int
    version: int
    samples: list[PublicSample] = []


class PublicWeek(BaseModel):
    id: int
    week: int
    title: str
    notice: str = ""
    problems: list[PublicProblem] = []


class PublicWeekSummary(BaseModel):
    id: int
    week: int
    title: str
    problem_count: int
    publish_at: datetime


# ---------- Run requests / responses ----------
class RunSampleRequest(BaseModel):
    week_id: int
    problem_id: int
    code: str
    sample_index: int = 0


class RunCustomRequest(BaseModel):
    week_id: int
    problem_id: int
    code: str
    input: str


class RunAllRequest(BaseModel):
    week_id: int
    problem_id: int
    code: str


class PreviewRunSampleRequest(BaseModel):
    problem_id: int = Field(ge=1, le=99)
    code: str
    sample_index: int = Field(default=0, ge=0)


class PreviewRunCustomRequest(BaseModel):
    problem_id: int = Field(ge=1, le=99)
    code: str
    input: str


class PreviewRunAllRequest(BaseModel):
    problem_id: int = Field(ge=1, le=99)
    code: str


class RunCaseResult(BaseModel):
    case_id: int
    passed: bool | None = None
    status: str
    time_ms: float | None = None
    memory_kb: float | None = None
    # Public information (sample/custom/manager preview)
    input: str | None = None
    expected: str | None = None
    actual: str | None = None
    stderr: str | None = None
    compile_error: str | None = None


class RunResponse(BaseModel):
    mode: str
    status: str
    summary: str
    compiled: bool
    compile_error: str | None = None
    passed_count: int = 0
    total_count: int = 0
    results: list[RunCaseResult] = []


# ---------- Admin schemas ----------
class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)


class AdminUserOut(BaseModel):
    username: str


class WeekBase(BaseModel):
    week: int = Field(ge=1, le=52)
    title: str = Field(default="", max_length=200)


class WeekCreate(WeekBase):
    pass


class WeekUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    notice: str | None = Field(default=None, max_length=20000)
    status: str | None = None
    publish_at: datetime | None = None

    @field_validator("status")
    @classmethod
    def check_status(cls, v: str | None) -> str | None:
        if v is not None and v not in ("DRAFT", "SCHEDULED", "PUBLISHED", "ARCHIVED"):
            raise ValueError("invalid status")
        return v


class WeekDuplicate(BaseModel):
    week: int = Field(ge=1, le=52)
    title: str = Field(default="", max_length=200)


class WeekOut(BaseModel):
    id: int
    week: int
    title: str
    notice: str = ""
    status: str
    publish_at: datetime | None
    published_at: datetime | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime
    problem_count: int = 0
    version: int = 0
    has_unverified_solution: bool = False


class WeekJsonCase(BaseModel):
    model_config = ConfigDict(extra="ignore")

    input: str
    output: str
    enabled: bool = True


class WeekJsonProblem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int = Field(ge=1, le=99)
    title: str = Field(default="", max_length=200)
    description: str = ""
    input_format: str = Field(
        default="",
        validation_alias=AliasChoices("inputFormat", "input_format"),
    )
    output_format: str = Field(
        default="",
        validation_alias=AliasChoices("outputFormat", "output_format"),
    )
    hint: str = ""
    template: str = ""
    time_limit_ms: int = Field(default=2000, ge=100, le=30000)
    memory_limit_mb: int = Field(default=256, ge=16, le=1024)
    output_limit_kb: int = Field(default=1024, ge=16, le=10240)
    sort_order: int | None = Field(default=None, ge=0, le=10000)
    samples: list[WeekJsonCase] = Field(default_factory=list)
    test_cases: list[WeekJsonCase] = Field(
        default_factory=list,
        validation_alias=AliasChoices("testCases", "test_cases"),
    )


class WeekJsonImport(BaseModel):
    model_config = ConfigDict(extra="ignore")

    week: int = Field(ge=1, le=52)
    title: str = Field(default="", max_length=200)
    problems: list[WeekJsonProblem] = Field(min_length=1, max_length=99)

    @model_validator(mode="after")
    def problem_ids_must_be_unique(self):
        ids = [problem.id for problem in self.problems]
        if len(ids) != len(set(ids)):
            raise ValueError("题目 ID 不能重复")
        return self


class WeekJsonImportResult(BaseModel):
    title: str
    problems_imported: int
    samples_imported: int
    hidden_cases_imported: int


class ProblemUpsert(BaseModel):
    stable_id: int = Field(ge=1, le=99)
    title: str = Field(default="", max_length=200)
    description: str = ""
    input_format: str = ""
    output_format: str = ""
    hint: str = ""
    template: str = ""
    time_limit_ms: int = Field(default=2000, ge=100, le=30000)
    memory_limit_mb: int = Field(default=256, ge=16, le=1024)
    output_limit_kb: int = Field(default=1024, ge=16, le=10240)
    sort_order: int = Field(default=0, ge=0, le=10000)


class ProblemOut(BaseModel):
    id: int
    week_id: int
    stable_id: int
    title: str
    description: str
    input_format: str
    output_format: str
    hint: str
    template: str
    time_limit_ms: int
    memory_limit_mb: int
    output_limit_kb: int
    sort_order: int
    version: int
    has_solution: bool = False
    solution_verified: bool = False


class TestCaseUpsert(BaseModel):
    input: str
    output: str
    is_public: bool = False
    sort_order: int = 0
    enabled: bool = True


class TestCaseImportItem(BaseModel):
    """One case in a batch import.

    The aliases keep the existing import endpoint backwards compatible while
    still letting FastAPI/Pydantic validate every field before any row is
    written to the database.
    """

    model_config = ConfigDict(extra="forbid")

    input: str = Field(validation_alias=AliasChoices("input", "in"))
    output: str = Field(validation_alias=AliasChoices("output", "out", "expected"))
    is_public: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("is_public", "public"),
    )
    enabled: bool = True


class TestCaseImportRequest(BaseModel):
    cases: list[TestCaseImportItem] = Field(min_length=1)
    public_default: bool = False


class TestCaseImportResult(BaseModel):
    imported: int
    solution_imported: bool = False


class TestCaseOut(BaseModel):
    id: int
    problem_id: int
    is_public: bool
    input: str
    output: str
    sort_order: int
    enabled: bool


class SolutionUpsert(BaseModel):
    code: str = Field(max_length=65536)


class SolutionOut(BaseModel):
    problem_id: int
    code: str
    verified: bool
    last_verified_at: datetime | None


class DashboardOut(BaseModel):
    current_public_week: WeekOut | None = None
    next_scheduled_publish: WeekOut | None = None
    draft_count: int = 0
    scheduled_count: int = 0
    published_count: int = 0
    archived_count: int = 0
    last_updated_at: datetime | None = None
    runner_status: str = "unknown"
    runner_concurrency: int = 0
    judge_max_concurrency: int = 0
    judge_queue_size: int = 0


class WeekPreviewOut(BaseModel):
    id: int
    week: int
    title: str
    notice: str = ""
    status: str
    is_preview: bool = True
    problems: list["ProblemPreviewOut"] = []


class ProblemPreviewOut(BaseModel):
    id: int
    stable_id: int
    title: str
    description: str
    input_format: str
    output_format: str
    hint: str
    template: str
    time_limit_ms: int
    memory_limit_mb: int
    output_limit_kb: int
    version: int
    samples: list[TestCaseOut] = []
    hidden_cases: list[TestCaseOut] = []


class SnapshotOut(BaseModel):
    id: int
    week_id: int
    version: int
    created_at: datetime


class ImportReport(BaseModel):
    dry_run: bool
    weeks_imported: int = 0
    problems_imported: int = 0
    samples_imported: int = 0
    hidden_cases_imported: int = 0
    weeks_updated: int = 0
    errors: list[str] = []
    details: list[str] = []


class ImportLegacyRequest(BaseModel):
    path: str = "example"
    dry_run: bool = False


class BackupInfo(BaseModel):
    path: str
    size_bytes: int
    created_at: datetime
