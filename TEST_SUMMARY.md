# Ship Role Categorization Test Suite

**File:** `tests/test_ship_role_categorization.py`  
**Total Tests:** 36  
**Status:** ✅ All Passing  
**Execution Time:** 1.09s

## Overview

Comprehensive test suite ensuring `settings.toml` configuration changes don't break ship role categorization functionality. Tests cover configuration validation, function behavior, fallback mechanisms, and real-world integration.

## Test Categories

### 1. Configuration Validation (10 tests)

Tests that verify `settings.toml` structure and content:

| Test | Description | Validates |
|------|-------------|-----------|
| `test_settings_file_exists` | File exists in project root | settings.toml presence |
| `test_settings_file_is_valid_toml` | Valid TOML syntax | File parsability |
| `test_ship_roles_section_exists` | [ship_roles] section present | Section structure |
| `test_all_role_categories_exist` | All 4 categories defined | dps, logi, links, support |
| `test_role_categories_are_lists` | Categories are list type | Type correctness |
| `test_role_lists_not_empty` | Lists contain ships | Non-empty validation |
| `test_special_cases_section_exists` | special_cases section present | Special case structure |
| `test_vulture_special_case_defined` | Vulture fit mappings correct | Vulture 369→DPS, 475→Links |
| `test_deimos_special_case_defined` | Deimos fit mappings correct | Deimos 202→DPS, 330→Support |
| `test_no_duplicate_ships_across_categories` | Ships unique to categories | Data integrity |

### 2. Function Behavior Tests (14 tests)

Tests for `categorize_ship_by_role()` function:

| Test | Ship | Fit ID | Expected Role | Purpose |
|------|------|--------|---------------|---------|
| `test_standard_dps_ship` | Ferox | 100 | DPS | Standard categorization |
| `test_standard_logi_ship` | Osprey | 200 | Logi | Standard categorization |
| `test_standard_links_ship` | Drake | 300 | Links | Standard categorization |
| `test_standard_support_ship` | Sabre | 400 | Support | Standard categorization |
| `test_vulture_dps_special_case` | Vulture | 369 | DPS | Special case handling |
| `test_vulture_links_special_case` | Vulture | 475 | Links | Special case handling |
| `test_vulture_unknown_fit_id_fallback` | Vulture | 999 | Support | Unknown fit_id fallback |
| `test_deimos_dps_special_case` | Deimos | 202 | DPS | Special case handling |
| `test_deimos_support_special_case` | Deimos | 330 | Support | Special case handling |
| `test_fit_id_as_integer` | Vulture | 369 (int) | DPS | Parameter type handling |
| `test_unknown_ship_keyword_fallback_hurricane` | Hurricane Fleet Issue | 500 | DPS | Keyword matching |
| `test_unknown_ship_keyword_fallback_osprey` | Osprey Navy Issue | 501 | Logi | Keyword matching |
| `test_unknown_ship_keyword_fallback_drake` | Drake Navy Issue | 502 | Links | Keyword matching |
| `test_completely_unknown_ship_fallback` | Unknown Ship XYZ | 999 | Support | Default fallback |

### 3. Fallback Behavior Tests (4 tests)

Tests for graceful degradation when `settings.toml` is missing:

| Test | Ship | Expected Role | Purpose |
|------|------|---------------|---------|
| `test_missing_settings_file_fallback` | Hurricane | DPS | Missing config → keyword match |
| `test_missing_settings_file_fallback_logi` | Osprey | Logi | Missing config → keyword match |
| `test_missing_settings_file_fallback_links` | Drake | Links | Missing config → keyword match |
| `test_missing_settings_file_fallback_support` | Unknown Ship | Support | Missing config → default |

### 4. Integration Tests (8 tests)

Tests using real `settings.toml` file:

