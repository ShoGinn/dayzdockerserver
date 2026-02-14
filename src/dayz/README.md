# DayZ Server Python Package Structure

This package has been reorganized into a logical, modular structure for better maintainability and clarity.

## Directory Structure

```
src/dayz/
├── __init__.py          # Main package exports
├── py.typed             # Type hints marker
│
├── core/                # Business Logic & Management
│   ├── __init__.py
│   ├── server.py        # ServerControl, ServerManager
│   ├── mods.py          # ModManager
│   ├── maps.py          # MapManager
│   └── steam.py         # SteamCMD, SteamCredentials
│
├── services/            # Long-Running Service Processes
│   ├── __init__.py
│   ├── api.py           # FastAPI web service
│   └── supervisor.py    # DayZ process supervisor
│
├── utils/               # Shared Utilities & Data Structures
│   ├── __init__.py
│   ├── models.py        # Pydantic models, dataclasses, enums
│   ├── paths.py         # Centralized path configuration
│   ├── server_version.py # Binary version extraction
│   └── vdf.py           # Valve KeyValues parser
│
└── cli/                 # Command-Line Scripts
    ├── __init__.py
    ├── healthcheck.py   # Container health check
    └── init_volumes.py  # Volume initialization
```

## Module Organization

### Core (`core/`)
**Purpose**: Business logic for managing server components

- **server.py**: Server lifecycle control and configuration management
  - `ServerControl`: Start/stop/restart via supervisor socket
  - `ServerManager`: Installation, updates, configuration
  
- **mods.py**: Workshop mod management
  - `ModManager`: Install, activate, build mod command lines
  
- **maps.py**: Custom map installation
  - `MapManager`: Map installation from GitHub repos
  
- **steam.py**: Steam operations
  - `SteamCMD`: SteamCMD wrapper with privilege dropping
  - `SteamCredentials`: Steam login management

### Services (`services/`)
**Purpose**: Long-running service processes

- **api.py**: FastAPI REST API for server management
  - Unified endpoint for all server operations
  - Handles authentication and request routing
  
- **supervisor.py**: Process supervisor
  - `DayZSupervisor`: Manages DayZServer lifecycle
  - `DayZSupervisorClient`: Socket-based IPC client

### Utils (`utils/`)
**Purpose**: Shared utilities and data structures used across modules

- **models.py**: Data models
  - Pydantic models for API requests/responses
  - Dataclasses for internal data structures
  - Enums for states and commands
  
- **paths.py**: Path configuration
  - Centralized path definitions for all volumes
  - Environment variable handling
  
- **server_version.py**: Binary analysis
  - Extract DayZ version from server binary
  
- **vdf.py**: Steam config parsing
  - Parse Valve KeyValues format files

### CLI (`cli/`)
**Purpose**: Command-line interface scripts

- **healthcheck.py**: Container health check script
  - Verifies supervisor is running
  - Checks state file freshness
  
- **init_volumes.py**: Volume initialization script
  - Creates directory structure
  - Sets proper ownership and permissions

## Import Patterns

### From core modules

```python
from dayz.core import ServerManager, ModManager, MapManager, SteamCMD
```

### From utils

```python
from dayz.utils.models import ServerState, ModInfo
from dayz.utils.paths import SERVER_FILES, PROFILES_DIR
```

### From services (for embedding)

```python
from dayz.services import app  # FastAPI app
from dayz.services import DayZSupervisor  # Supervisor
```

### Within modules

```python
# All imports use absolute paths from dayz
from dayz.core.mods import ModManager
from dayz.utils.models import ServerConfig
from dayz.utils.paths import SERVER_FILES
from dayz.services.supervisor import DayZSupervisorClient
```

## Benefits of This Organization

1. **Clear Separation of Concerns**
   - Core business logic separated from infrastructure
   - Services are isolated and can run independently
   - Utilities are truly shared and reusable

2. **Logical Grouping**
   - Manager classes grouped together in `core/`
   - Service processes grouped in `services/`
   - Tools and helpers grouped in `utils/`
   - Scripts grouped in `cli/`

3. **Better Maintainability**
   - Easy to locate functionality by purpose
   - Related code lives together
   - Clear dependencies between modules

4. **Scalability**
   - Easy to add new managers to `core/`
   - Easy to add new services without affecting core logic
   - Easy to add new utilities without cluttering main package

5. **Testing**
   - Easier to test individual components in isolation
   - Clear boundaries for mocking dependencies
   - Utils can be tested independently

## Migration Notes

All imports have been updated to reflect the new structure. The public API exposed by the main `__init__.py` remains unchanged, so external code importing from `dayz` should continue to work without modifications.
