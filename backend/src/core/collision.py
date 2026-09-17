"""Deterministic spatial and temporal collision detection engine."""

from datetime import datetime, date, timedelta
from typing import Optional
from decimal import Decimal


def parse_date(d) -> Optional[date]:
    """Parses a date string (YYYY-MM-DD) or date object into a date."""
    if not d:
        return None
    if isinstance(d, (date, datetime)):
        return d if isinstance(d, date) else d.date()
    try:
        return datetime.strptime(str(d).strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def resolve_project_dates(proj: dict) -> tuple[Optional[date], Optional[date]]:
    """
    Extracts or derives (start_date, end_date).
    If end_date is missing but duration_days is provided, derive end_date = start_date + duration.
    """
    start = parse_date(proj.get("start_date"))
    end = parse_date(proj.get("end_date"))
    duration = proj.get("duration_days")

    if start and not end and duration:
        try:
            end = start + timedelta(days=int(duration))
        except (ValueError, TypeError):
            pass

    return start, end


def check_temporal_relationship(s1: date, e1: date, s2: date, e2: date) -> tuple[bool, int]:
    """
    Returns (overlaps: bool, gap_days: int).
    - overlaps: True if intervals intersect [s1 <= e2 and s2 <= e1]
    - gap_days: Number of days between project windows if not overlapping (0 if overlapping)
    """
    if s1 <= e2 and s2 <= e1:
        return True, 0

    if e1 < s2:
        gap = (s2 - e1).days
    else:
        gap = (s1 - e2).days

    return False, max(0, gap)


def evaluate_pair_conflict(proj_a: dict, proj_b: dict, spatial_rel: str) -> Optional[dict]:
    """
    Evaluates collision between two projects given their spatial relationship ("SAME", "NEARBY", "NONE").
    Returns a conflict dictionary if risk is HIGH or POTENTIAL, else None.
    """
    if spatial_rel == "NONE":
        return None

    s1, e1 = resolve_project_dates(proj_a)
    s2, e2 = resolve_project_dates(proj_b)

    # If either project has unresolvable dates, it cannot be automatically compared
    if not s1 or not e1 or not s2 or not e2:
        return None

    overlaps, gap_days = check_temporal_relationship(s1, e1, s2, e2)

    type_a = proj_a.get("work_type", "other")
    type_b = proj_b.get("work_type", "other")
    dig_a = bool(proj_a.get("excavation_required", False))
    dig_b = bool(proj_b.get("excavation_required", False))

    surfacing_types = {"road_resurfacing", "road_construction"}
    a_surfaces = type_a in surfacing_types
    b_surfaces = type_b in surfacing_types

    risk_level = None
    conflict_type = None
    explanation = None
    expenditure_at_risk = 0.0

    cost_a = float(proj_a.get("cost_inr") or 0.0)
    cost_b = float(proj_b.get("cost_inr") or 0.0)

    # --- RULE 1: HIGH RISK ---
    # Same segment: one surfaces, other digs during surfacing OR within 180 days after surfacing ends
    if spatial_rel == "SAME":
        # Scenario 1A: A surfaces, B digs
        if a_surfaces and dig_b:
            if overlaps or (s2 >= s1 and (s2 - e1).days <= 180):
                risk_level = "HIGH"
                conflict_type = "ROAD_DESTRUCTION_REWORK"
                expenditure_at_risk = cost_a
                explanation = (
                    f"Excavation project '{proj_b.get('title', 'Project B')}' is scheduled to dig into "
                    f"road segment shortly after or during resurfacing by '{proj_a.get('title', 'Project A')}'. "
                    f"Resurfacing cost of ₹{cost_a:,.2f} is exposed to rework."
                )

        # Scenario 1B: B surfaces, A digs
        elif b_surfaces and dig_a:
            if overlaps or (s1 >= s2 and (s1 - e2).days <= 180):
                risk_level = "HIGH"
                conflict_type = "ROAD_DESTRUCTION_REWORK"
                expenditure_at_risk = cost_b
                explanation = (
                    f"Excavation project '{proj_a.get('title', 'Project A')}' is scheduled to dig into "
                    f"road segment shortly after or during resurfacing by '{proj_b.get('title', 'Project B')}'. "
                    f"Resurfacing cost of ₹{cost_b:,.2f} is exposed to rework."
                )

    # --- RULE 2: POTENTIAL RISK ---
    if not risk_level:
        # Pattern 2A: High risk pattern, but on NEARBY road (within 250m corridor)
        if spatial_rel == "NEARBY":
            if (a_surfaces and dig_b) or (b_surfaces and dig_a):
                if overlaps or gap_days <= 180:
                    risk_level = "POTENTIAL"
                    conflict_type = "CORRIDOR_DISRUPTION"
                    expenditure_at_risk = 0.0  # Conservative estimate on adjacent roads
                    explanation = (
                        f"Road resurfacing and excavation scheduled on adjacent connected corridors "
                        f"within {gap_days} days of each other. Traffic and access disruption likely."
                    )

        # Pattern 2B: Two excavations on SAME or NEARBY segment within 90 days (Shared-trench opportunity)
        if not risk_level and dig_a and dig_b:
            if overlaps or gap_days <= 90:
                risk_level = "POTENTIAL"
                conflict_type = "SHARED_TRENCH_OPPORTUNITY"
                expenditure_at_risk = 0.0
                explanation = (
                    f"Multiple utility excavations on {'same segment' if spatial_rel == 'SAME' else 'nearby segment'} "
                    f"within {gap_days} days. Opportunity for coordinated joint-trenching to prevent repeated digging."
                )

    if not risk_level:
        return None

    # Deterministic conflict ID
    id_a = proj_a.get("projectId", "A")
    id_b = proj_b.get("projectId", "B")
    pair_id = f"CONF_{min(id_a, id_b)}_{max(id_a, id_b)}"

    return {
        "conflictId": pair_id,
        "project_a_id": id_a,
        "project_b_id": id_b,
        "project_a_title": proj_a.get("title", "Project A"),
        "project_b_title": proj_b.get("title", "Project B"),
        "agency_a": proj_a.get("agency", "Unknown"),
        "agency_b": proj_b.get("agency", "Unknown"),
        "road_id": proj_a.get("road_id") or proj_b.get("road_id"),
        "road_name": proj_a.get("road_name") or proj_b.get("road_name"),
        "spatial_relationship": spatial_rel,
        "risk_level": risk_level,
        "conflict_type": conflict_type,
        "gap_days": gap_days,
        "expenditure_at_risk_inr": expenditure_at_risk,
        "explanation": explanation,
        "window_start": min(s1, s2).isoformat(),
        "window_end": max(e1, e2).isoformat(),
    }


def compute_all_conflicts(projects: list[dict], gazetteer) -> tuple[list[dict], float]:
    """
    Scans all projects, pairs them, detects collisions, and computes
    deduplicated total expenditure at risk.
    """
    valid_projects = [
        p for p in projects
        if p.get("status") == "EXTRACTED" and p.get("road_id")
    ]

    conflicts = []
    surfacing_projects_at_risk = set()

    n = len(valid_projects)
    for i in range(n):
        for j in range(i + 1, n):
            p1 = valid_projects[i]
            p2 = valid_projects[j]

            spatial_rel = gazetteer.get_spatial_relationship(p1.get("road_id"), p2.get("road_id"))
            conflict = evaluate_pair_conflict(p1, p2, spatial_rel)

            if conflict:
                conflicts.append(conflict)
                if conflict["risk_level"] == "HIGH":
                    # Deduplicate by surfacing project ID
                    if p1.get("work_type") in ("road_resurfacing", "road_construction"):
                        surfacing_projects_at_risk.add((p1["projectId"], float(p1.get("cost_inr") or 0.0)))
                    if p2.get("work_type") in ("road_resurfacing", "road_construction"):
                        surfacing_projects_at_risk.add((p2["projectId"], float(p2.get("cost_inr") or 0.0)))

    # Deduplicated total exposed expenditure
    total_deduped_expenditure = sum(cost for _, cost in surfacing_projects_at_risk)

    return conflicts, total_deduped_expenditure
