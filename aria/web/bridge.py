import asyncio
import threading
import os
from openai import OpenAI
from aria.config import get
from aria.agent import Agent
import aria.tools.interaction as _interaction


class WebSession:
    def __init__(self):
        self._loop       = None
        self._event_q    = None
        self._resp_event = threading.Event()
        self._resp_value = None

    # ── thread-safe emit (called from agent thread) ──────────────────────────

    def emit(self, event: dict):
        if self._loop and self._event_q is not None:
            self._loop.call_soon_threadsafe(self._event_q.put_nowait, event)

    # ── interactive tool hooks (block agent thread until user responds) ───────

    def ask_plan(self, steps, goal: str) -> str:
        if isinstance(steps, str):
            steps = [s.strip() for s in steps.split("\n") if s.strip()]
        self._resp_event.clear()
        self.emit({"type": "plan", "goal": goal, "steps": steps})
        self._resp_event.wait(timeout=300)
        return self._resp_value or "APPROVED"

    def ask_question(self, question: str) -> str:
        self._resp_event.clear()
        self.emit({"type": "question", "text": question})
        self._resp_event.wait(timeout=300)
        return self._resp_value or "(no answer)"

    def ask_approval(self, action: str) -> str:
        self._resp_event.clear()
        self.emit({"type": "approval", "action": action})
        self._resp_event.wait(timeout=300)
        return self._resp_value or "APPROVED"

    def _set_response(self, value: str):
        self._resp_value = value
        self._resp_event.set()

    # ── main WebSocket handler ────────────────────────────────────────────────

    async def handle(self, ws):
        self._loop   = asyncio.get_running_loop()
        self._event_q = asyncio.Queue()

        api_key   = get("api_key") or "aria"
        base_url  = get("base_url", "http://localhost:11434/v1")
        model     = get("default_model", "llama3.3")
        workspace = get("workspace") or os.getcwd()

        client = OpenAI(base_url=base_url, api_key=api_key)
        agent  = Agent(client, model, emit_cb=self.emit)

        _interaction._web_ctx.session = self

        await ws.send_json({
            "type": "connected",
            "model": model,
            "workspace": workspace,
            "version": "1.4.4",
        })

        agent_running = False

        while True:
            try:
                if not agent_running:
                    data = await ws.receive_json()
                    if data.get("type") == "message":
                        agent_running = True
                        asyncio.create_task(self._run_agent(agent, data["text"]))
                else:
                    recv_task = asyncio.ensure_future(ws.receive_json())
                    get_task  = asyncio.ensure_future(self._event_q.get())

                    done, pending = await asyncio.wait(
                        [recv_task, get_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for t in pending:
                        t.cancel()

                    if get_task in done:
                        event = get_task.result()
                        if event.get("type") == "_done":
                            agent_running = False
                            await ws.send_json({"type": "done"})
                        else:
                            await ws.send_json(event)

                    if recv_task in done:
                        try:
                            data = recv_task.result()
                            if data.get("type") == "response":
                                self._set_response(data.get("value", ""))
                        except Exception:
                            pass

            except Exception:
                break

    async def _run_agent(self, agent: Agent, user_input: str):
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, agent.run, user_input)
        except Exception as e:
            self.emit({"type": "error", "text": str(e)})
        finally:
            self.emit({"type": "_done"})
