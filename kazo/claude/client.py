import asyncio
import base64
import json
import logging
import mimetypes
from pathlib import Path

from kazo.config import settings

logger = logging.getLogger(__name__)

_api_client = None


def _get_api_client():
    global _api_client
    if _api_client is None:
        import anthropic

        _api_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _api_client


def _use_sdk() -> bool:
    return settings.anthropic_api_key is not None


SDK_MODEL_MAP = {
    "sonnet": "claude-sonnet-4-5-20250929",
    "haiku": "claude-haiku-4-5-20251001",
    "opus": "claude-opus-4-5-20251101",
}


def _resolve_model() -> str:
    return SDK_MODEL_MAP.get(settings.claude_model, settings.claude_model)


# --- CLI backend ---


async def _run_claude_once(args: list[str], timeout: int) -> dict:
    proc = await asyncio.create_subprocess_exec(
        "claude",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        raise TimeoutError(f"Claude CLI timed out after {timeout}s") from None

    stderr_text = stderr.decode().strip()
    if stderr_text:
        logger.debug("Claude CLI stderr: %s", stderr_text)

    if proc.returncode != 0:
        raise RuntimeError(f"Claude CLI error (rc={proc.returncode}): {stderr_text}")

    raw = stdout.decode()
    logger.debug("Claude CLI raw response: %s", raw[:2000])
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise RuntimeError(f"Claude CLI returned non-JSON: {raw[:500]}") from None


async def _run_cli(args: list[str], timeout: int | None = None, retries: int = 1) -> dict:
    effective_timeout = timeout or settings.claude_timeout
    last_error: Exception | None = None
    for attempt in range(1 + retries):
        try:
            return await _run_claude_once(args, effective_timeout)
        except (TimeoutError, RuntimeError) as exc:
            last_error = exc
            if attempt < retries:
                logger.warning("Claude CLI attempt %d failed (%s), retrying...", attempt + 1, exc)
                await asyncio.sleep(1)
    raise last_error  # type: ignore[misc]


async def _ask_cli(prompt: str, system_prompt: str = "") -> str:
    args = [
        "-p",
        prompt,
        "--model",
        settings.claude_model,
        "--output-format",
        "json",
        "--no-session-persistence",
        "--max-turns",
        "1",
    ]
    if system_prompt:
        args.extend(["--system-prompt", system_prompt])

    result = await _run_cli(args)
    return str(result.get("result", ""))


async def _ask_cli_structured(
    prompt: str,
    json_schema: dict,
    system_prompt: str = "",
    image_path: str | None = None,
) -> dict:
    schema_str = json.dumps(json_schema)

    if image_path:
        prompt = f"Read the file at {image_path} and then: {prompt}"

    args = [
        "-p",
        prompt,
        "--model",
        settings.claude_model,
        "--output-format",
        "json",
        "--json-schema",
        schema_str,
        "--no-session-persistence",
    ]

    if image_path:
        args.extend(
            [
                "--max-turns",
                "3",
                "--allowedTools",
                "Read",
                "--dangerously-skip-permissions",
            ]
        )

    if system_prompt:
        args.extend(["--append-system-prompt", system_prompt])

    timeout = settings.claude_timeout * 2 if image_path else None
    result = await _run_cli(args, timeout=timeout)
    structured = result.get("structured_output")
    if structured is None:
        raise RuntimeError(f"Claude returned no structured output. Raw result: {str(result.get('result', ''))[:300]}")
    if isinstance(structured, str):
        return json.loads(structured)
    return structured


# --- SDK backend ---


async def _ask_sdk(prompt: str, system_prompt: str = "") -> str:
    client = _get_api_client()
    kwargs: dict = {
        "model": _resolve_model(),
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system_prompt:
        kwargs["system"] = system_prompt

    response = await client.messages.create(**kwargs)
    return response.content[0].text


def _image_media_type(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    return mime or "image/jpeg"


async def _ask_sdk_structured(
    prompt: str,
    json_schema: dict,
    system_prompt: str = "",
    image_path: str | None = None,
) -> dict:
    client = _get_api_client()

    content: list[dict] = []
    if image_path:
        image_data = Path(image_path).read_bytes()
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": _image_media_type(image_path),
                    "data": base64.standard_b64encode(image_data).decode(),
                },
            }
        )
    content.append({"type": "text", "text": prompt})

    tool_name = "structured_output"
    tools = [
        {
            "name": tool_name,
            "description": "Return the structured output matching the schema.",
            "input_schema": json_schema,
        }
    ]

    kwargs: dict = {
        "model": _resolve_model(),
        "max_tokens": 2048,
        "messages": [{"role": "user", "content": content}],
        "tools": tools,
        "tool_choice": {"type": "tool", "name": tool_name},
    }
    if system_prompt:
        kwargs["system"] = system_prompt

    response = await client.messages.create(**kwargs)

    for block in response.content:
        if block.type == "tool_use" and block.name == tool_name:
            return block.input

    raise RuntimeError(f"Claude SDK returned no tool_use block. Response: {str(response.content)[:300]}")


class RateLimitExceeded(Exception):
    pass


# --- Public interface ---


async def ask_claude(prompt: str, system_prompt: str = "", chat_id: int | None = None) -> str:
    if chat_id is not None:
        _enforce_rate_limit(chat_id)
    if _use_sdk():
        return await _ask_sdk(prompt, system_prompt)
    return await _ask_cli(prompt, system_prompt)


async def ask_claude_structured(
    prompt: str,
    json_schema: dict,
    system_prompt: str = "",
    image_path: str | None = None,
    chat_id: int | None = None,
) -> dict:
    if chat_id is not None:
        _enforce_rate_limit(chat_id)
    if _use_sdk():
        return await _ask_sdk_structured(prompt, json_schema, system_prompt, image_path)
    return await _ask_cli_structured(prompt, json_schema, system_prompt, image_path)


def _enforce_rate_limit(chat_id: int) -> None:
    from kazo.main import check_rate_limit, record_rate_limit

    if not check_rate_limit(chat_id):
        raise RateLimitExceeded(f"Rate limit exceeded for chat {chat_id}")
    record_rate_limit(chat_id)
