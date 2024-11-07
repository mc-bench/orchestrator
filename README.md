# Orchestrator

Orchestrator to spin up MC server, run Mindcraft agent, save building and run eval

Please join our [Discord](https://discord.gg/qmsrd7zH) to follow discussions, help plan the roadmap and hear about next steps

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

4. Run the server:
```bash
python server_manager.py
```
  
### Usage

The current server manager provides functionality to:
- Create Minecraft servers dynamically
- Manage RCON connections
- Execute commands remotely
- Prepare building areas with grid lines and corner markers
- Clean up servers automatically

Running `server_manager.py` directly will create a demo server that:
- Starts up a Minecraft server
- Prepares a 25x25 building area
- Keeps the server running for 30 seconds to let you explore the world

Basic example:

  ```python
  from server_manager import MinecraftServerManager

  manager = MinecraftServerManager()
  
  # Create a server instance
  llm_id = "my_agent"
  server_id = manager.create_server(llm_id)

  # Wait for server to be ready (10 minute timeout)
  if manager.wait_for_server_ready(llm_id):
      # Prepare a building area with grid lines and corner markers
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

### Connecting to the Server

To view the building process in Minecraft:
1. Open Minecraft Java Edition
2. Go to Multiplayer
3. Add Server
4. Enter `localhost:25565` as the server address
5. Connect to the server
