import asyncio
import websockets

WS_HOST = "192.168.82.3" 
WS_PORT = 8765  

async def handle_client(websocket):
    print(f" Client connected: {websocket.remote_address}")
    try:
        async for message in websocket:
            print(f" Received: {message}")
    except websockets.exceptions.ConnectionClosed:
        print(" Client disconnected.")

async def start_server():
    server_instance = await websockets.serve(handle_client, WS_HOST, WS_PORT)
    print(f" WebSocket Server running on ws://{WS_HOST}:{WS_PORT}")
    await server_instance.wait_closed()

asyncio.run(start_server())
