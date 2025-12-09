"""
Tests for ship role categorization functionality.

This test suite validates:
- settings.toml loading and parsing
- categorize_ship_by_role() function behavior
- Special case handling for dual-role ships
- Fallback behavior for missing/invalid configurations
"""

import pytest
import tomllib
import pathlib
from unittest.mock import patch, mock_open
from tempfile import NamedTemporaryFile
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSettingsTomlLoading:
    """Test settings.toml configuration file loading and validation."""

    def test_settings_file_exists(self):
        """Verify settings.toml exists in project root."""
        settings_path = pathlib.Path(__file__).parent.parent / "settings.toml"
        assert settings_path.exists(), "settings.toml file should exist"

    def test_settings_file_is_valid_toml(self):
        """Verify settings.toml is valid TOML format."""
        settings_path = pathlib.Path(__file__).parent.parent / "settings.toml"
        with open(settings_path, "rb") as f:
            settings = tomllib.load(f)
        assert isinstance(settings, dict), "settings.toml should parse to a dictionary"

    def test_ship_roles_section_exists(self):
        """Verify [ship_roles] section exists in settings.toml."""
        settings_path = pathlib.Path(__file__).parent.parent / "settings.toml"
        with open(settings_path, "rb") as f:
            settings = tomllib.load(f)
        assert "ship_roles" in settings, "settings.toml should have [ship_roles] section"

    def test_all_role_categories_exist(self):
        """Verify all four role categories (dps, logi, links, support) are defined."""
        settings_path = pathlib.Path(__file__).parent.parent / "settings.toml"
        with open(settings_path, "rb") as f:
            settings = tomllib.load(f)

        ship_roles = settings["ship_roles"]
        assert "dps" in ship_roles, "dps role category should be defined"
        assert "logi" in ship_roles, "logi role category should be defined"
        assert "links" in ship_roles, "links role category should be defined"
        assert "support" in ship_roles, "support role category should be defined"

    def test_role_categories_are_lists(self):
        """Verify all role categories contain lists of ship names."""
        settings_path = pathlib.Path(__file__).parent.parent / "settings.toml"
        with open(settings_path, "rb") as f:
            settings = tomllib.load(f)

        ship_roles = settings["ship_roles"]
        assert isinstance(ship_roles["dps"], list), "dps should be a list"
        assert isinstance(ship_roles["logi"], list), "logi should be a list"
        assert isinstance(ship_roles["links"], list), "links should be a list"
        assert isinstance(ship_roles["support"], list), "support should be a list"

    def test_role_lists_not_empty(self):
        """Verify role category lists are not empty."""
        settings_path = pathlib.Path(__file__).parent.parent / "settings.toml"
        with open(settings_path, "rb") as f:
            settings = tomllib.load(f)

        ship_roles = settings["ship_roles"]
        assert len(ship_roles["dps"]) > 0, "dps list should not be empty"
        assert len(ship_roles["logi"]) > 0, "logi list should not be empty"
        assert len(ship_roles["links"]) > 0, "links list should not be empty"
        assert len(ship_roles["support"]) > 0, "support list should not be empty"

    def test_special_cases_section_exists(self):
        """Verify special_cases section exists and is properly structured."""
        settings_path = pathlib.Path(__file__).parent.parent / "settings.toml"
        with open(settings_path, "rb") as f:
            settings = tomllib.load(f)

        ship_roles = settings["ship_roles"]
        assert "special_cases" in ship_roles, "special_cases section should exist"
        assert isinstance(ship_roles["special_cases"], dict), "special_cases should be a dict"

    def test_vulture_special_case_defined(self):
        """Verify Vulture special case has correct fit_id mappings."""
        settings_path = pathlib.Path(__file__).parent.parent / "settings.toml"
        with open(settings_path, "rb") as f:
            settings = tomllib.load(f)

        special_cases = settings["ship_roles"]["special_cases"]
        assert "Vulture" in special_cases, "Vulture should be in special_cases"
        assert "369" in special_cases["Vulture"], "Vulture fit 369 should be defined"
        assert "475" in special_cases["Vulture"], "Vulture fit 475 should be defined"
        assert special_cases["Vulture"]["369"] == "DPS", "Vulture fit 369 should be DPS"
        assert special_cases["Vulture"]["475"] == "Links", "Vulture fit 475 should be Links"

    def test_deimos_special_case_defined(self):
        """Verify Deimos special case has correct fit_id mappings."""
        settings_path = pathlib.Path(__file__).parent.parent / "settings.toml"
        with open(settings_path, "rb") as f:
            settings = tomllib.load(f)

        special_cases = settings["ship_roles"]["special_cases"]
        assert "Deimos" in special_cases, "Deimos should be in special_cases"
        assert "202" in special_cases["Deimos"], "Deimos fit 202 should be defined"
        assert "330" in special_cases["Deimos"], "Deimos fit 330 should be defined"
        assert special_cases["Deimos"]["202"] == "DPS", "Deimos fit 202 should be DPS"
        assert special_cases["Deimos"]["330"] == "Support", "Deimos fit 330 should be Support"

    def test_no_duplicate_ships_across_categories(self):
        """Verify ships are not duplicated across standard role categories."""
        settings_path = pathlib.Path(__file__).parent.parent / "settings.toml"
        with open(settings_path, "rb") as f:
            settings = tomllib.load(f)

        ship_roles = settings["ship_roles"]
        dps_set = set(ship_roles["dps"])
        logi_set = set(ship_roles["logi"])
        links_set = set(ship_roles["links"])
        support_set = set(ship_roles["support"])

        # Check for overlaps
        assert len(dps_set & logi_set) == 0, "No ships should be in both dps and logi"
        assert len(dps_set & links_set) == 0, "No ships should be in both dps and links"
        assert len(dps_set & support_set) == 0, "No ships should be in both dps and support"
        assert len(logi_set & links_set) == 0, "No ships should be in both logi and links"
        assert len(logi_set & support_set) == 0, "No ships should be in both logi and support"
        assert len(links_set & support_set) == 0, "No ships should be in both links and support"


