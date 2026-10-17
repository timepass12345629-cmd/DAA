# 09 — Open Issues, Technical Risks, and Next Steps

**Project:** RingScope  
**Document:** Prioritized Risk Matrix, Open Defects, and Recommended Action Plan  
**Verification Level:** `SOURCE-VERIFIED` / `TEST-VERIFIED`  

---

## 1. Prioritized Technical Issues and Risks

| Issue ID | Severity | Category | Description | Source / Evidence | Recommended Action |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **ISS-01** | **Medium** | Repository State | Uncommitted Phase 7 working tree changes on `main` branch (19 modified, 7 untracked files). | `SOURCE-VERIFIED` `git status` | Create a clean, well-documented Git commit encapsulating Phase 7 audit repairs and handover documents. |
| **ISS-02** | **Medium** | Architecture | In-memory `BackendService` state (`_graphs`, `_streaming_sessions`) lacks an eviction/paging policy, leading to memory growth under sustained multi-tenant usage. | `SOURCE-VERIFIED` [ringscope/service.py#L38-L55](file:///c:/VS%20code/DAA/ringscope/service.py#L38-L55) | Implement LRU eviction or load graphs on-demand from SQLite `GraphStore`. |
| **ISS-03** | **Low** | Theory / Docs | Greedy++ $T=10$ default iteration count lacks a formal worst-case $(1-\epsilon)$ guarantee for arbitrary $\epsilon$ without graph-dependent iteration scaling. | `SOURCE-VERIFIED` [ringscope/algorithms/greedy_plus_plus.py#L42-L55](file:///c:/VS%20code/DAA/ringscope/algorithms/greedy_plus_plus.py#L42-L55) | Expose dynamic $T = \lceil \frac{\Delta}{\lambda^*} \frac{\log n}{\epsilon^2} \rceil$ calculation as an optional flag for rigorous theoretical benchmarking. |
| **ISS-04** | **Low** | Testing | Absence of automated end-to-end browser tests (e.g., Playwright/Cypress) for Cytoscape.js rendering and interactive node selection. | `UNVERIFIED` `frontend/` directory inspection | Add a lightweight Playwright suite verifying Canvas mounting and node click interactions. |
| **ISS-05** | **Low** | Data Model | Stream simulator and maintainers only support edge insertions; edge expirations (sliding time windows) are not currently supported. | `SOURCE-VERIFIED` [ringscope/streaming.py#L50-L120](file:///c:/VS%20code/DAA/ringscope/streaming.py#L50-L120) | Extend `TransactionGraph` and maintainers with edge deletion / sliding-window timestamp eviction. |

---

## 2. Immediate Best Next Action for the Project

The single best next engineering action for the project is:

> **Execute a structured, clean review commit on the `main` branch to record the Phase 7 audit repairs, reproduced benchmark outputs, and the complete `docs/handover/` dossier.**

### Rationale:
The repository is currently in a fully verified, 100% passing state (168 backend tests passing, 3 frontend tests passing, zero lint violations, clean Vite build, and validated benchmark reproductions). However, because these changes exist solely as an uncommitted working tree over commit `4c42b05`, any accidental reset or branch switch would lose the audit fixes. Recording a signed review commit preserves full reproducibility for the independent reviewer.
