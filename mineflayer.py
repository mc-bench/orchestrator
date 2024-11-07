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

def buildCreation(startX, startY, startZ):
    # Platform and base
    safeFill(startX - 20, startY, startZ - 20, startX + 20, startY + 4, startZ + 20, "smooth_quartz")
    
    # Main building footprint
    safeFill(startX - 10, startY + 4, startZ - 10, startX + 10, startY + 20, startZ + 10, "white_concrete")
    
    # Main entrance arch
    safeFill(startX - 4, startY + 4, startZ - 11, startX + 4, startY + 12, startZ - 10, "white_concrete")
    # Arch hollow
    safeFill(startX - 3, startY + 4, startZ - 11, startX + 3, startY + 10, startZ - 10, "air")
    
    # Four corner minarets
    def buildMinaret(x, z):
        safeFill(x - 2, startY + 4, z - 2, x + 2, startY + 30, z + 2, "white_concrete")
        # Minaret top
        safeFill(x - 3, startY + 30, z - 3, x + 3, startY + 32, z + 3, "smooth_quartz")
        # Minaret details
        for y in range(startY + 6, startY + 30, 4):
            safeFill(x - 2, y, z - 2, x + 2, y, z + 2, "light_gray_concrete")
    
    # Place minarets
    buildMinaret(startX - 15, startZ - 15)
    buildMinaret(startX + 15, startZ - 15)
    buildMinaret(startX - 15, startZ + 15)
    buildMinaret(startX + 15, startZ + 15)
    
    # Main dome base
    safeFill(startX - 8, startY + 20, startZ - 8, startX + 8, startY + 22, startZ + 8, "smooth_quartz")
    
    # Main dome
    def buildDome(centerX, centerY, centerZ, radius):
        for y in range(radius + 1):
            circleRadius = int((radius * radius - y * y) ** 0.5)
            for x in range(-circleRadius, circleRadius + 1):
                for z in range(-circleRadius, circleRadius + 1):
                    if x * x + z * z <= circleRadius * circleRadius:
                        safeSetBlock(centerX + x, centerY + y, centerZ + z, "white_concrete")
    
    # Build main dome
    buildDome(startX, startY + 22, startZ, 8)
    
    # Four smaller domes
    def buildSmallDome(x, z):
        buildDome(x, startY + 20, z, 4)
    
    # Place smaller domes
    buildSmallDome(startX - 8, startZ - 8)
    buildSmallDome(startX + 8, startZ - 8)
    buildSmallDome(startX - 8, startZ + 8)
    buildSmallDome(startX + 8, startZ + 8)
    
    # Decorative details
    # Windows
    for offset in range(-6, 7, 4):
        # Front and back windows
        safeFill(startX + offset - 1, startY + 8, startZ - 10, startX + offset + 1, startY + 12, startZ - 10, "glass_pane")
        safeFill(startX + offset - 1, startY + 8, startZ + 10, startX + offset + 1, startY + 12, startZ + 10, "glass_pane")
        
        # Side windows
        safeFill(startX - 10, startY + 8, startZ + offset - 1, startX - 10, startY + 12, startZ + offset + 1, "glass_pane")
        safeFill(startX + 10, startY + 8, startZ + offset - 1, startX + 10, startY + 12, startZ + offset + 1, "glass_pane")
    
    # Garden and water features
    # Water channels
    safeFill(startX - 18, startY + 4, startZ, startX + 18, startY + 4, startZ, "water")
    safeFill(startX, startY + 4, startZ - 18, startX, startY + 4, startZ + 18, "water")
    
    # Garden corners
    def buildGardenCorner(x, z):
        safeFill(x - 2, startY + 4, z - 2, x + 2, startY + 4, z + 2, "grass_block")
        safeSetBlock(x, startY + 5, z, "flowering_azalea")
    
    # Place garden corners
    buildGardenCorner(startX - 12, startZ - 12)
    buildGardenCorner(startX + 12, startZ - 12)
    buildGardenCorner(startX - 12, startZ + 12)
    buildGardenCorner(startX + 12, startZ + 12)
    
    # Decorative trim
    safeFill(startX - 10, startY + 19, startZ - 10, startX + 10, startY + 19, startZ + 10, "smooth_quartz_slab")
    
    # Top spire
    safeFill(startX - 1, startY + 30, startZ - 1, startX + 1, startY + 35, startZ + 1, "gold_block")
    safeSetBlock(startX, startY + 36, startZ, "lightning_rod")

def main():
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

    # Add event listeners for better debugging
    @On(bot, 'kicked')
    def on_kicked(this, reason, logged_in):
        print(f'Bot was kicked! Reason: {reason}')

    @On(bot, 'error')
    def on_error(this, err):
        print(f'Bot encountered an error: {err}')

    @On(bot, 'end')
    def on_end(this):
        print('Bot has disconnected from the server.')

    # Wait for login using 'once' function
    print('Waiting for login...')
    once(bot, 'spawn')
    print('Bot spawned')

    try:
        # Wait a short moment for the bot to fully spawn
        time.sleep(1)

        # Get bot position and offset it slightly for building
        pos = bot.entity.position
        startPos = {
            'x': int(pos.x) + 5,
            'y': int(pos.y) - 1,
            'z': int(pos.z) + 5
        }

        print(f"Starting build at position: {startPos}")

        # Test if the bot can execute a simple command
        bot.chat('/say Hello, world!')
        print('Sent command: /say Hello, world!')
        time.sleep(1)

        # Start the building process
        buildCreation(
            startPos['x'],
            startPos['y'],
            startPos['z']
        )

        print("Building complete, placing structure block...")

        # Save the structure
        saveStructure(STRUCTURE_NAME)

        print('Structure saved successfully!')

    except Exception as e:
        print('Error during building process:', e)
        raise e

    # Keep the bot running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Bot shutting down...")
        bot.quit()

# Run the main function
if __name__ == "__main__":
    main()
