from celery import Celery
from celery.result import AsyncResult
import time
import os
import redis
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Redis client
try:
    redis_client = redis.Redis.from_url(os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'))
    redis_client.ping()  # Test the connection
except redis.ConnectionError:
    print("Error: Unable to connect to Redis. Please ensure Redis is running.")
    exit(1)

# Initialize Celery client
CELERY_QUEUE = 'minecraft_builder'
celery_app = Celery('minecraft_builder',
                    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
                    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'))
celery_app.conf.update(
    task_default_queue=CELERY_QUEUE,
)

# Example build function that creates a small house
build_data = {
    'function_definition': """
# Floor
for x in range(5):
    for z in range(5):
        safeSetBlock(x, 0, z, 'stone')

# Walls
for y in range(4):
    for x in range(5):
        safeSetBlock(x, y+1, 0, 'oak_planks')  # Front wall
        safeSetBlock(x, y+1, 4, 'oak_planks')  # Back wall
    for z in range(5):
        safeSetBlock(0, y+1, z, 'oak_planks')  # Left wall
        safeSetBlock(4, y+1, z, 'oak_planks')  # Right wall

# Door
safeSetBlock(2, 1, 0, 'oak_door', {'half': 'lower'})
safeSetBlock(2, 2, 0, 'oak_door', {'half': 'upper'})

# Windows
safeSetBlock(1, 2, 0, 'glass')
safeSetBlock(3, 2, 0, 'glass')

# Roof
for x in range(5):
    for z in range(5):
        safeSetBlock(x, 4, z, 'oak_planks')""",
    'metadata': {
        'name': 'Simple House',
        'author': 'TestBuilder', 
        'version': '1.0',
        'description': 'A basic 5x5 house with door and windows',
        'tags': ['house', 'basic', 'test'],
        'created_at': time.strftime("%Y-%m-%dT%H-%M-%S")
    }
}

def submit_and_monitor_job():
    print("Submitting build job...")
    
    try:
        # Submit the job
        logger.info("About to submit Celery task")
        logger.info(f"Celery app config: {celery_app.conf}")
        result = celery_app.send_task(
            'minecraft_builder.build_structure',
            args=[build_data],
            queue=CELERY_QUEUE
        )
        
        task_id = result.id
        logger.info(f"Job submitted with ID: {task_id}")
        
        # Monitor the job
        while True:
            try:
                # Check job status using AsyncResult
                async_result = AsyncResult(task_id, app=celery_app)
                status = async_result.status
                print(f"Current status: {status}")
                
                if status in ['SUCCESS', 'FAILURE']:
                    # Get the result if available
                    try:
                        build_result = async_result.get(timeout=1)
                        print("\nBuild Result:")
                        print(f"Status: {build_result.get('status')}")
                        print(f"Structure Name: {build_result.get('structure_name')}")
                        print(f"Dimensions: {build_result.get('dimensions')}")
                        if build_result.get('error'):
                            print(f"Error: {build_result.get('error')}")
                    except Exception as e:
                        print(f"Error getting result: {e}")
                    break
                
                time.sleep(5)  # Wait 5 seconds before checking again
                
            except KeyboardInterrupt:
                print("\nMonitoring interrupted by user")
                break
            except Exception as e:
                print(f"Error monitoring job: {e}")
                break
    except Exception as e:
        print(f"Error submitting job: {e}")

def check_redis_queue():
    redis_client = redis.Redis.from_url(os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'))
    queue_key = f'celery:{CELERY_QUEUE}'
    queue_length = redis_client.llen(queue_key)
    logger.info(f"Current length of Redis queue '{queue_key}': {queue_length}")

if __name__ == "__main__":
    logger.info("Starting test script")
    print("Starting test...")
    print("\nMake sure you have:")
    print("1. Redis server running")
    print("2. Build service running (python build_service.py)")
    print("3. Docker daemon running")
    
    input("\nPress Enter to continue...")
    
    submit_and_monitor_job()
    check_redis_queue() 