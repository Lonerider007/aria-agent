import json
import time
from rich.live import Live
from rich.text import Text
from rich.markdown import Markdown
from rich.rule import Rule
from .console import console

# Pulse sequence — simulates zoom in/out
PULSE = ["·", "◦", "○", "◉", "●", "◉", "○", "◦"]


def stream_response(client, model: str, messages: list, tools: list):
    """
    Stream response from model.
    Returns (final_message_dict, tool_calls_list, text_content)
    """
    collected_content = ""
    collected_tool_calls = {}
    pulse_idx = 0
    last_pulse = time.time()

    with Live(console=console, refresh_per_second=30) as live:
        live.update(Text.from_markup(f"\n  [#7C3AED]◉[/#7C3AED] [#6B7280]Thinking...[/#6B7280]"))

        try:
            stream = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                stream=True,
            )

            for chunk in stream:
                choice = chunk.choices[0] if chunk.choices else None
                if not choice:
                    continue

                delta = choice.delta

                # Pulse animation on every chunk
                now = time.time()
                if now - last_pulse > 0.06:
                    icon = PULSE[pulse_idx % len(PULSE)]
                    live.update(Text.from_markup(
                        f"\n  [#7C3AED]{icon}[/#7C3AED] [#6B7280]Thinking...[/#6B7280]"
                    ))
                    pulse_idx += 1
                    last_pulse = now

                # Stream text content live
                if delta.content:
                    collected_content += delta.content
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
