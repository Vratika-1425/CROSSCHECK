from datetime import date
from backend.src.core.collision import (
    check_temporal_relationship,
    evaluate_pair_conflict,
    compute_all_conflicts
)
from backend.src.core.gazetteer import Gazetteer


def test_date_overlap_and_gap():
    # Complete overlap
    overlaps, gap = check_temporal_relationship(
        date(2025, 1, 1), date(2025, 3, 1),
        date(2025, 2, 1), date(2025, 4, 1)
    )
    assert overlaps is True
    assert gap == 0

    # 10 days gap
    overlaps, gap = check_temporal_relationship(
        date(2025, 1, 1), date(2025, 1, 31),
        date(2025, 2, 10), date(2025, 3, 1)
    )
    assert overlaps is False
    assert gap == 10


def test_high_risk_resurface_then_dig_within_180_days():
    resurfacing = {
        "projectId": "P1",
        "title": "MG Road Asphalt Overlay",
        "agency": "BBMP (Roads)",
        "work_type": "road_resurfacing",
        "excavation_required": False,
        "road_id": "ROAD_MG_01",
        "start_date": "2025-01-01",
        "end_date": "2025-02-01",
        "cost_inr": 5000000.0,
        "status": "EXTRACTED"
    }

    water_pipe_dig = {
        "projectId": "P2",
        "title": "Water Main Pipeline Replacement",
        "agency": "BWSSB (Water)",
        "work_type": "water_supply",
        "excavation_required": True,
        "road_id": "ROAD_MG_01",
        "start_date": "2025-04-01",  # 59 days after resurfacing ends (< 180 days)
        "end_date": "2025-05-01",
        "cost_inr": 2000000.0,
        "status": "EXTRACTED"
    }

    conflict = evaluate_pair_conflict(resurfacing, water_pipe_dig, spatial_rel="SAME")
    assert conflict is not None
    assert conflict["risk_level"] == "HIGH"
    assert conflict["conflict_type"] == "ROAD_DESTRUCTION_REWORK"
    assert conflict["expenditure_at_risk_inr"] == 5000000.0


def test_no_high_risk_after_180_days():
    resurfacing = {
        "projectId": "P1",
        "title": "MG Road Asphalt Overlay",
        "agency": "BBMP",
        "work_type": "road_resurfacing",
        "excavation_required": False,
        "start_date": "2025-01-01",
        "end_date": "2025-02-01",
        "cost_inr": 5000000.0,
    }

    dig_much_later = {
        "projectId": "P2",
        "title": "Telecom Trenching",
        "agency": "Telecom Dept",
        "work_type": "telecom_fiber",
        "excavation_required": True,
        "start_date": "2025-10-01",  # > 180 days gap
        "end_date": "2025-11-01",
        "cost_inr": 1000000.0,
    }

    conflict = evaluate_pair_conflict(resurfacing, dig_much_later, spatial_rel="SAME")
    assert conflict is None


def test_deduplication_of_expenditure_at_risk():
    gaz = Gazetteer()

    # One resurfacing project hit by TWO different dig projects on same road
    resurface = {
        "projectId": "P_SURFACE",
        "title": "MG Road Resurfacing",
        "work_type": "road_resurfacing",
        "excavation_required": False,
        "road_id": "ROAD_MG_01",
        "start_date": "2025-01-01",
        "end_date": "2025-01-31",
        "cost_inr": 10000000.0,  # 1 Crore
        "status": "EXTRACTED"
    }

    dig_water = {
        "projectId": "P_WATER",
        "title": "Water Pipe Trench",
        "work_type": "water_supply",
        "excavation_required": True,
        "road_id": "ROAD_MG_01",
        "start_date": "2025-02-15",
        "end_date": "2025-03-15",
        "cost_inr": 2000000.0,
        "status": "EXTRACTED"
    }

    dig_gas = {
        "projectId": "P_GAS",
        "title": "Gas Pipeline Trench",
        "work_type": "drainage",
        "excavation_required": True,
        "road_id": "ROAD_MG_01",
        "start_date": "2025-03-01",
        "end_date": "2025-03-30",
        "cost_inr": 1500000.0,
        "status": "EXTRACTED"
    }

    projects = [resurface, dig_water, dig_gas]
    conflicts, total_at_risk = compute_all_conflicts(projects, gaz)

    # 3 conflicts: surface vs water (HIGH), surface vs gas (HIGH), water vs gas (POTENTIAL)
    assert len(conflicts) == 3

    # The resurfacing cost of 10,000,000 must NOT be counted twice
    assert total_at_risk == 10000000.0
