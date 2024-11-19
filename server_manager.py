import os
import uuid
import time
import docker
import secrets
from pathlib import Path
from mcrcon import MCRcon
from celery import Celery
from celery.result import AsyncResult

class MinecraftServerManager:
    def __init__(self, base_port=25565):
        self.base_port = base_port
        self.servers = {}
        self.client = docker.from_env()
        
        # Load base compose template
        with open('base-compose.yml', 'r') as f:
            self.base_template = f.read()
            
        self.celery = Celery('minecraft_builder',
                            broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'))
        
    def create_server(self, llm_id):
        """Create a new Minecraft server for a given LLM"""
        server_id = str(uuid.uuid4())[:8]
        port = self.base_port + len(self.servers)
        rcon_port = port + 10
        rcon_password = secrets.token_urlsafe(16)

        compose_content = self.base_template.format(
            llm_id=server_id,
            port=port,
            rcon_port=rcon_port,
            rcon_password=rcon_password
        )

        compose_file = f'compose-{server_id}.yml'
        with open(compose_file, 'w') as f:
            f.write(compose_content)

        # Start the container with explicit project name
        project_name = f"mc-{server_id}"
        os.system(f'docker-compose -p {project_name} -f {compose_file} up -d')
        
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
        print(f"Waiting for container {container_name} to start...")
        
        retries = 0
        max_retries = 10
        while retries < max_retries:
            try:
                containers = self.client.containers.list(
                    filters={"name": container_name}
                )
                if containers:
                    container = containers[0]
                    print(f"Container {container_name} is {container.status}")
                    break
                retries += 1
                time.sleep(3)
            except docker.errors.NotFound:
                print(f"Waiting for container to be created... (attempt {retries+1}/{max_retries})")
                time.sleep(3)
                continue
        
        if retries >= max_retries:
            print("Failed to find container after maximum retries")
            return None

        # Initial delay to let server start up
        print("Waiting for initial server startup...")
        time.sleep(45)  # Increased initial wait time

        return server_id
        
    def wait_for_server_ready(self, llm_id, timeout=600):  # Increased timeout to 10 minutes
        """Wait for server to be ready with improved retry logic"""
        server_info = self.servers.get(llm_id)
        if not server_info:
            raise ValueError(f"No server found for LLM {llm_id}")
            
        start_time = time.time()
        retry_interval = 10  # Start with 10 second retries
        max_retry_interval = 30  # Max retry interval of 30 seconds

        # Get container logs to check startup progress
        container_name = f"mc-llm-{server_info['server_id']}"
        try:
            container = self.client.containers.get(container_name)
        except docker.errors.NotFound:
            print(f"Container {container_name} not found")
            return False
        
        while time.time() - start_time < timeout:
            try:
                # Check container logs for successful startup
                logs = container.logs(tail=50).decode('utf-8')
                if "Done" in logs:  # Server typically logs "Done!" when ready
                    print("Server initialization detected in logs")
                    
                    # Try RCON connection
                    with MCRcon("localhost", 
                              server_info['rcon_password'],
                              port=server_info['rcon_port']) as rcon:
                        response = rcon.command("list")
                        if response:
                            print(f"Server {llm_id} is ready!")
                            return True

            except ConnectionRefusedError:
                print(f"Server starting up... (waiting {retry_interval}s)")
            except Exception as e:
                print(f"Waiting for server... ({str(e)})")
                
            # Check if container is still running
            container.reload()
            if container.status != "running":
                print(f"Container stopped unexpectedly. Status: {container.status}")
                return False

            # Exponential backoff with max limit
            time.sleep(retry_interval)
            retry_interval = min(retry_interval * 1.5, max_retry_interval)
                    
        print(f"Server {llm_id} failed to become ready within {timeout} seconds")
        return False

    def connect_rcon(self, llm_id):
        """Establish RCON connection to a server"""
        server_info = self.servers.get(llm_id)
        if not server_info:
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
                return response
        except Exception as e:
            print(f"Failed to execute command on server {llm_id}: {e}")
            return None

    def prepare_building_area(self, llm_id, size=50):
        """Prepare a flat area for building using vanilla commands"""
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
                print(f"Command '{cmd}': {response}")
                time.sleep(0.1)  # Small delay between commands

    def stop_server(self, llm_id):
        """Stop and cleanup a specific server"""
        server_info = self.servers.get(llm_id)
        if not server_info:
            return
            
        # Stop the server using project name
        os.system(f'docker-compose -p {server_info["project_name"]} -f {server_info["compose_file"]} down -v')
        
        # Cleanup compose file
        if os.path.exists(server_info["compose_file"]):
            os.remove(server_info["compose_file"])
            
        del self.servers[llm_id]
        
    def stop_all_servers(self):
        """Stop all servers"""
        for llm_id in list(self.servers.keys()):
            self.stop_server(llm_id)

    def op_players(self, llm_id, players):
        """Give operator privileges to specified players"""
        try:
            with self.connect_rcon(llm_id) as rcon:
                for player in players:
                    response = rcon.command(f"op {player}")
                    print(f"Opping {player}: {response}")
        except Exception as e:
            print(f"Failed to op players on server {llm_id}: {e}")

    async def process_build_job(self, job_id, function_definition, metadata=None):
        """Process a build job from start to finish"""
        try:
            # Create server
            server_id = self.create_server(job_id)
            if not server_id:
                raise Exception("Failed to create server")

            # Wait for server ready
            if not self.wait_for_server_ready(job_id):
                raise Exception("Server failed to start")

            # Prepare building area
            self.prepare_building_area(job_id)

            # Submit build task with proper format
            build_data = {
                'function_definition': function_definition,
                'metadata': metadata or {}
            }
            
            task = self.celery.send_task(
                'minecraft_builder.build_structure',  # Matches the task name in build_service.py
                args=[build_data]                    # Proper argument format
            )

            # Wait for build completion
            result = AsyncResult(task.id, app=self.celery)
            build_result = result.get(timeout=600)  # 10 minute timeout

            if build_result['status'] != 'success':
                raise Exception(f"Build failed: {build_result.get('error')}")

            return build_result

        finally:
            # Always cleanup the server
            self.stop_server(job_id)
