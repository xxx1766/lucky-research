"""Pydantic models for the experiments package.

Pure type definitions — no I/O, no side-effects. Imported by ``parsers.py`` for
frontmatter validation and by every caller that takes typed input.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class ExperimentRepo(BaseModel):
    url: str
    branch: str = "main"
    last_known_sha: str | None = None
    clone_status: Literal["tracked", "cloned", "missing"] = "tracked"


class Experiment(BaseModel):
    slug: str
    title: str
    created_at: date
    repo: ExperimentRepo
    papers: list[str] = Field(default_factory=list)
    status: Literal["active", "paused", "archived", "abandoned"] = "active"
    tags: list[str] = Field(default_factory=list)
    body: str = ""


class HostInfo(BaseModel):
    hostname: str
    os: str
    arch: str


class GPUInfo(BaseModel):
    name: str
    count: int = 1
    driver: str | None = None


class Version(BaseModel):
    version: str
    description: str
    kind: Literal["major", "minor"] = "minor"
    status: Literal["planned", "running", "completed", "failed", "abandoned"] = "completed"
    commit_sha: str | None = None
    config_snapshot: str | None = None
    result_file: str | None = None
    mirrored_to: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    host: HostInfo | None = None
    gpu: list[GPUInfo] = Field(default_factory=list)
    cuda: str | None = None
    python: str | None = None
    libraries: dict[str, str] = Field(default_factory=dict)
    libraries_lockfile: str | None = None
    seeds: list[int] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    artifacts: list[str] = Field(default_factory=list)
    notes: str = ""
    body: str = ""


class DataArtifact(BaseModel):
    slug: str
    category: Literal["trace", "dataset", "checkpoint", "log", "plot", "other"]
    size: str | None = None
    sha256: str | None = None
    produced_by: str | None = None
    produced_on: str | None = None
    path: str
    description: str = ""


class Machine(BaseModel):
    """One host in the user's fleet. Used by ``/experiment feasibility``."""
    hostname: str
    gpus: list[GPUInfo] = Field(default_factory=list)
    cpu_cores: int | None = None
    ram_gb: float | None = None
    disk_gb: float | None = None
    network: str | None = None
    available: bool = True
    notes: str = ""


class FleetSnapshot(BaseModel):
    """Snapshot of the user's available machines at a point in time."""
    as_of: date
    machines: list[Machine] = Field(default_factory=list)
    body: str = ""


class FeasibilitySuggestion(BaseModel):
    """One purpose-preserving modification to fit the experiment to the fleet."""
    id: int
    axis: Literal[
        "model-size", "baseline-pruning", "batching", "sharding",
        "dataset-subset", "sequential", "lighter-eval", "mixed-precision",
        "gradient-checkpointing", "other",
    ]
    change: str
    rationale: str
    cost: str = ""


class FeasibilityReport(BaseModel):
    """The structured output of ``/experiment feasibility``.

    Frontmatter of ``feasibility-<date>.md`` files round-trips through this model.
    ``/experiment feasibility apply`` reads ``suggestions`` to drive design
    revisions.
    """
    slug: str
    date: date
    design_version: str                       # 'd1.0'
    verdict: Literal["feasible", "tight", "infeasible"]
    fleet_used: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    suggestions: list[FeasibilitySuggestion] = Field(default_factory=list)
    body: str = ""
