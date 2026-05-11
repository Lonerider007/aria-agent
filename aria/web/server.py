import socket
import webbrowser
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn

from aria.web.bridge import WebSession

app = FastAPI(docs_url=None, redoc_url=None)
_STATIC = Path(__file__).parent / "static"


@app.get("/")
async def index():
    return HTMLResponse((_STATIC / "index.html").read_text())


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    session = WebSession()
    try:
        await session.handle(ws)
    except WebSocketDisconnect:
        pass


def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


def start(host: str = "0.0.0.0", port: int = 7865, open_browser: bool = True):
    ip = _local_ip()
    print(f"\n  ◉  ARIA Web — running")
    print(f"  Local  : http://localhost:{port}")
    print(f"  Network: http://{ip}:{port}  ← open on phone\n")
    if open_browser:
        webbrowser.open(f"http://localhost:{port}")
    uvicorn.run(
        app, host=host, port=port, log_level="warning",
        ws_ping_interval=None, ws_ping_timeout=None,
    )
