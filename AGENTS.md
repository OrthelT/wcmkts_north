# Repository Guidelines for AI Coding Agents

This file provides guidance for AI coding agents (Claude Code, Cursor, GitHub Copilot, etc.) when working with code in this repository.

## Overview

Winter Coalition Market Stats Viewer is a Streamlit web application for EVE Online market analysis. It provides real-time market data visualization, doctrine analysis, and inventory management tools for the Winter Coalition.

## Project Structure & Module Organization

- **app.py**: Streamlit entrypoint. UI pages live in `pages/`.
- **pages/**: Individual page modules for different features
  - `market_stats.py`: Market data visualization and analysis
  - `doctrine_status.py`: Doctrine component tracking
  - `doctrine_report.py`: Doctrine analysis reports
  - `low_stock.py`: Low inventory alerting
  - `build_costs.py`: Manufacturing cost analysis
- **Core modules**:
  - `config.py`: Database configuration and sync management (DatabaseConfig class)
  - `db_handler.py`: Database connection management and engine creation
  - `db_utils.py`: Database synchronization with Turso cloud database
  - `doctrines.py`: Doctrine-related business logic
  - `models.py`: SQLAlchemy ORM models for database tables
  - `build_cost_models.py`: Models specific to manufacturing cost analysis
  - `utils.py`: Utility functions and helpers
- **Configuration**:
  - `config.toml`: Streamlit theme configuration
  - `settings.toml`: Application settings including ship role categorization
  - `logging_config.py`: Centralized logging setup
  - `.streamlit/`: Streamlit secrets (`.streamlit/secrets.toml`)
  - `.env`: Local environment overrides (optional)
- **Data/assets**:
  - Local SQLite/LibSQL replicas (`*.db*`)
  - CSV seeds
  - Logs (ignored by Git)
  - `last_sync_state.json`: Tracks database sync status and scheduling
- **Docs**: `docs/` contains admin/database guides and walkthroughs
- **Tests**: Lightweight checks in `tests/` (note: directory is ignored by `.gitignore`)

## Build, Test, and Development Commands

### Installation and Setup
```bash
# Install dependencies using uv (preferred package manager for Python 3.12)
uv sync

# Alternative: install via pip if uv is not available
pip install -e .
```

### Running the Application
```bash
# Run app locally (via uv)
uv run streamlit run app.py

# Alternative: direct streamlit command
streamlit run app.py

# Development mode with file watching
streamlit run app.py --server.runOnSave true
```

### Database Operations
```bash
# Test database sync functionality
python3 -c "
import sys
sys.path.append('.')
from db_utils import sync_db
sync_db()
"

# Check database connection and schema
python3 -c "
import sys
sys.path.append('.')
from db_handler import get_local_mkt_engine, get_local_sde_engine
print('Market DB:', get_local_mkt_engine())
print('SDE DB:', get_local_sde_engine())
"

# Quick data scripts
uv run python build_cost_models.py  # Rebuilds cost DB
```

### Linting and Formatting
```bash
# Lint (recommended if Ruff is installed)
uv run ruff check .

# Format
uv run ruff format .
```

### Testing
```bash
# Run tests (after adding pytest)
uv run pytest -q
```

## Database Architecture

### Turso Embedded Replica Pattern
The application uses Turso's embedded-replica feature for optimal performance:
- Local SQLite databases provide fast reads
- Automatic synchronization with remote Turso database
- Background sync occurs every 3 hours or on manual trigger

### Local Databases
- `wcmkt.db`: Market orders and statistics (synced from Turso)
- `sde.db`: EVE Online Static Data Export
- `build_cost.db`: Manufacturing and structure data

### Key Database Tables

**Market Database (wcmkt.db):**
- `marketorders`: Individual buy/sell orders
- `marketstats`: Aggregated market statistics
- `market_history`: Historical price/volume data
- `doctrines`: Fleet doctrine configurations
- `ship_targets`: Target inventory levels

**SDE Database (sde.db):**
- `invTypes`: EVE Online item definitions
- `invGroups`: Item group classifications
- `invCategories`: High-level item categories

## Environment Setup

### Required Secrets (Streamlit Cloud)
```toml
[secrets]
TURSO_DATABASE_URL = "your_turso_database_url"
TURSO_AUTH_TOKEN = "your_turso_auth_token"
SDE_URL = "your_sde_database_url"
SDE_AUTH_TOKEN = "your_sde_auth_token"
```

### Local Development
For local Streamlit runs, store credentials in `.streamlit/secrets.toml` (git-ignored). This is the default source for database URLs/tokens used by `DatabaseConfig`. Example structure:

```toml
[wcmkt2_turso]
url = "libsql://..."
token = "..."

[sde_aws_turso]
url = "libsql://..."
token = "..."

[buildcost_turso]
url = "libsql://..."
token = "..."
```

- Create `.streamlit/secrets.toml` with the above configuration
- Ensure local database files exist: `wcmkt.db`, `sde.db`, `build_cost.db`
- The application will use local SQLite files if sync credentials are not available
- `.env` variables may be used for other tooling, but the app resolves secrets via Streamlit

## Coding Style & Naming Conventions

- **Python style**: PEP 8, 4-space indents, max line length 100
- **Naming conventions**:
  - Modules/functions: `snake_case`
  - Classes: `PascalCase`
  - Constants: `UPPER_SNAKE_CASE`
- **Types/docstrings**: Prefer type hints; include concise docstrings on public functions
- **Logging**: Use `logging` with `logging_config.py`; don't use `print()` in production code

## Development Guidelines

### Adding New Pages
1. Create new page file in `pages/` directory
2. Follow existing naming pattern with emoji prefix
3. Add page registration in `app.py` pages dictionary
4. Import required database engines from `db_handler.py`
5. Use centralized logging from `logging_config.py`

### Database Operations
- Always use SQLAlchemy engines from `db_handler.py`
- Use context managers for database sessions
- Implement proper error handling and logging
- Clear Streamlit cache after database modifications

### Performance Considerations
- Use `@st.cache_data` for expensive computations (TTL: 15 minutes)
- Use `@st.cache_resource` for database connections
- Clear caches during database sync operations
- Implement proper connection pooling

### Data Synchronization
- Manual sync available via sidebar button
- Automatic sync scheduled for 13:00 UTC daily
- Sync status tracked in `last_sync_state.json`
- Use `db_utils.sync_db()` for programmatic sync operations

## Ship Role Categorization

### Overview
Ships in doctrine reports are categorized into functional roles (DPS, Logi, Links, Support) using configuration-driven logic instead of hardcoded lists. This allows for flexible role management and special case handling.

### Configuration File: settings.toml

The `settings.toml` file contains ship role definitions:

```toml
[ship_roles]
    dps = ['Hurricane', 'Ferox', 'Zealot', ...]  # Primary damage dealers
    logi = ['Osprey', 'Guardian', 'Basilisk', ...]  # Logistics ships
    links = ['Claymore', 'Drake', 'Sleipnir', ...]  # Command ships
    support = ['Sabre', 'Stiletto', 'Falcon', ...]  # EWAR, tackle, interdiction

    # Special cases: Ships that serve different roles based on fitting
    [ship_roles.special_cases.Vulture]
        "369" = "DPS"    # Vulture fit 369 is categorized as DPS
        "475" = "Links"  # Vulture fit 475 is categorized as Links

    [ship_roles.special_cases.Deimos]
        "202" = "DPS"      # Deimos fit 202 is DPS
        "330" = "Support"  # Deimos fit 330 is Support
```

### Role Categorization Logic

The `categorize_ship_by_role(ship_name, fit_id)` function in `pages/doctrine_report.py`:

1. **Checks special cases first**: If a ship has fit_id-specific roles defined, use that role
2. **Checks standard role lists**: Match ship name against dps, logi, links, support lists
3. **Fallback to keyword matching**: Legacy pattern matching if ship not in configuration
4. **Returns role**: "DPS", "Logi", "Links", or "Support"

### Adding New Ships or Roles

To add ships or modify roles:

1. Edit `settings.toml` and add ship names to appropriate role lists
2. For ships with multiple roles based on fitting, add to `special_cases` section
3. No code changes required - configuration is loaded dynamically
4. Restart the application to pick up changes

### Special Cases

Ships in the `special_cases` section can serve different roles depending on their fit_id. This is useful for:
- Dual-role ships (e.g., Vulture as DPS or Links)
- Doctrine-specific configurations
- Ships with non-standard fittings

**Example**: A Vulture with fit_id 369 is categorized as DPS, while fit_id 475 is categorized as Links.

### Fallback Behavior

If `settings.toml` is missing or a ship isn't found in the configuration:
- Function falls back to keyword pattern matching
- Ensures backward compatibility
- Prevents application crashes from configuration issues

## Testing Guidelines

- **Framework**: Add `pytest` for new tests; place files under `tests/` named `test_*.py`
- **What to test**: Data shape/columns, query correctness, and page-level helpers (mock DB where possible)
- **Run tests**: `uv run pytest -q` (after adding pytest)

## Commit & Pull Request Guidelines

- **Commits**: Follow Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`). Keep focused, imperative mood.
- **PRs**: Include a clear summary, linked issues, steps to validate, and screenshots/GIFs for UI changes. Note any DB/schema or config impacts.

## Security & Configuration Tips

- **Secrets**: Store Turso URLs/tokens in `.streamlit/secrets.toml`; never hard-code
- **Local env**: `.env` supported by `python-dotenv`
- **Git hygiene**: Large `*.db*` and `*.log` files are ignored—avoid committing generated artifacts

## Troubleshooting

### Database Connection Issues
- Verify local database files exist and are readable
- Check Turso credentials in secrets configuration
- Review sync logs in application logs

### Performance Issues
- Clear Streamlit cache: `st.cache_data.clear()`
- Check database sync status
- Monitor memory usage during large data operations

### Data Quality Issues
- Verify last sync timestamp
- Check for missing or corrupted local database files
- Review market data freshness in `marketstats` table

## Architecture Overview

Streamlit frontend (`app.py` + `pages/`) backed by local LibSQL replicas synced from Turso via `DatabaseConfig`. Business logic stays in modules; UI files should remain thin and delegate to helpers.

## TODOs

✅ COMPLETED - Refactored concurrency handling to use read-write locks (RWLock) instead of exclusive locks
  - Multiple concurrent reads now allowed
  - Writers maintain exclusive access
  - Sync operations properly block all access
  - Added comprehensive test coverage (12 new tests)

✅ COMPLETED - Updated tests to reflect current state of the codebase
  - All 36 tests passing (24 existing + 12 new)
  - Added test_rwlock.py for RWLock implementation
  - Added test_database_config_concurrency.py for DatabaseConfig concurrency behavior

✅ COMPLETED - Dynamic ship role categorization
  - Configuration-driven role assignment via settings.toml
  - Special case handling for dual-role ships based on fit_id
  - Comprehensive test suite with 36 tests (all passing)
  - Documentation updated
  - Test coverage: config validation, function behavior, fallback, integration
