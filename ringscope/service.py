"""
ringscope.service — Backend state and workflow execution service.

Manages graphs, analysis jobs, streaming sessions, and experiment runs.
Ensures CPU-bound graph operations and experiment benchmarks are offloaded
from the asyncio event loop using asyncio.to_thread.
"""

from __future__ import annotations

import asyncio
import io
import time
import uuid
from typing import Any, Optional

from ringscope.algorithms.cycle_detection import detect_rings, ring_summary
from ringscope.algorithms.goldberg import goldberg_densest_subgraph
from ringscope.algorithms.greedy_peeling import greedy_peeling
from ringscope.algorithms.greedy_plus_plus import greedy_plus_plus
from ringscope.data import (
    generate_planted_cluster_graph,
    random_graph,
    ring_graph,
)
from ringscope.eval_harness import (
    export_results_to_csv,
    export_results_to_json,
)
from ringscope.experiments import (
    run_exp_background_connectivity,
    run_exp_cluster_size_vs_recovery,
    run_exp_cluster_sparsity_vs_recovery,
    run_exp_exact_vs_approx_density,
    run_exp_multiple_clusters_and_hubs,
    run_exp_runtime_vs_graph_size,
    run_exp_streaming_modes_comparison,
)
from ringscope.graph import TransactionGraph
from ringscope.importer import import_csv_edgelist, import_snap_edgelist
from ringscope.models_v1 import (
    AnalysisJobResponse,
    DegreeStats,
    ExperimentJobResponse,
    GraphResponse,
    StreamSessionResponse,
    StreamStepResponse,
    StreamStopResponse,
    TransactionRecordIn,
)
from ringscope.stream_simulator import (
    FullRecomputationMaintainer,
    IncrementalHeuristicMaintainer,
    StreamBatch,
    TransactionRecord,
    WarmStartedMaintainer,
)


