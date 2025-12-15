import pytest
from recreation_api import RecreationGovAPI


def test_parse_facility_id_from_url():
    """Test parsing facility ID from various URL formats"""
    api = RecreationGovAPI()
    
    # Standard campground URL
    url1 = "https://www.recreation.gov/camping/campgrounds/232447"
    assert api.parse_facility_id_from_url(url1) == "232447"
    
    # Gateway URL
    url2 = "https://www.recreation.gov/camping/gateways/2725"
    assert api.parse_facility_id_from_url(url2) == "2725"
    
    # URL with parameters
    url3 = "https://www.recreation.gov/camping/campgrounds/232447?tab=info"
    assert api.parse_facility_id_from_url(url3) == "232447"
    
    # Just the ID
    url4 = "232447"
    assert api.parse_facility_id_from_url(url4) == "232447"
    
    # Invalid URL
    url5 = "https://www.example.com"
    assert api.parse_facility_id_from_url(url5) is None


def test_get_campsite_availability_for_dates():
    """Test parsing availability data for date range"""
    api = RecreationGovAPI()
    
    # Mock campsite data
    campsites_data = {
        "12345": {
            "campsite_name": "Site A",
            "campsite_type": "Standard",
            "availabilities": {
                "2024-07-01": "Available",
                "2024-07-02": "Reserved",
                "2024-07-03": "Available",
                "2024-07-10": "Available"
            }
        },
        "12346": {
            "campsite_name": "Site B",
            "campsite_type": "RV",
            "availabilities": {
                "2024-07-01": "Reserved",
                "2024-07-02": "Reserved",
                "2024-07-03": "Reserved"
            }
        }
    }
    
    result = api.get_campsite_availability_for_dates(
        campsites_data,
        "2024-07-01",
        "2024-07-03"
    )
    
    # Should have both sites
    assert "12345" in result
    assert "12346" in result
    
    # Site A should have availability
    assert result["12345"]["has_availability"] == True
    assert result["12345"]["name"] == "Site A"
    
    # Site B should not have availability
    assert result["12346"]["has_availability"] == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
