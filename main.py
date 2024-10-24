import os
import subprocess
import time
import json
from server_manager import MinecraftServerManager
from dotenv import load_dotenv

def setup_mindcraft():
    """Clone and setup mindcraft repo"""
    if not os.path.exists("mindcraft"):
        subprocess.run(["git", "clone", "https://github.com/kolbytn/mindcraft.git"], check=True)
        
    os.chdir("mindcraft")
    subprocess.run(["npm", "install"], check=True)

def main():
    # Load environment variables
    load_dotenv()
    
    # Initialize server manager 
    manager = MinecraftServerManager()
    
    # Create minecraft server
    llm_id = "mindcraft_agent"
    print(f"\nCreating server for {llm_id}...")
    server_id = manager.create_server(llm_id)

    try:
        if manager.wait_for_server_ready(llm_id):
            print("\nPreparing building area...")
            manager.prepare_building_area(llm_id, size=25)
            
            # Get server info
            server_info = manager.servers[llm_id]
            port = server_info['port']
            
            # Setup and run mindcraft
            setup_mindcraft()
            
            # Load and update settings
            settings_file = "settings.js"
            if os.path.exists(settings_file):
                with open(settings_file, "r") as f:
                    content = f.read()
                content = content.replace("55916", str(port))
                content = content.replace("127.0.0.1", "localhost")
                with open(settings_file, "w") as f:
                    f.write(content)
                
            # Run mindcraft with environment variables
            print("\nStarting mindcraft agent...")
            env = os.environ.copy()
            subprocess.Popen(["node", "main.js"], env=env)
            
            # Keep running until interrupted
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nShutting down...")
                
    finally:
        print("\nCleaning up...")
        manager.stop_all_servers()
        os.chdir("..")  # Return to original directory
        
if __name__ == "__main__":
    main()