class StreamSession:
    """Manages an active streaming simulation session."""

    def __init__(
        self,
        stream_id: str,
        mode: str,
        algorithm: str,
        batch_size: int,
        initial_graph: Optional[TransactionGraph] = None,
        config: Optional[dict[str, Any]] = None,
    ) -> None:
        self.stream_id = stream_id
        self.mode = mode
        self.algorithm = algorithm
        self.batch_size = batch_size
        self.status = "ACTIVE"
        self.created_at = time.time()
        self.step_counter = 0
        self.total_transactions = 0

        cfg = config or {}
        if mode == "full_recomputation":
            self.maintainer = FullRecomputationMaintainer(algorithm=algorithm)
        elif mode == "warm_started_recomputation":
            self.maintainer = WarmStartedMaintainer(algorithm=algorithm)
        elif mode == "incremental_heuristic":
            self.maintainer = IncrementalHeuristicMaintainer(
                algorithm=algorithm,
                recompute_interval=cfg.get("recompute_interval", 5),
                external_edge_threshold=cfg.get("external_edge_threshold", 10),
                external_degree_ratio=cfg.get(
                    "external_degree_ratio",
                    cfg.get("hub_degree_ratio", 1.5),
                ),
            )
        else:
            raise ValueError(f"Unknown stream mode '{mode}'")

        if initial_graph:
            for u, v in initial_graph.graph.edges():
                self.maintainer.graph.add_transaction(str(u), str(v))

        self.snapshots_history: list[dict[str, Any]] = []

    def to_response(self) -> StreamSessionResponse:
        return StreamSessionResponse(
            stream_id=self.stream_id,
            mode=self.mode,
            algorithm=self.algorithm,
            status=self.status,
            current_version=self.maintainer.version,
            total_transactions=self.total_transactions,
            total_unique_edges=self.maintainer.graph.num_unique_edges,
            recomputations_count=self.maintainer.recomputation_count,
            current_candidate_nodes=sorted(self.maintainer.current_candidate),
            current_density=round(self.maintainer.current_density, 5),
        )

    def process_custom_transactions(self, txs: list[TransactionRecordIn]) -> StreamStepResponse:
        self.step_counter += 1
        self.total_transactions += len(txs)
        records = [
            TransactionRecord(
                src=t.source,
                dst=t.target,
                amount=t.amount,
                timestamp=t.timestamp or time.time(),
                tx_id=t.tx_id or f"tx_{self.stream_id}_{self.step_counter}_{i}",
            )
            for i, t in enumerate(txs)
        ]
        batch = StreamBatch(batch_index=self.step_counter, transactions=records)
        snap = self.maintainer.process_batch(batch)
        snap_dict = snap.to_dict()
        self.snapshots_history.append(snap_dict)

        return StreamStepResponse(
            stream_id=self.stream_id,
            snapshots=[snap_dict],
            current_candidate_nodes=sorted(self.maintainer.current_candidate),
            current_density=round(self.maintainer.current_density, 5),
            total_transactions=self.total_transactions,
            total_unique_edges=self.maintainer.graph.num_unique_edges,
            recomputations_count=self.maintainer.recomputation_count,
        )

    def process_synthetic_batches(self, num_batches: int) -> StreamStepResponse:
        produced_snaps = []
        for _ in range(num_batches):
            self.step_counter += 1
            self.total_transactions += self.batch_size
            # Generate deterministic synthetic transactions
            records = []
            for i in range(self.batch_size):
                u = f"ACC_{(self.step_counter * 3 + i) % 15}"
                v = f"ACC_{(self.step_counter * 5 + i + 1) % 15}"
                if u == v:
                    v = f"ACC_{(self.step_counter * 5 + i + 2) % 15}"
                records.append(
                    TransactionRecord(
                        src=u,
                        dst=v,
                        amount=50.0 + (i * 10.0),
                        timestamp=time.time(),
                        tx_id=f"synth_{self.stream_id}_{self.step_counter}_{i}",
                    )
                )
            batch = StreamBatch(batch_index=self.step_counter, transactions=records)
            snap = self.maintainer.process_batch(batch)
            snap_dict = snap.to_dict()
            self.snapshots_history.append(snap_dict)
            produced_snaps.append(snap_dict)

        return StreamStepResponse(
            stream_id=self.stream_id,
            snapshots=produced_snaps,
            current_candidate_nodes=sorted(self.maintainer.current_candidate),
            current_density=round(self.maintainer.current_density, 5),
            total_transactions=self.total_transactions,
            total_unique_edges=self.maintainer.graph.num_unique_edges,
            recomputations_count=self.maintainer.recomputation_count,
        )

    def inject_ring(
        self,
        ring_size: int = 5,
        ring_nodes: Optional[list[str]] = None,
        amount: float = 100.0,
        complete_clique: bool = False,
    ) -> StreamStepResponse:
        self.step_counter += 1
        nodes = ring_nodes or [f"RING_{self.stream_id[-4:]}_{i}" for i in range(ring_size)]
        records = []
        if complete_clique:
            # Complete clique edges
            k = len(nodes)
            for i in range(k):
                for j in range(i + 1, k):
                    records.append(
                        TransactionRecord(
                            src=nodes[i],
                            dst=nodes[j],
                            amount=amount,
                            timestamp=time.time(),
                            tx_id=f"ring_clique_{self.step_counter}_{i}_{j}",
                        )
                    )
        else:
            # Simple cycle edges
            k = len(nodes)
            for i in range(k):
                u = nodes[i]
                v = nodes[(i + 1) % k]
                records.append(
                    TransactionRecord(
                        src=u,
                        dst=v,
                        amount=amount,
                        timestamp=time.time(),
                        tx_id=f"ring_cycle_{self.step_counter}_{i}",
                    )
                )

        self.total_transactions += len(records)
        batch = StreamBatch(
            batch_index=self.step_counter,
            transactions=records,
        )
        snap = self.maintainer.process_batch(batch)
        snap_dict = snap.to_dict()
        self.snapshots_history.append(snap_dict)

        return StreamStepResponse(
            stream_id=self.stream_id,
            snapshots=[snap_dict],
            current_candidate_nodes=sorted(self.maintainer.current_candidate),
            current_density=round(self.maintainer.current_density, 5),
            total_transactions=self.total_transactions,
            total_unique_edges=self.maintainer.graph.num_unique_edges,
            recomputations_count=self.maintainer.recomputation_count,
        )

    def stop(self) -> StreamStopResponse:
        self.status = "STOPPED"
        cum_lat = sum(s.get("batch_latency_ms", 0.0) for s in self.snapshots_history)
        return StreamStopResponse(
            stream_id=self.stream_id,
            status=self.status,
            total_batches=self.step_counter,
            total_transactions=self.total_transactions,
            total_recomputations=self.maintainer.recomputation_count,
            cumulative_latency_ms=round(cum_lat, 3),
        )


