import asyncio
from server_manager import MinecraftServerManager
import os
import logging
from typing import List, Dict
import time
import traceback
import redis
import sys
import json
from redis import Redis
import base64

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('minecraft_build_service.log')
    ]
)
logger = logging.getLogger(__name__)

# Redis configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
REDIS_QUEUE = 'minecraft_builder'

class MinecraftBuildService:
    def __init__(self, batch_size: int = 1):
        self.server_manager = MinecraftServerManager()
        self.batch_size = batch_size
        self.is_running = False
        self.redis_client = Redis.from_url(REDIS_URL)
        logger.info(f"MinecraftBuildService initialized with batch size: {batch_size}")

    def get_pending_jobs_from_redis(self) -> List[Dict]:
        """Get pending jobs directly from Redis queue"""
        logger.info("Checking for pending jobs in Redis")
        jobs = []
        
        while len(jobs) < self.batch_size:
            result = self.redis_client.brpop(REDIS_QUEUE, timeout=1)
            if result is None:
                break
            
            try:
                _, msg = result
                task = json.loads(msg)
                logger.info(f"Found task: {task}")
                
                # Decode the base64 encoded body
                body_decoded = base64.b64decode(task['body']).decode('utf-8')
                body = json.loads(body_decoded)
                
                build_data = body[0][0] if body and body[0] else {}
                jobs.append({
                    'id': task['headers']['id'],
                    'function_definition': build_data.get('function_definition'),
                    'metadata': build_data.get('metadata', {})
                })
            except json.JSONDecodeError:
                logger.error(f"Failed to decode message: {msg}")
            except Exception as e:
                logger.error(f"Error processing Redis message: {str(e)}")
        
        logger.info(f"Retrieved {len(jobs)} pending jobs from Redis")
        return jobs

    async def process_batch(self, jobs: List[Dict]) -> List[Dict]:
        """Process a batch of jobs concurrently"""
        tasks = []
        for job in jobs:
            logger.info(f"Creating task for job: {job['id']}")
            task = asyncio.create_task(
                self.server_manager.process_build_job(
                    job['id'],
                    job['function_definition'],
                    job['metadata']
                )
            )
            tasks.append(task)
        
        logger.info(f"Processing batch of {len(tasks)} tasks")
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        logger.info(f"Batch processing completed in {end_time - start_time:.2f} seconds")
        return results

    async def run(self):
        """Main service loop"""
        self.is_running = True
        logger.info(f"Starting build service with batch size {self.batch_size}")

        while self.is_running:
            try:
                jobs = self.get_pending_jobs_from_redis()
                
                if not jobs:
                    logger.info("No pending jobs, waiting for 5 seconds...")
                    await asyncio.sleep(5)
                    continue

                logger.info(f"Processing batch of {len(jobs)} jobs")
                results = await self.process_batch(jobs)
                
                for job, result in zip(jobs, results):
                    if isinstance(result, Exception):
                        logger.error(f"Job {job['id']} failed: {str(result)}")
                        logger.debug(f"Traceback for job {job['id']}: {traceback.format_exc()}")
                    else:
                        logger.info(f"Job {job['id']} completed successfully")

            except Exception as e:
                logger.error(f"Error in service loop: {str(e)}")
                logger.debug(f"Traceback: {traceback.format_exc()}")
                await asyncio.sleep(5)

    def stop(self):
        """Stop the service"""
        self.is_running = False
        logger.info("Stopping build service")

def check_redis_connection():
    try:
        redis_client = redis.Redis.from_url(REDIS_URL)
        redis_client.ping()
        logger.info("Successfully connected to Redis")
    except redis.ConnectionError:
        logger.error("Failed to connect to Redis. Make sure Redis is running.")
        sys.exit(1)

async def main():
    check_redis_connection()
    batch_size = int(os.getenv('BUILD_BATCH_SIZE', '1'))
    service = MinecraftBuildService(batch_size=batch_size)
    
    logger.info(f"Redis URL: {REDIS_URL}")
    logger.info(f"Redis Queue: {REDIS_QUEUE}")
    
    try:
        logger.info("Starting main service loop")
        await service.run()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.critical(f"Unexpected error in main loop: {str(e)}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
    finally:
        logger.info("Shutting down service")
        service.stop()
        logger.info("Stopping all Minecraft servers")
        service.server_manager.stop_all_servers()
        logger.info("Service shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())