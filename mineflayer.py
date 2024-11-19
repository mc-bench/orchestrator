import time
from javascript import require, On, Once, AsyncTask, once, off
import os
from threading import Thread

mineflayer = require('mineflayer')
Vec3 = require('vec3').Vec3
Buffer = require('buffer').Buffer or bot._global.Buffer

# Environment variables with defaults
HOST = os.getenv('HOST', '127.0.0.1')
PORT = int(os.getenv('PORT', '25565'))
VERSION = os.getenv('VERSION', '1.20.4')
USERNAME = os.getenv('USERNAME', 'builder')
DELAY = int(os.getenv('DELAY', '1000'))  # Increased delay to prevent spamming
STRUCTURE_NAME = os.getenv('STRUCTURE_NAME', f'structure_{time.strftime("%Y-%m-%dT%H-%M-%S")}')

def build_structure(function_definition):
    """Build a structure from a function definition"""
    try:
        global bot, commandQueue, coordinateTracker

        BOT_USERNAME = f'Builder'

        bot = mineflayer.createBot({
            'host': HOST,
            'port': PORT,
            'username': BOT_USERNAME,
            'version': VERSION,
            'hideErrors': False
        })

        commandQueue = CommandQueue()
        coordinateTracker = CoordinateTracker()

        # Set up event handlers
        @On(bot, 'kicked')
        def on_kicked(this, reason, logged_in):
            print(f'Bot was kicked! Reason: {reason}')

        @On(bot, 'error')
        def on_error(this, err):
            print(f'Bot encountered an error: {err}')

        # Wait for spawn
        print('Waiting for login...')
        once(bot, 'spawn')
        print('Bot spawned')

        # Short delay for spawn
        time.sleep(1)

        # Execute the build
        buildCreation(function_definition)

        # Save structure
        structure_name = STRUCTURE_NAME
        saveStructure(structure_name)

        # Wait for commands to complete
        while commandQueue.isProcessing:
            time.sleep(0.5)

        # Clean exit
        bot.quit()
        
        return {
            'status': 'success',
            'structure_name': structure_name,
            'dimensions': coordinateTracker.getDimensions()
        }

    except Exception as e:
        print(f'Build failed: {str(e)}')
        if 'bot' in globals():
            bot.quit()
        return {
            'status': 'error',
            'error': str(e)
        }

# Command queue system
class CommandQueue:
    def __init__(self, delay=DELAY):
        self.queue = []
        self.isProcessing = False
        self.DELAY = delay

    def add(self, command):
        self.queue.append(command)
        if not self.isProcessing:
            self.isProcessing = True
            thread = Thread(target=self.processQueue)
            thread.start()

    def processQueue(self):
        while self.queue:
            command = self.queue.pop(0)
            try:
                bot.chat(command)
                print(f'Executed command: {command}')
            except Exception as e:
                print(f'Error executing command "{command}": {e}')
            time.sleep(self.DELAY / 1000)
        self.isProcessing = False

# Coordinate tracking system
class CoordinateTracker:
    def __init__(self):
        self.coordinates = []
        self.boundingBox = None

    def addCoordinate(self, x, y, z):
        self.coordinates.append({'x': x, 'y': y, 'z': z})
        self.updateBoundingBox()

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

    def getBoundingBox(self):
        return self.boundingBox

    def getDimensions(self):
        if not self.boundingBox:
            return None
        return {
            'width': self.boundingBox['max']['x'] - self.boundingBox['min']['x'] + 1,
            'height': self.boundingBox['max']['y'] - self.boundingBox['min']['y'] + 1,
            'depth': self.boundingBox['max']['z'] - self.boundingBox['min']['z'] + 1
        }

def safeSetBlock(x, y, z, blockType, options={}):
    # Ensure coordinates are integers
    x = int(x)
    y = int(y)
    z = int(z)
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
    except Exception as e:
        print(f"Error placing block at {x} {y} {z}: {e}")
        raise e

def safeFill(x1, y1, z1, x2, y2, z2, blockType, options={}):
    # Ensure coordinates are integers
    x1 = int(x1)
    y1 = int(y1)
    z1 = int(z1)
    x2 = int(x2)
    y2 = int(y2)
    z2 = int(z2)
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
    except Exception as e:
        print(f"Error filling from ({x1},{y1},{z1}) to ({x2},{y2},{z2}): {e}")
        raise e

def saveStructure(name):
    boundingBox = coordinateTracker.getBoundingBox()
    if not boundingBox:
        print('No blocks placed yet to create structure')
        return

    min_coords = f"{boundingBox['min']['x']} {boundingBox['min']['y']} {boundingBox['min']['z']}"
    max_coords = f"{boundingBox['max']['x']} {boundingBox['max']['y']} {boundingBox['max']['z']}"

    commandQueue.add(f"/structure save {name} {min_coords} {max_coords}")

def buildCreation(functionDefinition):
    exec(functionDefinition)