class BackendService:
    """Singleton service maintaining graph, analysis, streaming, and experiment registries."""

    def __init__(self, output_dir: str = "experiments_output") -> None:
        self.start_time = time.time()
        self.output_dir = output_dir

        self.graphs: dict[str, dict[str, Any]] = {}
        self.analysis_jobs: dict[str, dict[str, Any]] = {}
        self.streams: dict[str, StreamSession] = {}
        self.experiment_jobs: dict[str, dict[str, Any]] = {}

    # -----------------------------------------------------------------------
    # Graph Operations
    # -----------------------------------------------------------------------

    def build_graph_response(
        self,
        graph_id: str,
        include_elements: bool = False,
    ) -> GraphResponse:
        entry = self.graphs.get(graph_id)
        if not entry:
            raise KeyError(f"Graph '{graph_id}' not found")

        tg: TransactionGraph = entry["graph"]
        deg_vals = list(tg.degrees().values())
        deg_stats = DegreeStats(
            min=min(deg_vals) if deg_vals else 0,
            avg=round(sum(deg_vals) / max(len(deg_vals), 1), 2),
            max=max(deg_vals) if deg_vals else 0,
        )

        nodes_list = sorted(list(tg.graph.nodes())) if include_elements else None
        edges_list = [(str(u), str(v)) for u, v in tg.graph.edges()] if include_elements else None

        return GraphResponse(
            graph_id=graph_id,
            num_nodes=tg.num_vertices,
            num_edges=tg.num_unique_edges,
            density=round(tg.density(), 5),
            connected_components_count=len(tg.connected_components()),
            degree_stats=deg_stats,
            generator_type=entry.get("generator_type", "custom"),
            planted_cluster=entry.get("planted_cluster"),
            created_at=entry.get("created_at", time.time()),
            nodes=nodes_list,
            edges=edges_list,
        )

    def generate_graph_sync(
        self,
        generator_type: str,
        num_nodes: int,
        cluster_size: int,
        p_internal: float,
        p_external: float,
        seed: Optional[int],
        graph_id: Optional[str] = None,
    ) -> GraphResponse:
        gid = graph_id or f"graph_{uuid.uuid4().hex[:8]}"
        created_at = time.time()
        planted_info = None

        if generator_type == "planted_cluster":
            res = generate_planted_cluster_graph(
                n_total=num_nodes,
                cluster_size=cluster_size,
                p_internal=p_internal,
                p_external=p_external,
                seed=seed or 42,
            )
            tg = res.graph
            cluster_nodes = sorted(list(res.planted_cluster))
            planted_info = {
                "nodes": cluster_nodes,
                "size": len(cluster_nodes),
                "internal_density": round(tg.density(cluster_nodes), 5),
            }
        elif generator_type == "ring":
            tg = ring_graph(ring_sizes=[cluster_size], seed=seed or 42)
        else:  # random
            tg = random_graph(
                n_accounts=num_nodes,
                n_transactions=int(num_nodes * 2),
                seed=seed or 42,
            )

        self.graphs[gid] = {
            "graph": tg,
            "generator_type": generator_type,
            "planted_cluster": planted_info,
            "created_at": created_at,
        }
        return self.build_graph_response(gid)

    async def generate_graph(self, **kwargs: Any) -> GraphResponse:
        return await asyncio.to_thread(self.generate_graph_sync, **kwargs)

    def import_graph_sync(
        self,
        content: str,
        fmt: str,
        graph_id: Optional[str] = None,
        source_col: Optional[str] = None,
        target_col: Optional[str] = None,
        delimiter: str = ",",
    ) -> GraphResponse:
        gid = graph_id or f"graph_import_{uuid.uuid4().hex[:8]}"
        created_at = time.time()

        if fmt == "snap":
            buf = io.StringIO(content)
            snap_delim = delimiter if delimiter != "," else None
            tg = import_snap_edgelist(buf, delimiter=snap_delim)
        else:
            buf = io.StringIO(content)
            # Auto-detect common column headers if not supplied
            first_line = content.strip().split("\n")[0]
            header_tokens = [t.strip().lower() for t in first_line.split(delimiter)]
            eff_source = source_col
            if not eff_source:
                for candidate in ["source", "src", "from", "u", "from_account"]:
                    if candidate in header_tokens:
                        eff_source = candidate
                        break
            eff_target = target_col
            if not eff_target:
                for candidate in ["target", "dst", "to", "v", "to_account"]:
                    if candidate in header_tokens:
                        eff_target = candidate
                        break

            kwargs: dict[str, Any] = {}
            if eff_source:
                kwargs["source_col"] = eff_source
            if eff_target:
                kwargs["target_col"] = eff_target
            tg = import_csv_edgelist(
                buf,
                delimiter=delimiter,
                **kwargs,
            )

        self.graphs[gid] = {
            "graph": tg,
            "generator_type": f"import_{fmt}",
            "planted_cluster": None,
            "created_at": created_at,
        }
        return self.build_graph_response(gid)

    async def import_graph(self, **kwargs: Any) -> GraphResponse:
        return await asyncio.to_thread(self.import_graph_sync, **kwargs)

    # -----------------------------------------------------------------------
    # Analysis Operations
    # -----------------------------------------------------------------------

    def execute_analysis_sync(
        self,
        analysis_id: str,
        graph_id: str,
        analysis_type: str,
        algorithm: str,
        params: dict[str, Any],
    ) -> None:
        job = self.analysis_jobs.get(analysis_id)
        if not job:
            return

        job["status"] = "RUNNING"
        t0 = time.perf_counter()

        try:
            entry = self.graphs.get(graph_id)
            if not entry:
                raise KeyError(f"Graph '{graph_id}' does not exist")

            tg: TransactionGraph = entry["graph"]
            results: dict[str, Any] = {}

            # Densest subgraph
            if analysis_type in ("densest_subgraph", "both"):
                densest_res: dict[str, Any] = {}
                if algorithm == "all":
                    t_g = time.perf_counter()
                    gold = goldberg_densest_subgraph(tg)
                    densest_res["goldberg"] = {
                        **gold.to_dict(),
                        "time_ms": round((time.perf_counter() - t_g) * 1000, 3),
                    }

                    t_p = time.perf_counter()
                    peel = greedy_peeling(tg)
                    densest_res["greedy_peeling"] = {
                        **peel.to_dict(),
                        "time_ms": round((time.perf_counter() - t_p) * 1000, 3),
                    }

                    t_pp = time.perf_counter()
                    gpp = greedy_plus_plus(
                        tg,
                        iterations=params.get("iterations", 10),
                    )
                    densest_res["greedy_plus_plus"] = {
                        **gpp.to_dict(),
                        "time_ms": round((time.perf_counter() - t_pp) * 1000, 3),
                    }
                elif algorithm == "goldberg":
                    res = goldberg_densest_subgraph(
                        tg,
                        tolerance=params.get("tolerance", 1e-4),
                    )
                    densest_res["goldberg"] = {
                        **res.to_dict(),
                        "time_ms": round(res.runtime_sec * 1000, 3),
                    }
                elif algorithm == "greedy_peeling":
                    res = greedy_peeling(tg)
                    densest_res["greedy_peeling"] = {
                        **res.to_dict(),
                        "time_ms": round(res.runtime_sec * 1000, 3),
                    }
                elif algorithm == "greedy_plus_plus":
                    res = greedy_plus_plus(
                        tg,
                        iterations=params.get("iterations", 10),
                    )
                    densest_res["greedy_plus_plus"] = {
                        **res.to_dict(),
                        "time_ms": round(res.runtime_sec * 1000, 3),
                    }
                results["densest_subgraph"] = densest_res

            # Cycle detection
            if analysis_type in ("cycle_detection", "both"):
                rings = detect_rings(
                    tg.graph,
                    min_length=params.get("min_ring_length", 3),
                    max_length=params.get("max_ring_length"),
                    max_rings=params.get("max_rings", 50),
                )
                results["cycle_detection"] = {
                    "rings": [r.to_dict() for r in rings],
                    "summary": ring_summary(rings),
                }

            elapsed_ms = (time.perf_counter() - t0) * 1000
            job["status"] = "COMPLETED"
            job["runtime_ms"] = round(elapsed_ms, 3)
            job["results"] = results
            job["completed_at"] = time.time()

        except Exception as exc:
            job["status"] = "FAILED"
            job["error"] = str(exc)
            job["completed_at"] = time.time()

    async def run_analysis(
        self,
        graph_id: str,
        analysis_type: str,
        algorithm: str,
        params: dict[str, Any],
        async_execution: bool = False,
    ) -> AnalysisJobResponse:
        if graph_id not in self.graphs:
            raise KeyError(f"Graph '{graph_id}' does not exist")

        aid = f"analysis_{uuid.uuid4().hex[:8]}"
        now = time.time()
        job = {
            "analysis_id": aid,
            "graph_id": graph_id,
            "status": "PENDING",
            "analysis_type": analysis_type,
            "algorithm": algorithm,
            "runtime_ms": None,
            "results": None,
            "error": None,
            "created_at": now,
            "completed_at": None,
        }
        self.analysis_jobs[aid] = job

        if async_execution:
            asyncio.create_task(
                asyncio.to_thread(
                    self.execute_analysis_sync,
                    aid,
                    graph_id,
                    analysis_type,
                    algorithm,
                    params,
                )
            )
            return AnalysisJobResponse(**job)

        # Synchronous execution off the event loop
        await asyncio.to_thread(
            self.execute_analysis_sync,
            aid,
            graph_id,
            analysis_type,
            algorithm,
            params,
        )
        return AnalysisJobResponse(**self.analysis_jobs[aid])

    def get_analysis_job(self, analysis_id: str) -> AnalysisJobResponse:
        job = self.analysis_jobs.get(analysis_id)
        if not job:
            raise KeyError(f"Analysis '{analysis_id}' not found")
        return AnalysisJobResponse(**job)

    # -----------------------------------------------------------------------
    # Streaming Operations
    # -----------------------------------------------------------------------

    def start_stream(
        self,
        stream_id: Optional[str],
        mode: str,
        algorithm: str,
        batch_size: int,
        initial_graph_id: Optional[str],
        config: dict[str, Any],
    ) -> StreamSessionResponse:
        sid = stream_id or f"stream_{uuid.uuid4().hex[:8]}"
        initial_tg = None
        if initial_graph_id:
            g_entry = self.graphs.get(initial_graph_id)
            if not g_entry:
                raise KeyError(f"Initial graph '{initial_graph_id}' not found")
            initial_tg = g_entry["graph"]

        session = StreamSession(
            stream_id=sid,
            mode=mode,
            algorithm=algorithm,
            batch_size=batch_size,
            initial_graph=initial_tg,
            config=config,
        )
        self.streams[sid] = session
        return session.to_response()

    async def step_stream(
        self,
        stream_id: str,
        transactions: Optional[list[TransactionRecordIn]],
        num_synthetic_batches: int,
    ) -> StreamStepResponse:
        session = self.streams.get(stream_id)
        if not session:
            raise KeyError(f"Stream '{stream_id}' not found")
        if session.status != "ACTIVE":
            raise ValueError(f"Stream '{stream_id}' is not active ({session.status})")

        if transactions:
            return await asyncio.to_thread(session.process_custom_transactions, transactions)
        return await asyncio.to_thread(session.process_synthetic_batches, num_synthetic_batches)

    async def inject_ring_stream(
        self,
        stream_id: str,
        ring_size: int,
        ring_nodes: Optional[list[str]],
        amount: float,
        complete_clique: bool,
    ) -> StreamStepResponse:
        session = self.streams.get(stream_id)
        if not session:
            raise KeyError(f"Stream '{stream_id}' not found")
        if session.status != "ACTIVE":
            raise ValueError(f"Stream '{stream_id}' is not active ({session.status})")

        return await asyncio.to_thread(
            session.inject_ring,
            ring_size,
            ring_nodes,
            amount,
            complete_clique,
        )

    def stop_stream(self, stream_id: str) -> StreamStopResponse:
        session = self.streams.get(stream_id)
        if not session:
            raise KeyError(f"Stream '{stream_id}' not found")
        return session.stop()

    # -----------------------------------------------------------------------
    # Experiment Operations
    # -----------------------------------------------------------------------

    def execute_experiment_sync(
        self,
        experiment_id: str,
        experiment_name: str,
        seed: int,
        params: dict[str, Any],
    ) -> None:
        job = self.experiment_jobs.get(experiment_id)
        if not job:
            return

        job["status"] = "RUNNING"
        t0 = time.perf_counter()

        try:
            import os

            os.makedirs(self.output_dir, exist_ok=True)

            results_list: list[dict[str, Any]] = []
            files_created: list[str] = []

            if experiment_name == "exp1_runtime_vs_size":
                results_list = run_exp_runtime_vs_graph_size(
                    sizes=params.get("sizes", [10, 20]),
                    seed=seed,
                )
            elif experiment_name == "exp2_cluster_size_recovery":
                results_list = run_exp_cluster_size_vs_recovery(
                    n=params.get("n", 20),
                    cluster_sizes=params.get("cluster_sizes", [3, 5]),
                    seed=seed,
                )
            elif experiment_name == "exp3_cluster_sparsity":
                results_list = run_exp_cluster_sparsity_vs_recovery(
                    n=params.get("n", 20),
                    p_in_values=params.get("p_in_values", [0.4, 0.8]),
                    seed=seed,
                )
            elif experiment_name == "exp4_background_connectivity":
                results_list = run_exp_background_connectivity(
                    n=params.get("n", 20),
                    p_out_values=params.get("p_out_values", [0.02, 0.1]),
                    seed=seed,
                )
            elif experiment_name == "exp5_exact_vs_approx":
                results_list = run_exp_exact_vs_approx_density(
                    sizes=params.get("sizes", [8, 12]),
                    seed=seed,
                )
            elif experiment_name == "exp6_streaming_modes":
                results_list = run_exp_streaming_modes_comparison(
                    n=params.get("n", 20),
                    num_batches=params.get("num_batches", 6),
                    batch_size=params.get("batch_size", 3),
                    seed=seed,
                )
            elif experiment_name == "exp7_clusters_and_hubs":
                results_list = run_exp_multiple_clusters_and_hubs(
                    n=params.get("n", 25),
                    seed=seed,
                )
            elif experiment_name == "all":
                # Run concise composite
                results_list = run_exp_streaming_modes_comparison(
                    n=15, num_batches=4, batch_size=2, seed=seed
                )

            # Persist to disk
            json_path = os.path.join(self.output_dir, f"{experiment_id}.json")
            csv_path = os.path.join(self.output_dir, f"{experiment_id}.csv")
            export_results_to_json(results_list, json_path)
            export_results_to_csv(results_list, csv_path)
            files_created.extend([json_path, csv_path])

            elapsed_ms = (time.perf_counter() - t0) * 1000
            job["status"] = "COMPLETED"
            job["runtime_ms"] = round(elapsed_ms, 3)
            job["results_data"] = results_list
            job["output_files"] = files_created
            job["completed_at"] = time.time()

        except Exception as exc:
            job["status"] = "FAILED"
            job["error"] = str(exc)
            job["completed_at"] = time.time()

    async def run_experiment(
        self,
        experiment_name: str,
        seed: int,
        params: dict[str, Any],
        experiment_id: Optional[str] = None,
        async_execution: bool = False,
    ) -> ExperimentJobResponse:
        eid = experiment_id or f"exp_{experiment_name}_{uuid.uuid4().hex[:6]}"
        now = time.time()
        job = {
            "experiment_id": eid,
            "experiment_name": experiment_name,
            "status": "PENDING",
            "created_at": now,
            "completed_at": None,
            "runtime_ms": None,
            "output_files": [],
            "results_data": None,
            "error": None,
        }
        self.experiment_jobs[eid] = job

        if async_execution:
            asyncio.create_task(
                asyncio.to_thread(
                    self.execute_experiment_sync,
                    eid,
                    experiment_name,
                    seed,
                    params,
                )
            )
            return ExperimentJobResponse(**job)

        await asyncio.to_thread(
            self.execute_experiment_sync,
            eid,
            experiment_name,
            seed,
            params,
        )
        return ExperimentJobResponse(**self.experiment_jobs[eid])

    def get_experiment_job(self, experiment_id: str) -> ExperimentJobResponse:
        job = self.experiment_jobs.get(experiment_id)
        if not job:
            raise KeyError(f"Experiment '{experiment_id}' not found")
        return ExperimentJobResponse(**job)

    def get_experiment_results(self, experiment_id: str) -> list[dict[str, Any]]:
        job = self.experiment_jobs.get(experiment_id)
        if not job:
            raise KeyError(f"Experiment '{experiment_id}' not found")
        if job["status"] == "PENDING" or job["status"] == "RUNNING":
            raise RuntimeError(f"Experiment '{experiment_id}' is still in progress")
        if job["status"] == "FAILED":
            raise RuntimeError(f"Experiment failed: {job.get('error')}")
        return job.get("results_data") or []


# Global singleton instance
backend_service = BackendService()
