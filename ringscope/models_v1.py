"""
Pydantic v2 data models and request/response specifications for RingScope REST API v1.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Meta & Health
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str = Field("ok", description="Server status indicator")
    version: str = Field("0.4.0", description="API version")
    timestamp: float = Field(..., description="Current server UNIX epoch timestamp")
    uptime_seconds: float = Field(..., description="Server uptime in seconds")
    active_graphs: int = Field(..., description="Number of graphs in memory")
    active_streams: int = Field(..., description="Number of active streaming sessions")
    active_jobs: int = Field(..., description="Number of background analysis/experiment jobs")


# ---------------------------------------------------------------------------
# Graph Models
# ---------------------------------------------------------------------------


class GraphGenerateRequest(BaseModel):
    generator_type: Literal["planted_cluster", "random", "ring"] = Field(
        default="planted_cluster",
        description="Graph generation strategy",
    )
    num_nodes: int = Field(
        default=30,
        ge=2,
        le=5000,
        description="Total number of vertices/accounts (max 5000)",
    )
    cluster_size: int = Field(
        default=8,
        ge=2,
        le=1000,
        description="Planted dense cluster size (used when generator_type='planted_cluster')",
    )
    p_internal: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Internal edge probability within planted cluster",
    )
    p_external: float = Field(
        default=0.05,
        ge=0.0,
        le=1.0,
        description="Background noise / external edge probability",
    )
    seed: Optional[int] = Field(
        default=42,
        description="Deterministic PRNG seed",
    )
    graph_id: Optional[str] = Field(
        default=None,
        description="Custom graph ID. If omitted, a unique ID is generated.",
    )


class GraphImportRequest(BaseModel):
    content: str = Field(
        ...,
        max_length=10_000_000,
        description="Raw edge-list text content in CSV or SNAP format (max 10MB)",
    )
    format: Literal["csv", "snap"] = Field(
        default="csv",
        description="File format parser: 'csv' or 'snap'",
    )
    graph_id: Optional[str] = Field(
        default=None,
        description="Custom graph ID. If omitted, a unique ID is generated.",
    )
    source_col: Optional[str] = Field(
        default=None,
        description="CSV source column header (auto-detected if omitted)",
    )
    target_col: Optional[str] = Field(
        default=None,
        description="CSV target column header (auto-detected if omitted)",
    )
    delimiter: str = Field(
        default=",",
        description="Delimiter character for CSV files",
    )


class DegreeStats(BaseModel):
    min: int
    avg: float
    max: int


class GraphResponse(BaseModel):
    graph_id: str
    num_nodes: int
    num_edges: int
    density: float
    connected_components_count: int
    degree_stats: DegreeStats
    generator_type: str
    planted_cluster: Optional[dict[str, Any]] = None
    created_at: float
    nodes: Optional[list[str]] = None
    edges: Optional[list[tuple[str, str]]] = None


# ---------------------------------------------------------------------------
# Analysis Models
# ---------------------------------------------------------------------------


class AnalysisRunRequest(BaseModel):
    graph_id: str = Field(..., description="ID of graph to analyze")
    analysis_type: Literal["densest_subgraph", "cycle_detection", "both"] = Field(
        default="densest_subgraph",
        description="Type of analysis to execute",
    )
    algorithm: Literal["goldberg", "greedy_peeling", "greedy_plus_plus", "all"] = Field(
        default="goldberg",
        description="Densest subgraph algorithm selection",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional algorithm parameters (e.g., iterations, tolerance, min_ring_length)",
    )
    async_execution: bool = Field(
        default=False,
        description="If True, dispatches computation to background and returns 202 immediately",
    )


class AnalysisJobResponse(BaseModel):
    analysis_id: str
    graph_id: str
    status: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED"]
    analysis_type: str
    algorithm: str
    runtime_ms: Optional[float] = None
    results: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    created_at: float
    completed_at: Optional[float] = None


# ---------------------------------------------------------------------------
# Streaming Models
# ---------------------------------------------------------------------------


class TransactionRecordIn(BaseModel):
    source: str = Field(..., description="Source account identifier")
    target: str = Field(..., description="Target account identifier")
    amount: float = Field(default=100.0, gt=0, description="Transaction amount")
    timestamp: Optional[float] = Field(default=None, description="UNIX timestamp")
    tx_id: Optional[str] = Field(default=None, description="Optional custom transaction ID")


class StreamStartRequest(BaseModel):
    stream_id: Optional[str] = Field(
        default=None,
        description="Custom streaming session ID. Generated if omitted.",
    )
    mode: Literal["full_recomputation", "warm_started_recomputation", "incremental_heuristic"] = (
        Field(
            default="full_recomputation",
            description="Streaming candidate maintenance strategy",
        )
    )
    algorithm: Literal["goldberg", "greedy_peeling", "greedy_plus_plus"] = Field(
        default="greedy_peeling",
        description="Algorithm used for densest candidate computation",
    )
    batch_size: int = Field(
        default=5,
        ge=1,
        le=1000,
        description="Default batch size for stepping",
    )
    initial_graph_id: Optional[str] = Field(
        default=None,
        description="Optional existing graph ID to initialize the stream from",
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Configuration for heuristic mode (recompute_interval, thresholds)",
    )


class StreamSessionResponse(BaseModel):
    stream_id: str
    mode: str
    algorithm: str
    status: str
    current_version: int
    total_transactions: int
    total_unique_edges: int
    recomputations_count: int
    current_candidate_nodes: list[str]
    current_density: float


class StreamStepRequest(BaseModel):
    stream_id: str = Field(..., description="Active stream session identifier")
    transactions: Optional[list[TransactionRecordIn]] = Field(
        default=None,
        description="Explicit transaction records to ingest in this step",
    )
    num_synthetic_batches: int = Field(
        default=1,
        ge=1,
        le=50,
        description="Number of deterministic synthetic batches to ingest if no transactions given",
    )
    include_edges: bool = Field(
        default=False,
        description="If True, returns the generated/ingested (source, target) edge records in the step response",
    )


class StreamStepResponse(BaseModel):
    stream_id: str
    snapshots: list[dict[str, Any]]
    current_candidate_nodes: list[str]
    current_density: float
    total_transactions: int
    total_unique_edges: int
    recomputations_count: int
    new_edges: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="Newly generated or ingested edges with source and target, when include_edges is True",
    )


class StreamInjectRingRequest(BaseModel):
    stream_id: str = Field(..., description="Active stream session identifier")
    ring_size: int = Field(
        default=5,
        ge=3,
        le=50,
        description="Number of vertices in the injected ring",
    )
    ring_nodes: Optional[list[str]] = Field(
        default=None,
        description="Optional custom node names for the injected ring",
    )
    amount: float = Field(
        default=100.0,
        gt=0,
        description="Transaction amount for ring edges",
    )
    complete_clique: bool = Field(
        default=False,
        description="If True, injects an entire clique K_k rather than a simple cycle C_k",
    )
    include_edges: bool = Field(
        default=False,
        description="If True, returns the generated/injected (source, target) edge records in the step response",
    )


class StreamStopRequest(BaseModel):
    stream_id: str = Field(..., description="Stream session to terminate")


class StreamStopResponse(BaseModel):
    stream_id: str
    status: str
    total_batches: int
    total_transactions: int
    total_recomputations: int
    cumulative_latency_ms: float


# ---------------------------------------------------------------------------
# Experiment Models
# ---------------------------------------------------------------------------


class ExperimentRunRequest(BaseModel):
    experiment_name: Literal[
        "exp1_runtime_vs_size",
        "exp2_cluster_size_recovery",
        "exp3_cluster_sparsity",
        "exp4_background_connectivity",
        "exp5_exact_vs_approx",
        "exp6_streaming_modes",
        "exp7_clusters_and_hubs",
        "all",
    ] = Field(..., description="Designated experiment identifier")
    experiment_id: Optional[str] = Field(
        default=None,
        description="Custom experiment run ID",
    )
    seed: int = Field(default=42, description="Random seed for reproducibility")
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Overrides for experiment parameters",
    )
    async_execution: bool = Field(
        default=False,
        description="If True, runs experiment in background and returns 202 immediately",
    )


class ExperimentJobResponse(BaseModel):
    experiment_id: str
    experiment_name: str
    status: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED"]
    created_at: float
    completed_at: Optional[float] = None
    runtime_ms: Optional[float] = None
    output_files: list[str] = Field(default_factory=list)
    error: Optional[str] = None
