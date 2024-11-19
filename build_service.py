import asyncio
from celery import Celery
from server_manager import MinecraftServerManager
import os
import logging
from typing import Optional, List, Dict
from mineflayer import build_structure

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

celery_app = Celery('minecraft_builder',
                    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'))

@celery_app.task(name='minecraft_builder.build_structure')
def build_structure_task(build_data):
    """Celery task wrapper for build_structure"""
    function_definition = build_data.get('function_definition')
    metadata = build_data.get('metadata', {})
    return build_structure(function_definition, metadata)

class MinecraftBuildService:
    def __init__(self, batch_size: int = 1):
        self.celery = celery_app
        self.server_manager = MinecraftServerManager()
        self.batch_size = batch_size
        self.is_running = False

    async def process_job(self, job_id: str, function_definition: str) -> Dict:
        """Process a single build job"""
        logger.info(f"Processing job {job_id}")
        try:
            result = await self.server_manager.process_build_job(job_id, function_definition)
            logger.info(f"Job {job_id} completed successfully")
            return result
        except Exception as e:
            logger.error(f"Job {job_id} failed: {str(e)}")
            return {
                'status': 'error',
                'error': str(e),
                'job_id': job_id
            }

    async def process_batch(self, jobs: List[Dict]) -> List[Dict]:
        """Process a batch of jobs concurrently"""
        tasks = []
        for job in jobs:
            task = asyncio.create_task(
                self.process_job(job['id'], job['function_definition'])
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results

    def get_pending_jobs(self) -> List[Dict]:
        """Get pending jobs from Celery queue"""
        inspector = self.celery.control.inspect()
        reserved = inspector.reserved() or {}
        
        jobs = []
        for worker, tasks in reserved.items():
            for task in tasks:
                if len(jobs) >= self.batch_size:
                    break
                build_data = task['args'][0] if task['args'] else {}
                jobs.append({
                    'id': task['id'],
                    'function_definition': build_data.get('function_definition'),
                    'metadata': build_data.get('metadata', {})
                })
        return jobs

    async def run(self):
        """Main service loop"""
        self.is_running = True
        logger.info(f"Starting build service with batch size {self.batch_size}")

        while self.is_running:
            try:
                # Get pending jobs
                jobs = self.get_pending_jobs()
                
                if not jobs:
                    logger.debug("No pending jobs, waiting...")
                    await asyncio.sleep(5)
                    continue

                logger.info(f"Processing batch of {len(jobs)} jobs")
                results = await self.process_batch(jobs)
                
                # Log results
                for job, result in zip(jobs, results):
                    if isinstance(result, Exception):
                        logger.error(f"Job {job['id']} failed with error: {str(result)}")
                    else:
                        logger.info(f"Job {job['id']} completed with status: {result['status']}")

            except Exception as e:
                logger.error(f"Error in service loop: {str(e)}")
                await asyncio.sleep(5)

    def stop(self):
        """Stop the service"""
        self.is_running = False
        logger.info("Stopping build service")

async def main():
    # Get batch size from environment variable or use default
    batch_size = int(os.getenv('BUILD_BATCH_SIZE', '1'))
    
    service = MinecraftBuildService(batch_size=batch_size)
    
    try:
        await service.run()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        service.stop()
        # Ensure all servers are cleaned up
        service.server_manager.stop_all_servers()

if __name__ == "__main__":
    asyncio.run(main()) 