class TestCategorizeShipByRole:
    """Test the categorize_ship_by_role() function from doctrine_report.py."""

    @pytest.fixture
    def mock_settings(self):
        """Provide mock settings for testing."""
        return {
            "ship_roles": {
                "dps": ["Ferox", "Hurricane", "Tempest"],
                "logi": ["Osprey", "Guardian", "Basilisk"],
                "links": ["Drake", "Claymore", "Nighthawk"],
                "support": ["Sabre", "Stiletto", "Falcon"],
                "special_cases": {
                    "Vulture": {"369": "DPS", "475": "Links"},
                    "Deimos": {"202": "DPS", "330": "Support"}
                }
            }
        }

    def test_standard_dps_ship(self, mock_settings):
        """Test categorization of standard DPS ship."""
        from pages.doctrine_report import categorize_ship_by_role

        with patch("builtins.open", mock_open(read_data=b"")):
            with patch("tomllib.load", return_value=mock_settings):
                result = categorize_ship_by_role("Ferox", 100)
                assert result == "DPS", "Ferox should be categorized as DPS"

    def test_standard_logi_ship(self, mock_settings):
        """Test categorization of standard Logi ship."""
        from pages.doctrine_report import categorize_ship_by_role

        with patch("builtins.open", mock_open(read_data=b"")):
            with patch("tomllib.load", return_value=mock_settings):
                result = categorize_ship_by_role("Osprey", 200)
                assert result == "Logi", "Osprey should be categorized as Logi"

    def test_standard_links_ship(self, mock_settings):
        """Test categorization of standard Links ship."""
        from pages.doctrine_report import categorize_ship_by_role

        with patch("builtins.open", mock_open(read_data=b"")):
            with patch("tomllib.load", return_value=mock_settings):
                result = categorize_ship_by_role("Drake", 300)
                assert result == "Links", "Drake should be categorized as Links"

    def test_standard_support_ship(self, mock_settings):
        """Test categorization of standard Support ship."""
        from pages.doctrine_report import categorize_ship_by_role

        with patch("builtins.open", mock_open(read_data=b"")):
            with patch("tomllib.load", return_value=mock_settings):
                result = categorize_ship_by_role("Sabre", 400)
                assert result == "Support", "Sabre should be categorized as Support"

    def test_vulture_dps_special_case(self, mock_settings):
        """Test Vulture with fit_id 369 categorized as DPS."""
        from pages.doctrine_report import categorize_ship_by_role

        with patch("builtins.open", mock_open(read_data=b"")):
            with patch("tomllib.load", return_value=mock_settings):
                result = categorize_ship_by_role("Vulture", 369)
                assert result == "DPS", "Vulture fit 369 should be DPS"

    def test_vulture_links_special_case(self, mock_settings):
        """Test Vulture with fit_id 475 categorized as Links."""
        from pages.doctrine_report import categorize_ship_by_role

        with patch("builtins.open", mock_open(read_data=b"")):
            with patch("tomllib.load", return_value=mock_settings):
                result = categorize_ship_by_role("Vulture", 475)
                assert result == "Links", "Vulture fit 475 should be Links"

    def test_vulture_unknown_fit_id_fallback(self, mock_settings):
        """Test Vulture with unknown fit_id falls back to keyword matching."""
        from pages.doctrine_report import categorize_ship_by_role

        with patch("builtins.open", mock_open(read_data=b"")):
            with patch("tomllib.load", return_value=mock_settings):
                result = categorize_ship_by_role("Vulture", 999)
                assert result == "Support", "Vulture with unknown fit_id should fall back to Support"

    def test_deimos_dps_special_case(self, mock_settings):
        """Test Deimos with fit_id 202 categorized as DPS."""
        from pages.doctrine_report import categorize_ship_by_role

        with patch("builtins.open", mock_open(read_data=b"")):
            with patch("tomllib.load", return_value=mock_settings):
                result = categorize_ship_by_role("Deimos", 202)
                assert result == "DPS", "Deimos fit 202 should be DPS"

    def test_deimos_support_special_case(self, mock_settings):
        """Test Deimos with fit_id 330 categorized as Support."""
        from pages.doctrine_report import categorize_ship_by_role

        with patch("builtins.open", mock_open(read_data=b"")):
            with patch("tomllib.load", return_value=mock_settings):
                result = categorize_ship_by_role("Deimos", 330)
                assert result == "Support", "Deimos fit 330 should be Support"

    def test_fit_id_as_integer(self, mock_settings):
        """Test that fit_id can be passed as integer (auto-converted to string)."""
        from pages.doctrine_report import categorize_ship_by_role

        with patch("builtins.open", mock_open(read_data=b"")):
            with patch("tomllib.load", return_value=mock_settings):
                result = categorize_ship_by_role("Vulture", 369)  # int, not string
                assert result == "DPS", "fit_id should work as integer"

    def test_unknown_ship_keyword_fallback_hurricane(self, mock_settings):
        """Test unknown ship with 'hurricane' in name falls back to DPS."""
        from pages.doctrine_report import categorize_ship_by_role

        with patch("builtins.open", mock_open(read_data=b"")):
            with patch("tomllib.load", return_value=mock_settings):
                result = categorize_ship_by_role("Hurricane Fleet Issue", 500)
                assert result == "DPS", "Ships with 'hurricane' should fall back to DPS"

    def test_unknown_ship_keyword_fallback_osprey(self, mock_settings):
        """Test unknown ship with 'osprey' in name falls back to Logi."""
        from pages.doctrine_report import categorize_ship_by_role

        with patch("builtins.open", mock_open(read_data=b"")):
            with patch("tomllib.load", return_value=mock_settings):
                result = categorize_ship_by_role("Osprey Navy Issue", 501)
                assert result == "Logi", "Ships with 'osprey' should fall back to Logi"

    def test_unknown_ship_keyword_fallback_drake(self, mock_settings):
        """Test unknown ship with 'drake' in name falls back to Links."""
        from pages.doctrine_report import categorize_ship_by_role

        with patch("builtins.open", mock_open(read_data=b"")):
            with patch("tomllib.load", return_value=mock_settings):
                result = categorize_ship_by_role("Drake Navy Issue", 502)
                assert result == "Links", "Ships with 'drake' should fall back to Links"

    def test_completely_unknown_ship_fallback(self, mock_settings):
        """Test completely unknown ship defaults to Support."""
        from pages.doctrine_report import categorize_ship_by_role

        with patch("builtins.open", mock_open(read_data=b"")):
            with patch("tomllib.load", return_value=mock_settings):
                result = categorize_ship_by_role("Unknown Ship XYZ", 999)
                assert result == "Support", "Unknown ships should default to Support"


