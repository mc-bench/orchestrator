# Orchestrator

Orchestrator to spin up MC server, run Mindcraft agent, save building and run eval

## Setup

### Prerequisites

- Docker
- Python 3.7+
- Docker Compose

### Installation

1. Clone the repository:
  ```bash
  git clone <repository-url>
  cd orchestrator
  ```

2. Create and activate a virtual environment:
  ```bash
  python -m venv .venv
  source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
  ```

3. Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```

### Usage

The current server manager provides functionality to:
- Create Minecraft servers dynamically
- Manage RCON connections
- Execute commands remotely
- Prepare building areas
- Clean up servers automatically

Basic example:

  ```python
  from server_manager import MinecraftServerManager

  manager = MinecraftServerManager()
  
  # Create a server instance
  llm_id = "my_agent"
  server_id = manager.create_server(llm_id)

  # Wait for server to be ready
  if manager.wait_for_server_ready(llm_id):
      # Prepare a 50x50 building area
      manager.prepare_building_area(llm_id, size=50)

  # Clean up when done
  manager.stop_server(llm_id)
  ```

### Configuration

The server uses Docker containers with the following default settings:
- Base port: 25565 (Minecraft)
- RCON enabled
- Creative mode
- Paper server type
- Minecraft version 1.20.4
- Optimized JVM settings for performance
