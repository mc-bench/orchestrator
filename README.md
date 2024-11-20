# Orchestrator

Orchestrator to spin up Minecraft servers, run Minecraft agents, save buildings, and prepare for evaluation.

Please join our [Discord](https://discord.gg/qmsrd7zH) to follow discussions, help plan the roadmap and hear about next steps.

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

## Architecture

The orchestrator consists of several key components:

1. `build_service.py`: The main service that listens to a Redis queue for build jobs.
2. `server_manager.py`: Manages Minecraft server instances using Docker.
3. `mineflayer.py`: Handles the Minecraft bot actions for building structures.
4. `test.py`: A test script to submit build jobs and monitor their progress.

### Detailed Component Overview

#### build_service.py

This is the core of the orchestrator. It:
- Initializes a connection to Redis
- Continuously polls a specified Redis queue for new build jobs
- When a job is received, it:
  1. Creates a new Minecraft server instance
  2. Waits for the server to be ready
  3. Prepares the building area
  4. Executes the build function using mineflayer
  5. Saves the resulting structure
  6. Cleans up the server
- Handles multiple jobs concurrently (configurable batch size)
- Implements error handling and logging

The job object in `build_service.py` contains:
- `id`: A unique identifier for the job
- `function_definition`: The Python code defining the build function
- `metadata`: Additional information about the build (e.g., name, author, description)

#### server_manager.py

This component manages the lifecycle of Minecraft servers:
- Creates Docker containers for Minecraft servers on-demand
- Manages server configurations (ports, RCON passwords, etc.)
- Provides methods to start, stop, and interact with servers
- Handles server readiness checks
- Prepares the building area within the Minecraft world

#### mineflayer.py

This script interfaces with the Minecraft server to perform building actions:
- Connects a bot to the Minecraft server
- Provides functions for placing blocks and filling areas
- Manages a command queue to prevent overwhelming the server
- Tracks coordinates of placed blocks
- Handles structure saving

In `mineflayer.py`, the build task is executed through the `build_structure` function, which takes:
- `function_definition`: The Python code to execute for building
- `metadata`: Additional information about the build

#### test.py

A utility script for testing the orchestrator:
- Submits a sample build job to the Redis queue
- Monitors the progress of the job
- Displays the results of the build

The `test.py` script creates a sample build job with:
- `function_definition`: A Python function that builds a simple house
- `metadata`: Information about the build (name, author, version, description, tags, creation time)

## Usage

The orchestrator listens to a Redis queue for build jobs. Each job contains a function definition and metadata for building a structure in Minecraft.

1. Submit a job:
   Use `test.py` to submit a build job to the Redis queue.

   ```bash
   python test.py
   ```

   This will:
   - Connect to Redis
   - Submit a predefined build job (a simple house)
   - Monitor the job's progress
   - Display the result

2. Process jobs:
   The `build_service.py` script continuously listens for jobs in the queue and processes them:
   - Spins up a Minecraft server using `server_manager.py`
   - Executes the build function using `mineflayer.py`
   - Saves the resulting structure
   - Cleans up the server

3. View results:
   The saved structures can be evaluated in the frontend (not included in this repository).

## Configuration

- Redis URL: Set the `REDIS_URL` environment variable (default: `redis://localhost:6379/0`)
- Redis Queue: Set the `REDIS_QUEUE` environment variable (default: `minecraft_builder`)
- Batch Size: Set the `BUILD_BATCH_SIZE` environment variable (default: `1`)

## Debugging

### Connecting to the Server

To view the building process in Minecraft:
1. Open Minecraft Java Edition
2. Go to Multiplayer
3. Add Server
4. Enter `localhost:<port>` as the server address (check logs for the assigned port)
5. Connect to the server

Note: Servers are automatically created and destroyed for each job, so connections are temporary.

### Logging

All components use Python's logging module. Check the console output and log files for detailed information about the orchestrator's operations.

## Development

When developing or extending the orchestrator:

- `server_manager.py`: Modify to change how Minecraft servers are managed (e.g., different Docker configurations, server settings)
- `mineflayer.py`: Extend to add new building capabilities or optimize existing ones
- `build_service.py`: Adjust job processing logic, error handling, or add new features to the main service
- `test.py`: Create new test scenarios or modify the existing one to test different aspects of the system

Refer to individual files for more detailed documentation on their functionalities and how they interact with each other.

## Flow of Operations

1. A build job is submitted to the Redis queue (e.g., via `test.py`)
2. `build_service.py` picks up the job from the queue
3. `build_service.py` uses `server_manager.py` to create a new Minecraft server
4. Once the server is ready, `build_service.py` calls functions in `mineflayer.py` to execute the build
5. `mineflayer.py` connects a bot to the server and performs the building operations
6. After building, the structure is saved, and the server is cleaned up
7. Results are logged and can be retrieved for evaluation

This cycle repeats for each job in the queue, allowing for scalable and automated Minecraft structure generation.
