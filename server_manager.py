import os
import uuid
import time
import docker
import secrets
import logging
from pathlib import Path
from mcrcon import MCRcon
from celery import Celery
from celery.result import AsyncResult

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MinecraftServerManager:
    def __init__(self, base_port=25565):
        self.base_port = base_port
        self.servers = {}
        self.client = docker.from_env()
        
        # Load base compose template
        try:
            with open('base-compose.yml', 'r') as f:
                self.base_template = f.read()
        except FileNotFoundError:
            logger.error("base-compose.yml not found. Ensure it exists in the current directory.")
            raise
        except IOError as e:
            logger.error(f"Error reading base-compose.yml: {e}")
            raise
        
        self.celery = Celery('minecraft_builder',
                             broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'))
        
        logger.info("MinecraftServerManager initialized successfully.")
        
    def create_server(self, llm_id):
        """Create a new Minecraft server for a given LLM"""
        server_id = str(uuid.uuid4())[:8]
        port = self.base_port + len(self.servers)
        rcon_port = port + 10
        rcon_password = secrets.token_urlsafe(16)

        logger.info(f"Creating new server for LLM ID: {llm_id}, Server ID: {server_id}")

        compose_content = self.base_template.format(
            llm_id=server_id,
            port=port,
            rcon_port=rcon_port,
            rcon_password=rcon_password
        )

        compose_file = f'compose-{server_id}.yml'
        try:
            with open(compose_file, 'w') as f:
                f.write(compose_content)
        except IOError as e:
            logger.error(f"Failed to write compose file {compose_file}: {e}")
            return None

        # Start the container with explicit project name
        project_name = f"mc-{server_id}"
        start_command = f'docker-compose -p {project_name} -f {compose_file} up -d'
        logger.info(f"Starting container with command: {start_command}")
        os.system(start_command)
        
        # Store server info
        self.servers[llm_id] = {
            'server_id': server_id,
            'port': port,
            'rcon_port': rcon_port,
            'compose_file': compose_file,
            'rcon_password': rcon_password,
            'project_name': project_name
        }

        # Wait for container to be running
        container_name = f"mc-llm-{server_id}"
        logger.info(f"Waiting for container {container_name} to start...")
        
        retries = 0
        max_retries = 10
        while retries < max_retries:
            try:
                containers = self.client.containers.list(
                    filters={"name": container_name}
                )
                if containers:
                    container = containers[0]
                    logger.info(f"Container {container_name} is {container.status}")
                    break
                retries += 1
                time.sleep(3)
            except docker.errors.NotFound:
                logger.warning(f"Waiting for container to be created... (attempt {retries+1}/{max_retries})")
                time.sleep(3)
                continue
        
        if retries >= max_retries:
            logger.error("Failed to find container after maximum retries")
            return None

        # Initial delay to let server start up
        logger.info("Waiting for initial server startup...")
        time.sleep(45)  # Increased initial wait time

        return server_id
        
    def wait_for_server_ready(self, llm_id, timeout=600):  # Increased timeout to 10 minutes
        """Wait for server to be ready with improved retry logic"""
        server_info = self.servers.get(llm_id)
        if not server_info:
            logger.error(f"No server found for LLM {llm_id}")
            raise ValueError(f"No server found for LLM {llm_id}")
            
        start_time = time.time()
        retry_interval = 10  # Start with 10 second retries
        max_retry_interval = 30  # Max retry interval of 30 seconds

        # Get container logs to check startup progress
        container_name = f"mc-llm-{server_info['server_id']}"
        try:
            container = self.client.containers.get(container_name)
        except docker.errors.NotFound:
            logger.error(f"Container {container_name} not found")
            return False
        
        while time.time() - start_time < timeout:
            try:
                # Check container logs for successful startup
                logs = container.logs(tail=50).decode('utf-8')
                if "Done" in logs:  # Server typically logs "Done!" when ready
                    logger.info("Server initialization detected in logs")
                    
                    # Try RCON connection
                    with MCRcon("localhost", 
                                server_info['rcon_password'],
                                port=server_info['rcon_port']) as rcon:
                        response = rcon.command("list")
                        if response:
                            logger.info(f"Server {llm_id} is ready!")
                            return True

            except ConnectionRefusedError:
                logger.info(f"Server starting up... (waiting {retry_interval}s)")
            except Exception as e:
                logger.warning(f"Waiting for server... ({str(e)})")
                
            # Check if container is still running
            container.reload()
            if container.status != "running":
                logger.error(f"Container stopped unexpectedly. Status: {container.status}")
                return False

            # Exponential backoff with max limit
            time.sleep(retry_interval)
            retry_interval = min(retry_interval * 1.5, max_retry_interval)
                    
        logger.error(f"Server {llm_id} failed to become ready within {timeout} seconds")
        return False

    def connect_rcon(self, llm_id):
        """Establish RCON connection to a server"""
        server_info = self.servers.get(llm_id)
        if not server_info:
            logger.error(f"No server found for LLM {llm_id}")
            raise ValueError(f"No server found for LLM {llm_id}")
            
        rcon = MCRcon(
            "localhost", 
            server_info['rcon_password'],
            port=server_info['rcon_port']
        )
        rcon.connect()
        return rcon
    
    def execute_command(self, llm_id, command):
        """Execute a command on the server via RCON"""
        try:
            with self.connect_rcon(llm_id) as rcon:
                response = rcon.command(command)
                logger.info(f"Command executed on server {llm_id}: {command}")
                return response
        except Exception as e:
            logger.error(f"Failed to execute command on server {llm_id}: {e}")
            return None

    def prepare_building_area(self, llm_id, size=50):
        """Prepare a flat area for building using vanilla commands"""
        logger.info(f"Preparing building area for server {llm_id}")
        with self.connect_rcon(llm_id) as rcon:
            commands = [
                # Clear the area
                f"fill ~-{size} ~-1 ~-{size} ~{size} ~50 ~{size} air",
                
                # Create base platform
                f"fill ~-{size} ~-1 ~-{size} ~{size} ~-1 ~{size} smooth_stone",
                
                # Create grid lines
                f"fill ~-{size} ~-1 ~0 ~{size} ~-1 ~0 gray_concrete",
                f"fill ~0 ~-1 ~-{size} ~0 ~-1 ~{size} gray_concrete",
                
                # Corner markers
                f"setblock ~{size} ~0 ~{size} red_concrete",
                f"setblock ~-{size} ~0 ~{size} blue_concrete", 
                f"setblock ~{size} ~0 ~-{size} green_concrete",
                f"setblock ~-{size} ~0 ~-{size} yellow_concrete",
                
                # Optimal visibility settings
                "time set day",
                "weather clear",
                "gamerule doWeatherCycle false",
                "gamerule doDaylightCycle false",
            ]
            
            for cmd in commands:
                response = rcon.command(cmd)
                logger.debug(f"Command '{cmd}': {response}")
                time.sleep(0.1)  # Small delay between commands

        logger.info(f"Building area prepared for server {llm_id}")

    def stop_server(self, llm_id):
        """Stop and cleanup a specific server"""
        server_info = self.servers.get(llm_id)
        if not server_info:
            logger.warning(f"No server found for LLM {llm_id} to stop")
            return
            
        # Stop the server using project name
        stop_command = f'docker-compose -p {server_info["project_name"]} -f {server_info["compose_file"]} down -v'
        logger.info(f"Stopping server {llm_id} with command: {stop_command}")
        os.system(stop_command)
        
        # Cleanup compose file
        if os.path.exists(server_info["compose_file"]):
            os.remove(server_info["compose_file"])
            logger.info(f"Removed compose file: {server_info['compose_file']}")
            
        del self.servers[llm_id]
        logger.info(f"Server {llm_id} stopped and cleaned up")
        
    def stop_all_servers(self):
        """Stop all servers"""
        logger.info("Stopping all servers")
        for llm_id in list(self.servers.keys()):
            self.stop_server(llm_id)
        logger.info("All servers stopped")

    def op_players(self, llm_id, players):
        """Give operator privileges to specified players"""
        try:
            with self.connect_rcon(llm_id) as rcon:
                for player in players:
                    response = rcon.command(f"op {player}")
                    logger.info(f"Opping player {player} on server {llm_id}: {response}")
        except Exception as e:
            logger.error(f"Failed to op players on server {llm_id}: {e}")

    async def process_build_job(self, job_id, function_definition, metadata=None):
        """Process a build job from start to finish"""
        logger.info(f"Starting build job {job_id}")
        try:
            # Create server
            server_id = self.create_server(job_id)
            if not server_id:
                raise Exception("Failed to create server")

            # Wait for server ready with increased timeout
            if not self.wait_for_server_ready(job_id, timeout=120):  # Increased to 2 minutes
                raise Exception("Server failed to start")

            # Prepare building area
            self.prepare_building_area(job_id)

            # Set environment variables for mineflayer
            server_info = self.servers[job_id]
            os.environ['HOST'] = 'localhost'
            os.environ['PORT'] = str(server_info['port'])
            os.environ['USERNAME'] = 'Builder'
            
            # Add additional delay for server stability
            logger.info("Waiting for server to stabilize...")
            time.sleep(20)  # Increased from 10 to 20 seconds

            # Verify server is accepting connections via RCON
            retries = 3
            while retries > 0:
                try:
                    with self.connect_rcon(job_id) as rcon:
                        response = rcon.command("list")
                        logger.info(f"Server response: {response}")
                        break
                except Exception as e:
                    logger.warning(f"RCON connection attempt failed ({retries} retries left): {e}")
                    retries -= 1
                    if retries == 0:
                        raise Exception("Server not responding to RCON commands")
                    time.sleep(5)

            # Execute build with retry logic
            from mineflayer import build_structure
            logger.info(f"Executing build for job {job_id}")
            result = build_structure(function_definition, metadata)
            
            if result['status'] == 'success':
                container_name = f"mc-llm-{server_info['server_id']}"
                # Update path to match Minecraft's structure directory
                structure_path = f"/data/world/generated/minecraft/structures/{result['structure_name']}.nbt"
                
                try:
                    container = self.client.containers.get(container_name)
                    
                    # Create local structures directory
                    os.makedirs('structures', exist_ok=True)
                    
                    # Try to copy the structure file
                    try:
                        bits, stat = container.get_archive(structure_path)
                        with open(f"structures/{result['structure_name']}.nbt", 'wb') as f:
                            for chunk in bits:
                                f.write(chunk)
                        logger.info(f"Structure exported to structures/{result['structure_name']}.nbt")
                        result['structure_file'] = f"structures/{result['structure_name']}.nbt"
                    except Exception as e:
                        logger.error(f"Failed to export structure: {e}")
                        # List all contents recursively to help debug
                        try:
                            exec_result = container.exec_run("find /data/world -type f -name '*.nbt'")
                            logger.info(f"Found .nbt files: {exec_result.output.decode()}")
                        except Exception as dir_error:
                            logger.error(f"Failed to search for .nbt files: {dir_error}")
                        raise e

                except Exception as e:
                    logger.error(f"Failed to export structure: {e}")
                    result['structure_export_error'] = str(e)
                    # Add more detailed error information
                    logger.error(f"Container name: {container_name}")
                    logger.error(f"Attempted paths: {structure_path}")
                    
                    # List all contents recursively to find the structure file
                    try:
                        exec_result = container.exec_run("find /data/world -name '*.nbt'")
                        logger.info(f"Found .nbt files: {exec_result.output.decode()}")
                    except Exception as dir_error:
                        logger.error(f"Failed to search for .nbt files: {dir_error}")
            
            return result

        except Exception as e:
            logger.error(f"Build job {job_id} failed: {str(e)}")
            return {
                'status': 'error',
                'error': str(e),
                'metadata': metadata
            }
        finally:
            # Always cleanup the server
            logger.info(f"Cleaning up server for job {job_id}")
            self.stop_server(job_id)