| Test | Ship | Fit ID | Expected Role | Purpose |
|------|------|--------|---------------|---------|
| `test_ferox_categorized_as_dps` | Ferox | 100 | DPS | Real config integration |
| `test_osprey_categorized_as_logi` | Osprey | 200 | Logi | Real config integration |
| `test_claymore_categorized_as_links` | Claymore | 300 | Links | Real config integration |
| `test_sabre_categorized_as_support` | Sabre | 400 | Support | Real config integration |
| `test_vulture_369_is_dps` | Vulture | 369 | DPS | Real special case |
| `test_vulture_475_is_links` | Vulture | 475 | Links | Real special case |
| `test_deimos_202_is_dps` | Deimos | 202 | DPS | Real special case |
| `test_deimos_330_is_support` | Deimos | 330 | Support | Real special case |

## Running the Tests

### Run All Tests
```bash
uv run pytest tests/test_ship_role_categorization.py -v
```

### Run Specific Test Class
```bash
# Configuration validation only
uv run pytest tests/test_ship_role_categorization.py::TestSettingsTomlLoading -v

# Function behavior only
uv run pytest tests/test_ship_role_categorization.py::TestCategorizeShipByRole -v

# Fallback behavior only
uv run pytest tests/test_ship_role_categorization.py::TestFallbackBehavior -v

# Integration tests only
uv run pytest tests/test_ship_role_categorization.py::TestRealSettingsToml -v
```

### Run Specific Test
```bash
uv run pytest tests/test_ship_role_categorization.py::TestCategorizeShipByRole::test_vulture_dps_special_case -v
```

## What's Protected

These tests ensure:

### ✅ Configuration Integrity
- settings.toml file exists and is valid TOML
- All required sections are present
- Ship lists are properly formatted
- Special cases are correctly defined
- No accidental ship duplicates across categories

### ✅ Function Correctness
- Standard ships categorized correctly
- Special cases work for specific fit_ids
- Unknown fit_ids fall back gracefully
- Parameter types handled correctly (int/string)
- Keyword matching works for unknown ships

### ✅ Error Resilience
- Missing config file doesn't crash the app
- Invalid fit_ids fall back to safe defaults
- Unknown ships get reasonable default categorization

### ✅ Real-World Behavior
- Integration with actual settings.toml
- Special cases work as documented
- All role categories function correctly

## Breaking Changes Detection

The tests will fail if:

1. **settings.toml is deleted or moved**
2. **Invalid TOML syntax introduced**
3. **Required sections removed** (ship_roles, dps, logi, links, support)
4. **Special cases misconfigured** (Vulture, Deimos)
5. **Function signature changed** (categorize_ship_by_role parameters)
6. **Categorization logic broken** (ships returning wrong roles)

## Test Maintenance

### Adding New Ships
When adding ships to `settings.toml`:
1. Tests automatically validate the file structure
2. No test changes needed for standard ships
3. Add integration tests if special validation needed

### Adding New Special Cases
When adding new special case ships:
1. Update `test_special_cases_section_exists` if needed
2. Add specific tests like `test_[shipname]_special_case_defined`
3. Add integration tests for each fit_id variant

### Modifying Function Behavior
When changing `categorize_ship_by_role()`:
1. Update mock_settings fixture if needed
2. Add tests for new behavior
3. Ensure backward compatibility tests still pass

## CI/CD Integration

Recommended pytest command for CI:
```bash
uv run pytest tests/test_ship_role_categorization.py -v --tb=short
```

For coverage reporting:
```bash
uv run pytest tests/test_ship_role_categorization.py --cov=pages.doctrine_report --cov-report=term-missing
```

## Test Performance

- **Execution Time:** ~1.09 seconds for 36 tests
- **Fast feedback** for configuration changes
- **Minimal dependencies** (only requires tomllib, pytest, pathlib)

## Success Criteria

All 36 tests must pass before:
- ✅ Merging PRs that modify settings.toml
- ✅ Deploying changes to production
- ✅ Releasing new versions
- ✅ Modifying ship role categorization logic

---

**Last Updated:** 2025-12-08  
**Test Suite Version:** 1.0  
**Maintained By:** Automated testing framework
