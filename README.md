# Orchestrator

Orchestrator to spin up MC servers, run Minecraft agents, save buildings, and prepare for evaluation

Please join our [Discord](https://discord.gg/qmsrd7zH) to follow discussions, help plan the roadmap and hear about next steps

## Setup

### Prerequisites

- Docker
- Python 3.7+
- Docker Compose
- Redis

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

4. Ensure Redis is running:
  ```bash
  redis-server
  ```

5. Run the build service:
  ```bash
  python build_service.py
  ```

### Architecture

The orchestrator consists of several components:

1. `build_service.py`: The main service that listens to a Redis queue for build jobs.
2. `server_manager.py`: Manages Minecraft server instances using Docker.
3. `mineflayer.py`: Handles the Minecraft bot actions for building structures.
4. `test.py`: A test script to submit build jobs and monitor their progress.

### Usage

The orchestrator listens to a Redis queue for build jobs. Each job contains a function definition and metadata for building a structure in Minecraft.

1. Submit a job:
   Use `test.py` to submit a build job to the Redis queue.

   ```bash
   python test.py
   ```

2. Process jobs:
   The `build_service.py` script continuously listens for jobs in the queue and processes them:
   - Spins up a Minecraft server
   - Executes the build function
   - Saves the resulting structure
   - Cleans up the server

3. View results:
   The saved structures can be evaluated in the frontend (not included in this repository).

### Configuration

- Redis URL: Set the `REDIS_URL` environment variable (default: `redis://localhost:6379/0`)
- Redis Queue: Set the `REDIS_QUEUE` environment variable (default: `minecraft_builder`)
- Batch Size: Set the `BUILD_BATCH_SIZE` environment variable (default: `1`)

### Connecting to the Server (for debugging)

To view the building process in Minecraft:
1. Open Minecraft Java Edition
2. Go to Multiplayer
3. Add Server
4. Enter `localhost:<port>` as the server address (check logs for the assigned port)
5. Connect to the server

Note: Servers are automatically created and destroyed for each job, so connections are temporary.

### Development

- `server_manager.py`: Handles Minecraft server lifecycle using Docker
- `mineflayer.py`: Provides building functions using Mineflayer
- `build_service.py`: Main service for processing build jobs from the Redis queue
- `test.py`: Helper script for submitting test jobs and monitoring progress

Refer to individual files for more detailed documentation on their functionalities.
