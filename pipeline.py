"""LangGraph orchestration: load -> schema_validate <-> fixer -> date_normalize -> security_gate -> END."""

from pathlib import Path
from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph

from config import DEFAULT_INPUT_PATH, FIXER_MAX_ITERATIONS, REFERENCE_DATE
from gates.date_normalization import run_date_normalization
from gates.fixer_agent import run_fixer_agent
from gates.schema_validation import run_schema_validation
from gates.security_gate import run_security_gate
from schema import normalize_patient_name


class PipelineState(TypedDict, total=False):
    input_path: str | Path
    raw_records: list[dict[str, Any]]
    to_validate: list[dict[str, Any]]
    valid_records: list[dict[str, Any]]
    needs_healing: list[dict[str, Any]]
    quarantined_from_healing: list[dict[str, Any]]
    date_normalized: list[dict[str, Any]]
    cleaned_records: list[dict[str, Any]]
    quarantined: list[dict[str, Any]]
    fixer_iterations: int


def load_node(state: PipelineState) -> PipelineState:
    """Load raw records from path. Path is passed in state as input_path or use default."""
    path = state.get("input_path") or DEFAULT_INPUT_PATH
    if isinstance(path, str):
        path = Path(path)
    import json
    with open(path, "r") as f:
        data = json.load(f)
    if not isinstance(data, list):
        data = [data]
    return {
        "raw_records": data,
        "to_validate": data,
        "valid_records": [],
        "quarantined_from_healing": [],
        "fixer_iterations": 0,
    }


def schema_validate_node(state: PipelineState) -> PipelineState:
    """Gate 01: split to_validate into valid_records (append) and needs_healing."""
    to_validate = state.get("to_validate") or []
    valid_records = list(state.get("valid_records") or [])
    valid_batch, needs_healing = run_schema_validation(to_validate)
    valid_records.extend(valid_batch)
    return {
        "valid_records": valid_records,
        "needs_healing": needs_healing,
    }


def route_after_schema(
    state: PipelineState,
) -> Literal["security_on_healing", "quarantine_remaining", "date_normalize"]:
    """Route: if needs_healing and under max iter -> security_on_healing; elif needs_healing -> quarantine_remaining; else date_normalize."""
    needs_healing = state.get("needs_healing") or []
    iterations = state.get("fixer_iterations") or 0
    if needs_healing and iterations < FIXER_MAX_ITERATIONS:
        return "security_on_healing"
    if needs_healing:
        return "quarantine_remaining"
    return "date_normalize"


def security_on_healing_node(state: PipelineState) -> PipelineState:
    """Run Security Gate on needs_healing; quarantine malicious, keep only non-malicious for Fixer."""
    needs_healing = state.get("needs_healing") or []
    quarantined_from_healing = list(state.get("quarantined_from_healing") or [])
    clean_for_fixer, malicious = run_security_gate(needs_healing)
    quarantined_from_healing.extend(malicious)
    return {
        "needs_healing": clean_for_fixer,
        "quarantined_from_healing": quarantined_from_healing,
    }


def fixer_node(state: PipelineState) -> PipelineState:
    """Gate 04: run Fixer on needs_healing; set to_validate to repaired for next schema pass."""
    needs_healing = state.get("needs_healing") or []
    repaired = run_fixer_agent(needs_healing)
    iterations = (state.get("fixer_iterations") or 0) + 1
    return {
        "to_validate": repaired,
        "fixer_iterations": iterations,
    }


def quarantine_remaining_node(state: PipelineState) -> PipelineState:
    """Add records still in needs_healing (after max Fixer iterations) to quarantined_from_healing with failed_healing."""
    needs_healing = state.get("needs_healing") or []
    quarantined_from_healing = list(state.get("quarantined_from_healing") or [])
    for rec in needs_healing:
        rec_copy = dict(rec) if isinstance(rec, dict) else {"_raw": rec}
        rec_copy["quarantine_reason"] = ["failed_healing"]
        quarantined_from_healing.append(rec_copy)
    return {
        "quarantined_from_healing": quarantined_from_healing,
        "needs_healing": [],
    }


def date_normalize_node(state: PipelineState) -> PipelineState:
    """Gate 02: normalize dates on valid_records."""
    valid_records = state.get("valid_records") or []
    normalized = run_date_normalization(valid_records, REFERENCE_DATE)
    return {"date_normalized": normalized}


def security_gate_node(state: PipelineState) -> PipelineState:
    """Gate 03: split date_normalized into cleaned and quarantined. Normalize patient_name to title case."""
    date_normalized = state.get("date_normalized") or []
    cleaned, quarantined = run_security_gate(date_normalized)
    cleaned = [
        {**rec, "patient_name": normalize_patient_name(rec.get("patient_name")) or rec.get("patient_name")}
        if isinstance(rec, dict) and "patient_name" in rec
        else rec
        for rec in cleaned
    ]
    return {
        "cleaned_records": cleaned,
        "quarantined": quarantined,
    }


def build_graph() -> StateGraph:
    workflow = StateGraph(PipelineState)
    workflow.add_node("load", load_node)
    workflow.add_node("schema_validate", schema_validate_node)
    workflow.add_node("security_on_healing", security_on_healing_node)
    workflow.add_node("fixer", fixer_node)
    workflow.add_node("quarantine_remaining", quarantine_remaining_node)
    workflow.add_node("date_normalize", date_normalize_node)
    workflow.add_node("security_gate", security_gate_node)

    workflow.set_entry_point("load")
    workflow.add_edge("load", "schema_validate")
    workflow.add_conditional_edges(
        "schema_validate",
        route_after_schema,
        {
            "security_on_healing": "security_on_healing",
            "quarantine_remaining": "quarantine_remaining",
            "date_normalize": "date_normalize",
        },
    )
    workflow.add_edge("security_on_healing", "fixer")
    workflow.add_edge("fixer", "schema_validate")
    workflow.add_edge("quarantine_remaining", "date_normalize")
    workflow.add_edge("date_normalize", "security_gate")
    workflow.add_edge("security_gate", END)

    return workflow


def run_pipeline(input_path: Path | str | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Run the full pipeline. Returns (cleaned_records, quarantined_records).
    Optionally pass input_path for the JSON file.
    """
    graph = build_graph().compile()
    initial: PipelineState = {}
    if input_path is not None:
        initial["input_path"] = str(input_path) if isinstance(input_path, Path) else input_path
    final = graph.invoke(initial)
    cleaned = final.get("cleaned_records") or []
    quarantined = final.get("quarantined") or []
    quarantined_from_healing = final.get("quarantined_from_healing") or []
    return cleaned, quarantined + quarantined_from_healing
