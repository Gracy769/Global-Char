import asyncio
import websockets
import json
import os
from dotenv import load_dotenv

# Load environment variables (for local testing)
load_dotenv()

# --- Configuration ---
# Use environment PORT (for Heroku/Render) or default to 8765 (for local)
PORT = int(os.environ.get("PORT", 8765)) 
HOST = "0.0.0.0" # Listen on all interfaces for deployment

# --- Global State ---
CONNECTIONS = set()
MAX_HISTORY = 50
CHAT_HISTORY = []

# --- Core Server Logic ---

async def register(websocket):
    """Adds a new client and sends history."""
    CONNECTIONS.add(websocket)
    print(f"[INFO] Client connected from {websocket.remote_address}. Total: {len(CONNECTIONS)}")
    
    # Send history
    try:
        for message in CHAT_HISTORY:
            # We use await here to ensure history is sent completely before moving on
            await websocket.send(json.dumps(message))
    except websockets.exceptions.ConnectionClosed:
        # If the connection closes while sending history, it will be cleaned up later
        pass

async def unregister(websocket):
    """Removes a client."""
    if websocket in CONNECTIONS:
        CONNECTIONS.remove(websocket)
        print(f"[INFO] Client disconnected. Total: {len(CONNECTIONS)}")

async def broadcast(message):
    """Sends a message to all connected clients."""
    global CHAT_HISTORY
    
    # Update history
    CHAT_HISTORY.append(message)
    if len(CHAT_HISTORY) > MAX_HISTORY:
        CHAT_HISTORY = CHAT_HISTORY[1:] 

    message_json = json.dumps(message)
    
    # Concurrently send the message to all clients
    # Filter out connections that fail during broadcast (robust cleanup)
    if CONNECTIONS:
        # Create a list of send tasks
        send_tasks = [conn.send(message_json) for conn in CONNECTIONS]
        
        # Run them concurrently and collect exceptions
        results = await asyncio.gather(*send_tasks, return_exceptions=True)
        
        # Clean up failed connections
        disconnected_clients = []
        for websocket, result in zip(CONNECTIONS, results):
            if isinstance(result, Exception):
                # Handle various connection closing exceptions
                disconnected_clients.append(websocket)
                
        for client in disconnected_clients:
            await unregister(client)

async def handler(websocket, path):
    """Handles connection, message receiving, and disconnection."""
    await register(websocket)
    
    try:
        # Listen for messages from this specific client
        async for raw_message in websocket:
            try:
                message = json.loads(raw_message)
                
                # Basic validation
                if all(key in message for key in ["user", "text"]) and message["text"].strip():
                    message["text"] = message["text"].strip()
                    message["timestamp"] = asyncio.get_event_loop().time()
                    await broadcast(message)
                
            except json.JSONDecodeError:
                print(f"[WARNING] Received invalid JSON from {websocket.remote_address}")

    # Catch expected closure events
    except websockets.exceptions.ConnectionClosedOK:
        print(f"[INFO] Connection closed gracefully by {websocket.remote_address}")
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"[ERROR] Connection closed unexpectedly by {websocket.remote_address}: {e}")
    except Exception as e:
        print(f"[FATAL] Unhandled exception in handler: {e}")
        
    finally:
        # Ensure client is unregistered if still in the set
        await unregister(websocket)

async def main():
    """Starts the WebSocket server."""
    # Ensure port is valid
    if PORT <= 0 or PORT >= 65535:
         print(f"[ERROR] Invalid PORT setting: {PORT}. Exiting.")
         return
         
    print(f"🌍 Starting Global Chat Server on {HOST}:{PORT}")
    try:
        async with websockets.serve(handler, HOST, PORT):
            await asyncio.Future() # Run forever
    except OSError as e:
        print(f"[FATAL] Failed to bind to port {PORT}. Is another process running? Error: {e}")
    except Exception as e:
         print(f"[FATAL] An error occurred during server startup: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped manually.")
    # This might catch errors if the process is terminated abruptly
    except Exception as e:
        print(f"\nServer stopped due to a top-level error: {e}")
