import time
import logging
from javascript import require, On, Once, AsyncTask, once, off
import os
from threading import Thread

mineflayer = require('mineflayer')
Vec3 = require('vec3').Vec3
Buffer = require('buffer').Buffer or bot._global.Buffer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Environment variables with defaults
HOST = os.getenv('HOST', '127.0.0.1')
PORT = int(os.getenv('PORT', '25565'))
VERSION = os.getenv('VERSION', '1.20.4')
USERNAME = os.getenv('USERNAME', 'builder')
DELAY = int(os.getenv('DELAY', '1000'))  # Increased delay to prevent spamming
STRUCTURE_NAME = os.getenv('STRUCTURE_NAME', f'structure_{time.strftime("%Y-%m-%dT%H-%M-%S")}')

def build_structure(function_definition, metadata=None):
    """Build a structure from a function definition"""
    try:
        global bot, commandQueue, coordinateTracker

        logger.info("Starting build_structure function")
        
        # Log metadata if provided
        if metadata:
            logger.info(f"Building structure: {metadata.get('name', 'Unnamed')}")
            logger.info(f"Author: {metadata.get('author', 'Unknown')}")
            logger.info(f"Description: {metadata.get('description', 'No description')}")

        BOT_USERNAME = f'Builder'

        # Add retry logic for bot connection
        max_retries = 3
        retry_delay = 5
        last_error = None

        for attempt in range(max_retries):
            try:
                logger.info(f"Attempting to connect bot (attempt {attempt + 1}/{max_retries})")
                bot = mineflayer.createBot({
                    'host': HOST,
                    'port': PORT,
                    'username': BOT_USERNAME,
                    'version': VERSION,
                    'hideErrors': False,
                    'connectTimeout': 30000,  # 30 seconds timeout
                })
                logger.info("Bot connection successful")
                break
            except Exception as e:
                last_error = e
                logger.error(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    raise Exception(f"Failed to connect after {max_retries} attempts: {last_error}")

        commandQueue = CommandQueue()
        coordinateTracker = CoordinateTracker()

        # Set up event handlers
        @On(bot, 'kicked')
        def on_kicked(this, reason, logged_in):
            logger.warning(f'Bot was kicked! Reason: {reason}')

        @On(bot, 'error')
        def on_error(this, err):
            logger.error(f'Bot encountered an error: {err}')

        # Wait for spawn with timeout
        logger.info('Waiting for login...')
        spawn_timeout = 30  # 30 seconds timeout
        spawn_start = time.time()
        while time.time() - spawn_start < spawn_timeout:
            try:
                once(bot, 'spawn')
                logger.info('Bot spawned successfully')
                break
            except Exception as e:
                if time.time() - spawn_start >= spawn_timeout:
                    raise Exception(f"Bot spawn timeout after {spawn_timeout} seconds")
                time.sleep(1)

        # Short delay for spawn
        time.sleep(1)

        # Execute the build
        logger.info("Starting build execution")
        buildCreation(function_definition)
        
        # Wait for commands to complete
        logger.info("Waiting for build commands to complete")
        while commandQueue.isProcessing:
            time.sleep(0.5)

        # Save structure
        structure_name = STRUCTURE_NAME
        logger.info(f"Saving structure as: {structure_name}")
        saveStructure(structure_name)

        # Wait for commands to complete
        logger.info("Waiting for all commands to complete")
        while commandQueue.isProcessing:
            time.sleep(0.5)

        # Clean exit
        logger.info("Build completed, disconnecting bot")
        bot.quit()
        
        dimensions = coordinateTracker.getDimensions()
        logger.info(f"Build dimensions: {dimensions}")
        
        return {
            'status': 'success',
            'structure_name': structure_name,
            'dimensions': dimensions,
            'metadata': metadata
        }

    except Exception as e:
        logger.exception(f'Build failed: {str(e)}')
        if 'bot' in globals():
            bot.quit()
        return {
            'status': 'error',
            'error': str(e),
            'metadata': metadata
        }

# Command queue system
class CommandQueue:
    def __init__(self, delay=DELAY):
        self.queue = []
        self.isProcessing = False
        self.DELAY = delay
        self.logger = logging.getLogger(__name__ + '.CommandQueue')

    def add(self, command):
        self.queue.append(command)
        self.logger.debug(f"Added command to queue: {command}")
        if not self.isProcessing:
            self.isProcessing = True
            thread = Thread(target=self.processQueue)
            thread.start()

    def processQueue(self):
        self.logger.info("Started processing command queue")
        while self.queue:
            command = self.queue.pop(0)
            try:
                bot.chat(command)
                self.logger.info(f'Executed command: {command}')
            except Exception as e:
                self.logger.error(f'Error executing command "{command}": {e}')
            time.sleep(self.DELAY / 1000)
        self.isProcessing = False
        self.logger.info("Finished processing command queue")

# Coordinate tracking system
class CoordinateTracker:
    def __init__(self):
        self.coordinates = []
        self.boundingBox = None
        self.logger = logging.getLogger(__name__ + '.CoordinateTracker')

    def addCoordinate(self, x, y, z):
        self.coordinates.append({'x': x, 'y': y, 'z': z})
        self.updateBoundingBox()
        self.logger.debug(f"Added coordinate: ({x}, {y}, {z})")

    def updateBoundingBox(self):
        if not self.coordinates:
            return

        xs = [c['x'] for c in self.coordinates]
        ys = [c['y'] for c in self.coordinates]
        zs = [c['z'] for c in self.coordinates]

        self.boundingBox = {
            'min': {
                'x': min(xs),
                'y': min(ys),
                'z': min(zs)
            },
            'max': {
                'x': max(xs),
                'y': max(ys),
                'z': max(zs)
            }
        }
        self.logger.debug(f"Updated bounding box: {self.boundingBox}")

    def getBoundingBox(self):
        return self.boundingBox

    def getDimensions(self):
        if not self.boundingBox:
            return None
        dimensions = {
            'width': self.boundingBox['max']['x'] - self.boundingBox['min']['x'] + 1,
            'height': self.boundingBox['max']['y'] - self.boundingBox['min']['y'] + 1,
            'depth': self.boundingBox['max']['z'] - self.boundingBox['min']['z'] + 1
        }
        self.logger.info(f"Structure dimensions: {dimensions}")
        return dimensions

def safeSetBlock(x, y, z, blockType, options={}):
    logger = logging.getLogger(__name__ + '.safeSetBlock')
    # Ensure coordinates are integers
    x, y, z = map(int, (x, y, z))
    try:
        # Add minecraft: namespace if not present
        fullBlockType = blockType if ':' in blockType else f'minecraft:{blockType}'
        command = f"/setblock {x} {y} {z} {fullBlockType}"

        # Add block states if provided
        blockStates = options.get('blockStates')
        if blockStates and blockStates.keys():
            stateString = ','.join([f"{key}={value}" for key, value in blockStates.items()])
            command += f'[{stateString}]'

        # Add placement mode if provided
        mode = options.get('mode')
        if mode:
            validModes = ['replace', 'destroy', 'keep']
            if mode not in validModes:
                raise ValueError(f"Invalid placement mode: {mode}. Must be one of: {', '.join(validModes)}")
            command += f' {mode}'

        commandQueue.add(command)
        coordinateTracker.addCoordinate(x, y, z)
        logger.debug(f"Block placed at ({x}, {y}, {z}): {fullBlockType}")
    except Exception as e:
        logger.error(f"Error placing block at {x} {y} {z}: {e}")
        raise e

def safeFill(x1, y1, z1, x2, y2, z2, blockType, options={}):
    logger = logging.getLogger(__name__ + '.safeFill')
    # Ensure coordinates are integers
    x1, y1, z1, x2, y2, z2 = map(int, (x1, y1, z1, x2, y2, z2))
    try:
        # Add minecraft: namespace if not present
        fullBlockType = blockType if ':' in blockType else f'minecraft:{blockType}'
        command = f"/fill {x1} {y1} {z1} {x2} {y2} {z2} {fullBlockType}"

        # Add block states if provided
        blockStates = options.get('blockStates')
        if blockStates and blockStates.keys():
            stateString = ','.join([f"{key}={value}" for key, value in blockStates.items()])
            command += f'[{stateString}]'

        # Handle fill modes and replace filter
        mode = options.get('mode')
        if mode:
            validModes = ['destroy', 'hollow', 'keep', 'outline', 'replace']
            if mode not in validModes:
                raise ValueError(f"Invalid fill mode: {mode}. Must be one of: {', '.join(validModes)}")
            command += f' {mode}'

            # Handle replace filter if specified
            if mode == 'replace' and options.get('replaceFilter'):
                fullReplaceFilter = options['replaceFilter'] if ':' in options['replaceFilter'] else f"minecraft:{options['replaceFilter']}"
                command += f' {fullReplaceFilter}'

                # Add replace filter block states if provided
                replaceFilterStates = options.get('replaceFilterStates')
                if replaceFilterStates and replaceFilterStates.keys():
                    filterStateString = ','.join([f"{key}={value}" for key, value in replaceFilterStates.items()])
                    command += f'[{filterStateString}]'

        commandQueue.add(command)

        # Track corners of the filled region
        for x in [x1, x2]:
            for y in [y1, y2]:
                for z in [z1, z2]:
                    coordinateTracker.addCoordinate(x, y, z)
        
        logger.debug(f"Fill command executed from ({x1},{y1},{z1}) to ({x2},{y2},{z2}): {fullBlockType}")
    except Exception as e:
        logger.error(f"Error filling from ({x1},{y1},{z1}) to ({x2},{y2},{z2}): {e}")
        raise e

def saveStructure(name):
    logger = logging.getLogger(__name__ + '.saveStructure')
    boundingBox = coordinateTracker.getBoundingBox()
    if not boundingBox:
        logger.warning('No blocks placed yet to create structure')
        return

    min_coords = f"{boundingBox['min']['x']} {boundingBox['min']['y']} {boundingBox['min']['z']}"
    max_coords = f"{boundingBox['max']['x']} {boundingBox['max']['y']} {boundingBox['max']['z']}"

    # Save structure with include-entities false to reduce file size
    command = f"/structure save {name} {min_coords} {max_coords} false disk"
    commandQueue.add(command)
    logger.info(f"Structure saved: {name} from {min_coords} to {max_coords}")
    
    print("Please check the structure file in the world/structures directory")
    time.sleep(50000000)
    
    # Verify the save worked by attempting to load it
    verify_command = f"/structure load {name} {min_coords}"
    commandQueue.add(verify_command)

def buildCreation(functionDefinition):
    logger = logging.getLogger(__name__ + '.buildCreation')
    logger.info("Starting build creation")
    try:
        exec(functionDefinition)
        logger.info("Build creation completed successfully")
    except Exception as e:
        logger.error(f"Error during build creation: {e}")
        raise e
