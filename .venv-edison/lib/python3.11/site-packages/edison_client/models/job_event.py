"""Job event models for cost and usage tracking."""

from datetime import datetime
from enum import StrEnum, auto
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ExecutionType(StrEnum):
    """Type of execution for job events."""

    TRAJECTORY = auto()
    SESSION = auto()


class CostComponent(StrEnum):
    """Cost component types for job events."""

    LLM_USAGE = auto()
    EXTERNAL_SERVICE = auto()
    STEP = auto()


class JobEventCreateRequest(BaseModel):
    """Request model for creating a job event matching crow-service schema."""

    execution_id: UUID = Field(description="UUID for trajectory_id or session_id")
    execution_type: ExecutionType = Field()
    cost_component: CostComponent = Field()
    started_at: datetime | None = Field(
        default=None, description="Start time of the job event"
    )
    ended_at: datetime | None = Field(
        default=None, description="End time of the job event"
    )
    amount_acu: float | None = Field(default=None, description="Cost amount in ACUs")
    amount_usd: float | None = Field(default=None, description="Cost amount in USD")
    rate: float | None = Field(default=None, description="Rate per token/call in USD")
    input_token_count: int | None = Field(
        default=None, description="Input token count for LLM calls"
    )
    completion_token_count: int | None = Field(
        default=None, description="Completion token count for LLM calls"
    )
    metadata: dict[str, Any] | None = Field(default=None)


class JobEventUpdateRequest(BaseModel):
    """Request model for updating a job event matching crow-service schema."""

    amount_acu: float | None = Field(
        default=None, description="Cost amount in ACU (Agent Compute Unit)"
    )
    amount_usd: float | None = Field(default=None, description="Cost amount in USD")
    rate: float | None = Field(default=None, description="Rate per token/call in USD")
    input_token_count: int | None = Field(
        default=None, description="Input token count for LLM calls"
    )
    completion_token_count: int | None = Field(
        default=None, description="Completion token count for LLM calls"
    )
    metadata: dict[str, Any] | None = Field(default=None)
    started_at: datetime | None = Field(
        default=None, description="Start time of the job event"
    )
    ended_at: datetime | None = Field(
        default=None, description="End time of the job event"
    )


class JobEventCreateResponse(BaseModel):
    """Response model for job event creation."""

    id: UUID = Field(description="UUID of the created job event")


class JobEventBatchItemRequest(BaseModel):
    """Individual job event data for batch creation (without execution context)."""

    cost_component: CostComponent = Field()
    started_at: datetime | None = Field(
        default=None, description="Start time of the cost period"
    )
    ended_at: datetime | None = Field(
        default=None, description="End time of the cost period"
    )
    amount_acu: float | None = Field(
        default=None, description="Cost amount in ACU (Agent Compute Unit)"
    )
    amount_usd: float | None = Field(default=None, description="Cost amount in USD")
    rate: float | None = Field(default=None, description="Rate per token/call in USD")
    input_token_count: int | None = Field(
        default=None, description="Input token count for LLM calls"
    )
    completion_token_count: int | None = Field(
        default=None, description="Completion token count for LLM calls"
    )
    metadata: dict[str, Any] | None = Field(default=None)
    idempotency_key: str | None = Field(
        default=None, description="Idempotency key to prevent duplicate events"
    )


class JobEventBatchCreateRequest(BaseModel):
    """Request model for creating multiple job events in a single batch operation."""

    execution_id: UUID = Field(description="UUID for trajectory_id or session_id")
    execution_type: ExecutionType = Field()
    job_events: list[JobEventBatchItemRequest] = Field(
        description="List of job events to create for this execution",
        min_length=1,
        max_length=100,  # Reasonable limit to prevent abuse
    )


class JobEventBatchCreateResponse(BaseModel):
    """Response model for batch job event creation."""

    ids: list[UUID] = Field(description="List of UUIDs of the created job events")
    created_count: int = Field(description="Number of job events successfully created")
