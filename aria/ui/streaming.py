import json
import time
import threading
from rich.live import Live
from rich.text import Text
from rich.markdown import Markdown
from rich.rule import Rule
from .console import console

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


def _run_stream_in_thread(client, model, messages, tools, timeout, result_holder):
    """Run API call in a thread so main thread can enforce hard timeout."""
    try:
        import httpx
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            stream=True,
            timeout=httpx.Timeout(connect=15.0, read=90.0, write=15.0, pool=15.0),
        )
        collected_content = ""
        collected_tool_calls = {}
        for chunk in stream:
            if result_holder.get("abort"):
                break
            choice = chunk.choices[0] if chunk.choices else None
            if not choice:
                continue
            delta = choice.delta
            if delta.content:
                collected_content += delta.content
                result_holder["partial_text"] = collected_content
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in collected_tool_calls:
                        collected_tool_calls[idx] = {"id": tc_delta.id or "", "type": "function", "function": {"name": "", "arguments": ""}}
                    if tc_delta.id:
                        collected_tool_calls[idx]["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            collected_tool_calls[idx]["function"]["name"] += tc_delta.function.name
                        if tc_delta.function.arguments:
                            collected_tool_calls[idx]["function"]["arguments"] += tc_delta.function.arguments
        result_holder["content"] = collected_content
        result_holder["tool_calls"] = collected_tool_calls
        result_holder["done"] = True
    except Exception as e:
        result_holder["error"] = e
        result_holder["done"] = True


def stream_response(client, model: str, messages: list, tools: list, on_token=None, timeout: int = 180):
    """
    Stream response from model with hard thread timeout.
    Returns (final_message_dict, tool_calls_list, text_content)
    """
    start_time = time.time()
    total_chars = sum(len(str(m.get("content", ""))) for m in messages)
    pulse_idx = 0
    last_pulse = time.time()

    result_holder = {"done": False, "abort": False, "content": "", "tool_calls": {}, "partial_text": "", "error": None}
    t = threading.Thread(target=_run_stream_in_thread, args=(client, model, messages, tools, timeout, result_holder), daemon=True)
    t.start()

    with Live(console=console, refresh_per_second=10) as live:
        live.update(Text.from_markup(f"\n  [#7C3AED]◉[/#7C3AED] [#6B7280]Thinking...[/#6B7280]"))
        while not result_holder["done"]:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                result_holder["abort"] = True
                live.update(Text(""))
                raise RuntimeError("API_TIMEOUT")
            now = time.time()
            if now - last_pulse > 0.1:
                icon = PULSE[pulse_idx % len(PULSE)]
                e_str = _fmt_time(elapsed)
                tok = _fmt_tokens(str(total_chars + len(result_holder["partial_text"])))
                partial = result_holder["partial_text"]
                if partial:
                    preview = Text()
                    preview.append("\n  ◉ ", style="#7C3AED bold")
                    preview.append(partial[-300:], style="white")
                    live.update(preview)
                    if on_token:
                        pass  # tokens already collected, emit on_token handled in thread
                else:
                    live.update(Text.from_markup(
                        f"\n  [#7C3AED]{icon}[/#7C3AED] [#6B7280]Thinking...[/#6B7280]"
                        f"  [#4A4A6A]{e_str} · ↑ {tok} tokens[/#4A4A6A]"
                    ))
                pulse_idx += 1
                last_pulse = now
            time.sleep(0.05)
        live.update(Text(""))

    if result_holder["error"]:
        err = result_holder["error"]
        err_str = str(err)
        if "timed out" in err_str.lower() or "timeout" in err_str.lower() or "ReadTimeout" in err_str or "ConnectTimeout" in err_str:
            raise RuntimeError("API_TIMEOUT") from err
        if "prompt too long" in err_str or "context length" in err_str:
            raise RuntimeError("CONTEXT_TOO_LONG") from err
        if "invalid tool call" in err_str or ("invalid_request" in err_str and "tool" in err_str.lower()):
            raise RuntimeError("INVALID_TOOL_ARGS") from err
        if "429" in err_str or "rate limit" in err_str.lower() or "usage limit" in err_str.lower():
            raise RuntimeError("RATE_LIMIT") from err
        if ("500" in err_str or "502" in err_str or "503" in err_str or
                "internal service error" in err_str.lower() or
                "InternalServerError" in type(err).__name__ or
                "unexpected EOF" in err_str or "Bad Gateway" in err_str):
            raise RuntimeError("SERVER_ERROR") from err
        raise err

    collected_content = result_holder["content"]
    collected_tool_calls = result_holder["tool_calls"]
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
