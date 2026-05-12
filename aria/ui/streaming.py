import json
import time
import threading
from rich.live import Live
from rich.text import Text
from rich.markdown import Markdown
from rich.rule import Rule
from .console import console

_CHUNK_TIMEOUT = 45  # seconds — if no chunk arrives in 45s, abort stream

# Pulse sequence — simulates zoom in/out
PULSE = ["·", "◦", "○", "◉", "●", "◉", "○", "◦"]


def _fmt_time(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    return f"{int(seconds // 60)}m {int(seconds % 60)}s"


def _fmt_tokens(text: str) -> str:
    est = max(1, len(text) // 4)
    if est >= 1000:
        return f"{est/1000:.1f}k"
    return str(est)


def stream_response(client, model: str, messages: list, tools: list, on_token=None, timeout: int = 180):
    """
    Stream response from model.
    Returns (final_message_dict, tool_calls_list, text_content)
    timeout: seconds before aborting a hung API call (default 3 min)
    """
    collected_content = ""
    collected_tool_calls = {}
    pulse_idx = 0
    last_pulse = time.time()
    start_time = time.time()
    total_chars = sum(len(str(m.get("content", ""))) for m in messages)

    with Live(console=console, refresh_per_second=30) as live:
        live.update(Text.from_markup(f"\n  [#7C3AED]◉[/#7C3AED] [#6B7280]Thinking...[/#6B7280]"))

        try:
            stream = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                stream=True,
                timeout=timeout,
            )

            _last_chunk = [time.time()]  # watchdog: reset on every chunk

            def _watchdog():
                while True:
                    time.sleep(5)
                    if time.time() - _last_chunk[0] > _CHUNK_TIMEOUT:
                        stream.close()
                        break

            _wd = threading.Thread(target=_watchdog, daemon=True)
            _wd.start()

            for chunk in stream:
                _last_chunk[0] = time.time()  # reset watchdog
                choice = chunk.choices[0] if chunk.choices else None
                if not choice:
                    continue

                delta = choice.delta

                # Pulse + timer + token count
                now = time.time()
                if now - last_pulse > 0.06:
                    icon    = PULSE[pulse_idx % len(PULSE)]
                    elapsed = _fmt_time(now - start_time)
                    tokens  = _fmt_tokens(str(total_chars + len(collected_content)))
                    live.update(Text.from_markup(
                        f"\n  [#7C3AED]{icon}[/#7C3AED] [#6B7280]Thinking...[/#6B7280]"
                        f"  [#4A4A6A]{elapsed} · ↑ {tokens} tokens[/#4A4A6A]"
                    ))
                    pulse_idx += 1
                    last_pulse = now

                # Stream text content live
                if delta.content:
                    collected_content += delta.content
                    if on_token:
                        on_token(delta.content)
                    preview = Text()
                    preview.append("\n  ◉ ", style="#7C3AED bold")
                    preview.append(collected_content[-300:], style="white")
                    live.update(preview)

                # Accumulate tool calls
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in collected_tool_calls:
                            collected_tool_calls[idx] = {
                                "id": tc_delta.id or "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""}
                            }
                        if tc_delta.id:
                            collected_tool_calls[idx]["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                collected_tool_calls[idx]["function"]["name"] += tc_delta.function.name
                            if tc_delta.function.arguments:
                                collected_tool_calls[idx]["function"]["arguments"] += tc_delta.function.arguments

            live.update(Text(""))

        except Exception as e:
            live.update(Text(""))
            err_str = str(e)
            if "timed out" in err_str.lower() or "timeout" in err_str.lower() or "ReadTimeout" in err_str or "ConnectTimeout" in err_str or "StreamClosedError" in err_str or "closed" in err_str.lower():
                raise RuntimeError("API_TIMEOUT") from e
            if "prompt too long" in err_str or "context length" in err_str:
                raise RuntimeError("CONTEXT_TOO_LONG") from e
            if "invalid tool call" in err_str or ("invalid_request" in err_str and "tool" in err_str.lower()):
                raise RuntimeError("INVALID_TOOL_ARGS") from e
            if "429" in err_str or "rate limit" in err_str.lower() or "usage limit" in err_str.lower() or "weekly" in err_str.lower():
                raise RuntimeError("RATE_LIMIT") from e
            if "500" in err_str or "internal service error" in err_str.lower() or "InternalServerError" in err_str:
                raise RuntimeError("SERVER_ERROR") from e
            raise e

    tool_calls_list = [collected_tool_calls[i] for i in sorted(collected_tool_calls.keys())]

    msg_dict = {"role": "assistant", "content": collected_content or ""}
    if tool_calls_list:
        msg_dict["tool_calls"] = tool_calls_list

    return msg_dict, tool_calls_list, collected_content


def print_response(text: str):
    if not text.strip():
        return
    console.print()
    console.print(Rule("[aria.dim]Report[/aria.dim]", style="#7C3AED"))
    console.print(Markdown(text))
    console.print(Rule(style="#7C3AED"))
