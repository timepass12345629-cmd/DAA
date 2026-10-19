"""
ringscope.api_v1 — REST API v1 endpoints for RingScope.

Exposes graph generation/import, densest subgraph and cycle detection analyses,
deterministic streaming simulator sessions, and reproducible experiment runners.
"""

from __future__ import annotations

import os
import time
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse, Response

from ringscope.models_v1 import (
    AnalysisJobResponse,
    AnalysisRunRequest,
    ExperimentJobResponse,
    ExperimentRunRequest,
    GraphGenerateRequest,
    GraphImportRequest,
    GraphResponse,
    HealthResponse,
    StreamInjectRingRequest,
    StreamSessionResponse,
    StreamStartRequest,
    StreamStepRequest,
    StreamStepResponse,
    StreamStopRequest,
    StreamStopResponse,
)
from ringscope.service import backend_service

router = APIRouter(prefix="", tags=["API v1"])


# ---------------------------------------------------------------------------
# Meta & Health
# ---------------------------------------------------------------------------


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System health and operational metrics probe",
)
def get_health() -> HealthResponse:
    now = time.time()
    return HealthResponse(
        status="ok",
        version="0.4.0",
        timestamp=now,
        uptime_seconds=round(now - backend_service.start_time, 2),
        active_graphs=len(backend_service.graphs),
        active_streams=len(backend_service.streams),
        active_jobs=len(backend_service.analysis_jobs) + len(backend_service.experiment_jobs),
    )


# ---------------------------------------------------------------------------
# Graph Management
# ---------------------------------------------------------------------------


@router.post(
    "/graphs/generate",
    response_model=GraphResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a synthetic transaction graph",
)
async def generate_graph(req: GraphGenerateRequest) -> GraphResponse:
    try:
        return await backend_service.generate_graph(
            generator_type=req.generator_type,
            num_nodes=req.num_nodes,
            cluster_size=req.cluster_size,
            p_internal=req.p_internal,
            p_external=req.p_external,
            seed=req.seed,
            graph_id=req.graph_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to generate graph: {exc}",
        )


@router.post(
    "/graphs/import",
    response_model=GraphResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import an edge-list graph from CSV or SNAP format",
)
async def import_graph(req: GraphImportRequest) -> GraphResponse:
    if not req.content or not req.content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Import payload 'content' cannot be empty",
        )
    try:
        return await backend_service.import_graph(
            content=req.content,
            fmt=req.format,
            graph_id=req.graph_id,
            source_col=req.source_col,
            target_col=req.target_col,
            delimiter=req.delimiter,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to import graph: {exc}",
        )


@router.get(
    "/graphs/{graph_id}",
    response_model=GraphResponse,
    summary="Retrieve graph topology, metrics, and summary statistics",
)
def get_graph(
    graph_id: str,
    include_elements: bool = Query(
        default=False,
        description="Include full lists of vertices and edges",
    ),
) -> GraphResponse:
    try:
        return backend_service.build_graph_response(
            graph_id,
            include_elements=include_elements,
        )
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Graph '{graph_id}' not found",
        )


# ---------------------------------------------------------------------------
# Analysis & Algorithms
# ---------------------------------------------------------------------------


@router.post(
    "/analysis/run",
    response_model=AnalysisJobResponse,
    summary="Execute densest subgraph or cycle detection analysis on a graph",
)
async def run_analysis(
    req: AnalysisRunRequest,
    response: Response,
) -> AnalysisJobResponse:
    try:
        res = await backend_service.run_analysis(
            graph_id=req.graph_id,
            analysis_type=req.analysis_type,
            algorithm=req.algorithm,
            params=req.params,
            async_execution=req.async_execution,
        )
        if req.async_execution:
            response.status_code = status.HTTP_202_ACCEPTED
        else:
            response.status_code = status.HTTP_200_OK
        return res
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/analysis/{analysis_id}",
    response_model=AnalysisJobResponse,
    summary="Retrieve status and results of an analysis job",
)
def get_analysis(analysis_id: str) -> AnalysisJobResponse:
    try:
        return backend_service.get_analysis_job(analysis_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis '{analysis_id}' not found",
        )