class TestFallbackBehavior:
    """Test fallback behavior when settings.toml is missing or invalid."""

    def test_missing_settings_file_fallback(self):
        """Test that missing settings.toml falls back to keyword matching."""
        from pages.doctrine_report import categorize_ship_by_role

        with patch("builtins.open", side_effect=FileNotFoundError("settings.toml not found")):
            result = categorize_ship_by_role("Hurricane", 100)
            assert result == "DPS", "Should fall back to DPS for Hurricane"

    def test_missing_settings_file_fallback_logi(self):
        """Test fallback for Logi ships when settings.toml missing."""
        from pages.doctrine_report import categorize_ship_by_role

        with patch("builtins.open", side_effect=FileNotFoundError("settings.toml not found")):
            result = categorize_ship_by_role("Osprey", 200)
            assert result == "Logi", "Should fall back to Logi for Osprey"

    def test_missing_settings_file_fallback_links(self):
        """Test fallback for Links ships when settings.toml missing."""
        from pages.doctrine_report import categorize_ship_by_role

        with patch("builtins.open", side_effect=FileNotFoundError("settings.toml not found")):
            result = categorize_ship_by_role("Drake", 300)
            assert result == "Links", "Should fall back to Links for Drake"

    def test_missing_settings_file_fallback_support(self):
        """Test fallback for unknown ships when settings.toml missing."""
        from pages.doctrine_report import categorize_ship_by_role

        with patch("builtins.open", side_effect=FileNotFoundError("settings.toml not found")):
            result = categorize_ship_by_role("Unknown Ship", 999)
            assert result == "Support", "Should fall back to Support for unknown ships"


