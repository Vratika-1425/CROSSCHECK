from backend.src.extract.evidence import verify_quote, verify_extraction_field
from backend.src.core.gazetteer import Gazetteer, haversine_distance_meters

def test_evidence_verification():
    page_text = "Tender No: PWD/2024/09\nResurfacing of Mahatma Gandhi Road from Junction A to B."
    
    # Exact quote
    assert verify_quote(page_text, "Resurfacing of Mahatma Gandhi Road") is True
    
    # Whitespace/newline tolerance
    assert verify_quote(page_text, "PWD/2024/09 Resurfacing of") is True
    
    # Hallucinated quote
    assert verify_quote(page_text, "Resurfacing of Brigade Road") is False

def test_gazetteer_matching():
    gaz = Gazetteer()
    
    # Alias matches
    assert gaz.match_road("M.G. Road") == "ROAD_MG_01"
    assert gaz.match_road("Resurfacing on brigade rd near junction") == "ROAD_BRIGADE_01"
    assert gaz.match_road("Unknown Path in Jungle") is None

def test_spatial_relationship():
    gaz = Gazetteer()
    
    # Same road
    assert gaz.get_spatial_relationship("ROAD_MG_01", "ROAD_MG_01") == "SAME"
    
    # MG Road and Brigade Road connect at junction (distance ~0m) -> NEARBY
    assert gaz.get_spatial_relationship("ROAD_MG_01", "ROAD_BRIGADE_01") == "NEARBY"
    
    # MG Road to Indiranagar 100ft Road is > 3km -> NONE
    assert gaz.get_spatial_relationship("ROAD_MG_01", "ROAD_INDIRA_100FT") == "NONE"