# ---------------------------------------------------------------------------
# Streaming Simulation & Candidate Maintenance
# ---------------------------------------------------------------------------


@router.post(
    "/stream/start",
    response_model=StreamSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new transaction stream maintenance session",
)
def start_stream(req: StreamStartRequest) -> StreamSessionResponse:
    try:
        return backend_service.start_stream(
            stream_id=req.stream_id,
            mode=req.mode,
            algorithm=req.algorithm,
            batch_size=req.batch_size,
            initial_graph_id=req.initial_graph_id,
            config=req.config,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/stream/step",
    response_model=StreamStepResponse,
    summary="Advance streaming session by ingesting transactions or synthetic batches",
)
async def step_stream(req: StreamStepRequest) -> StreamStepResponse:
    try:
        return await backend_service.step_stream(
            stream_id=req.stream_id,
            transactions=req.transactions,
            num_synthetic_batches=req.num_synthetic_batches,
            include_edges=req.include_edges,
        )
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stream '{req.stream_id}' not found",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/stream/inject-ring",
    response_model=StreamStepResponse,
    summary="Inject a dense cycle or clique into an active stream session",
)
async def inject_ring(req: StreamInjectRingRequest) -> StreamStepResponse:
    try:
        return await backend_service.inject_ring_stream(
            stream_id=req.stream_id,
            ring_size=req.ring_size,
            ring_nodes=req.ring_nodes,
            amount=req.amount,
            complete_clique=req.complete_clique,
            include_edges=req.include_edges,
        )
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stream '{req.stream_id}' not found",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/stream/stop",
    response_model=StreamStopResponse,
    summary="Terminate an active streaming session and report cumulative metrics",
)
def stop_stream(req: StreamStopRequest) -> StreamStopResponse:
    try:
        return backend_service.stop_stream(req.stream_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stream '{req.stream_id}' not found",
        )


# ---------------------------------------------------------------------------
# Experiments & Benchmark Harness
# ---------------------------------------------------------------------------


@router.post(
    "/experiments/run",
    response_model=ExperimentJobResponse,
    summary="Execute a benchmark experiment from the reproducible test harness",
)
async def run_experiment(
    req: ExperimentRunRequest,
    response: Response,
) -> ExperimentJobResponse:
    try:
        res = await backend_service.run_experiment(
            experiment_name=req.experiment_name,
            seed=req.seed,
            params=req.params,
            experiment_id=req.experiment_id,
            async_execution=req.async_execution,
        )
        if req.async_execution:
            response.status_code = status.HTTP_202_ACCEPTED
        else:
            response.status_code = status.HTTP_200_OK
        return res
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to execute experiment: {exc}",
        )


@router.get(
    "/experiments/{experiment_id}",
    response_model=ExperimentJobResponse,
    summary="Check status and execution details of an experiment",
)
def get_experiment(experiment_id: str) -> ExperimentJobResponse:
    try:
        return backend_service.get_experiment_job(experiment_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment '{experiment_id}' not found",
        )


@router.get(
    "/experiments/{experiment_id}/results",
    summary="Retrieve computed benchmark results for a completed experiment",
)
def get_experiment_results(experiment_id: str) -> list[dict[str, Any]]:
    try:
        return backend_service.get_experiment_results(experiment_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment '{experiment_id}' not found",
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.get(
    "/experiments/{experiment_id}/export",
    summary="Export experiment benchmark results as downloadable JSON or CSV",
)
def export_experiment_results(
    experiment_id: str,
    format: Literal["json", "csv"] = Query(
        default="json",
        description="Export format: 'json' or 'csv'",
    ),
) -> FileResponse:
    try:
        job = backend_service.get_experiment_job(experiment_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment '{experiment_id}' not found",
        )

    file_ext = f".{format}"
    target_file = None
    for f in job.output_files:
        if f.endswith(file_ext):
            target_file = f
            break

    if not target_file:
        target_file = os.path.join(backend_service.output_dir, f"{experiment_id}{file_ext}")

    if not os.path.exists(target_file):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export file '{target_file}' not found",
        )

    media_type = "application/json" if format == "json" else "text/csv"
    return FileResponse(
        path=target_file,
        media_type=media_type,
        filename=f"{experiment_id}{file_ext}",
    )