class TestRealSettingsToml:
    """Test with the actual settings.toml file from the project."""

    def test_ferox_categorized_as_dps(self):
        """Test Ferox is categorized as DPS using real settings.toml."""
        from pages.doctrine_report import categorize_ship_by_role
        result = categorize_ship_by_role("Ferox", 100)
        assert result == "DPS", "Ferox should be DPS"

    def test_osprey_categorized_as_logi(self):
        """Test Osprey is categorized as Logi using real settings.toml."""
        from pages.doctrine_report import categorize_ship_by_role
        result = categorize_ship_by_role("Osprey", 200)
        assert result == "Logi", "Osprey should be Logi"

    def test_claymore_categorized_as_links(self):
        """Test Claymore is categorized as Links using real settings.toml."""
        from pages.doctrine_report import categorize_ship_by_role
        result = categorize_ship_by_role("Claymore", 300)
        assert result == "Links", "Claymore should be Links"

    def test_sabre_categorized_as_support(self):
        """Test Sabre is categorized as Support using real settings.toml."""
        from pages.doctrine_report import categorize_ship_by_role
        result = categorize_ship_by_role("Sabre", 400)
        assert result == "Support", "Sabre should be Support"

    def test_vulture_369_is_dps(self):
        """Test Vulture fit 369 is DPS using real settings.toml."""
        from pages.doctrine_report import categorize_ship_by_role
        result = categorize_ship_by_role("Vulture", 369)
        assert result == "DPS", "Vulture fit 369 should be DPS"

    def test_vulture_475_is_links(self):
        """Test Vulture fit 475 is Links using real settings.toml."""
        from pages.doctrine_report import categorize_ship_by_role
        result = categorize_ship_by_role("Vulture", 475)
        assert result == "Links", "Vulture fit 475 should be Links"

    def test_deimos_202_is_dps(self):
        """Test Deimos fit 202 is DPS using real settings.toml."""
        from pages.doctrine_report import categorize_ship_by_role
        result = categorize_ship_by_role("Deimos", 202)
        assert result == "DPS", "Deimos fit 202 should be DPS"

    def test_deimos_330_is_support(self):
        """Test Deimos fit 330 is Support using real settings.toml."""
        from pages.doctrine_report import categorize_ship_by_role
        result = categorize_ship_by_role("Deimos", 330)
        assert result == "Support", "Deimos fit 330 should be Support"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
