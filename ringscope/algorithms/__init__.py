"""
ringscope.algorithms — Cycle detection, max flow, and densest-subgraph algorithms.

Algorithms:
-----------
1. dinic.py             — Dinic's maximum flow & minimum cut algorithm
2. goldberg.py          — Goldberg exact flow-based densest subgraph & threshold decision
3. greedy_peeling.py    — Charikar greedy minimum-degree peeling (2-approximation)
4. greedy_plus_plus.py  — Greedy++ iterative load-weighted peeling framework
5. brute_force.py       — Small-instance (N <= 20) exact densest subgraph reference oracle
6. cycle_detection.py   — Johnson (1975) elementary cycle detection
7. densest_subgraph.py  — Unified dispatcher and legacy wrappers
8. streaming.py         — Sliding-window incremental ring cache
"""

from ringscope.algorithms.brute_force import (
    MAX_BRUTE_FORCE_NODES,
    BruteForceResult,
    brute_force_densest_subgraph,
)
from ringscope.algorithms.cycle_detection import (
    Ring,
    detect_rings,
    ring_summary,
)
from ringscope.algorithms.densest_subgraph import (
    DenseSubgraph,
    densest_subgraph,
    exact_goldberg,
    greedy_charikar,
)
from ringscope.algorithms.dinic import Dinic, FlowEdge
from ringscope.algorithms.goldberg import (
    GoldbergDecisionResult,
    GoldbergDensestResult,
    goldberg_decision_threshold,
    goldberg_densest_subgraph,
)
from ringscope.algorithms.greedy_peeling import (
    GreedyPeelingResult,
    PeelingStep,
    greedy_peeling,
)
from ringscope.algorithms.greedy_plus_plus import (
    GreedyPlusPlusResult,
    greedy_plus_plus,
)
from ringscope.algorithms.streaming import (
    StreamEdge,
    StreamingRingDetector,
    WindowSnapshot,
)

__all__ = [
    "Dinic",
    "FlowEdge",
    "goldberg_decision_threshold",
    "goldberg_densest_subgraph",
    "GoldbergDecisionResult",
    "GoldbergDensestResult",
    "greedy_peeling",
    "PeelingStep",
    "GreedyPeelingResult",
    "greedy_plus_plus",
    "GreedyPlusPlusResult",
    "brute_force_densest_subgraph",
    "BruteForceResult",
    "MAX_BRUTE_FORCE_NODES",
    "detect_rings",
    "Ring",
    "ring_summary",
    "densest_subgraph",
    "greedy_charikar",
    "exact_goldberg",
    "DenseSubgraph",
    "StreamingRingDetector",
    "StreamEdge",
    "WindowSnapshot",
]
