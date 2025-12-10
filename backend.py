import asyncio
import websockets
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file (for local testing)
load_dotenv()

# --- Configuration ---
PORT = int(os.environ.get("PORT", 8765)) # Use environment PORT or default to 8765
HOST = "0.0.0.0" # Listen on all interfaces

# --- Global State ---
CONNECTIONS = set()
MAX_HISTORY = 50
CHAT_HISTORY = []

# --- Core Server Logic ---

async def register(websocket):
    """Adds a new client and sends history."""
    CONNECTIONS.add(websocket)
    print(f"Client connected. Total: {len(CONNECTIONS)}")
    
    # Send history to the new client
    try:
        for message in CHAT_HISTORY:
            await websocket.send(json.dumps(message))
    except websockets.exceptions.ConnectionClosed:
        pass

async def unregister(websocket):
    """Removes a client."""
    CONNECTIONS.remove(websocket)
    print(f"Client disconnected. Total: {len(CONNECTIONS)}")

async def broadcast(message):
    """Sends a message to all connected clients."""
    global CHAT_HISTORY
    
    # Update history
    CHAT_HISTORY.append(message)
    if len(CHAT_HISTORY) > MAX_HISTORY:
        CHAT_HISTORY = CHAT_HISTORY[1:] 

    # Prepare message for sending
    message_json = json.dumps(message)
    
    # Broadcast concurrently, handling potential disconnections
    disconnected_clients = []
    
    if CONNECTIONS:
        awaitables = [conn.send(message_json) for conn in CONNECTIONS]
        results = await asyncio.gather(*awaitables, return_exceptions=True)
        
        # Identify clients that failed to send (disconnected)
        for websocket, result in zip(CONNECTIONS, results):
            if isinstance(result, websockets.exceptions.ConnectionClosed):
                disconnected_clients.append(websocket)
                
        # Clean up disconnected clients
        for client in disconnected_clients:
            await unregister(client)

async def handler(websocket, path):
    """Handles connection and message flow."""
    await register(websocket)
    try:
        async for raw_message in websocket:
            try:
                message = json.loads(raw_message)
                
                # Basic validation
                if all(key in message for key in ["user", "text"]) and message["text"].strip():
                    message["text"] = message["text"].strip()
                    # Add a simple timestamp (seconds since epoch)
                    message["timestamp"] = asyncio.get_event_loop().time()
                    await broadcast(message)
                
            except json.JSONDecodeError:
                print("Received invalid JSON.")

    except websockets.exceptions.ConnectionClosed:
        pass
    
    finally:
        # Note: unregistering happens inside broadcast for better cleanup, 
        # but this ensures cleanup if no broadcast occurs before disconnect.
        if websocket in CONNECTIONS:
            await unregister(websocket)

async def main():
    """Starts the WebSocket server."""
    print(f"🌍 Starting Global Chat Server on {HOST}:{PORT}")
    async with websockets.serve(handler, HOST, PORT):
        await asyncio.Future() # Run forever

if __name__ == "__main__":
    try:
        # Since asyncio.run() only runs in main thread, use simple exception
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped.")
    except Exception as e:
        print(f"An error occurred: {e}")
