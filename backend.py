import asyncio
import websockets
import json
import os
from dotenv import load_dotenv

# Load environment variables (for local testing)
load_dotenv()

# --- Configuration ---
PORT = int(os.environ.get("PORT", 8765)) 
HOST = "0.0.0.0" 

# --- Global State ---
CONNECTIONS = set()
MAX_HISTORY = 50
CHAT_HISTORY = []

# --- Core Server Logic ---

async def register(websocket):
    """Adds a new client and sends history."""
    CONNECTIONS.add(websocket)
    print(f"[INFO] Client connected from {websocket.remote_address}. Total: {len(CONNECTIONS)}")
    
    try:
        for message in CHAT_HISTORY:
            await websocket.send(json.dumps(message))
    except websockets.exceptions.ConnectionClosed:
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
    
    if CONNECTIONS:
        send_tasks = [conn.send(message_json) for conn in CONNECTIONS]
        results = await asyncio.gather(*send_tasks, return_exceptions=True)
        
        disconnected_clients = []
        for websocket, result in zip(CONNECTIONS, results):
            if isinstance(result, Exception):
                disconnected_clients.append(websocket)
                
        for client in disconnected_clients:
            await unregister(client)

async def handler(websocket, path):
    """Handles connection, message receiving, and disconnection."""
    await register(websocket)
    
    try:
        async for raw_message in websocket:
            try:
                message = json.loads(raw_message)
                
                if all(key in message for key in ["user", "text"]) and message["text"].strip():
                    message["text"] = message["text"].strip()
                    message["timestamp"] = asyncio.get_event_loop().time()
                    await broadcast(message)
                
            except json.JSONDecodeError:
                print(f"[WARNING] Received invalid JSON from {websocket.remote_address}")

    except (websockets.exceptions.ConnectionClosedOK, websockets.exceptions.ConnectionClosedError) as e:
        print(f"[INFO] Connection closed by {websocket.remote_address}: {e.__class__.__name__}")
    except Exception as e:
        print(f"[FATAL] Unhandled exception in handler: {e}")
        
    finally:
        await unregister(websocket)

async def main():
    """Starts the WebSocket server."""
    print(f"🌍 Starting Global Chat Server on {HOST}:{PORT}")
    try:
        async with websockets.serve(handler, HOST, PORT):
            await asyncio.Future() 
    except OSError as e:
        print(f"[FATAL] Failed to bind to port {PORT}. Error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped manually.")
