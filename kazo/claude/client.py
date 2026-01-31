import asyncio
import json
import logging

from kazo.config import settings

logger = logging.getLogger(__name__)


async def _run_claude_once(args: list[str], timeout: int) -> dict:
    proc = await asyncio.create_subprocess_exec(
        "claude", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise TimeoutError(
            f"Claude CLI timed out after {timeout}s"
        )

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
        raise RuntimeError(f"Claude CLI returned non-JSON: {raw[:500]}")


async def _run_claude(args: list[str], timeout: int | None = None, retries: int = 1) -> dict:
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


async def ask_claude(prompt: str, system_prompt: str = "") -> str:
    args = [
        "-p", prompt,
        "--model", settings.claude_model,
        "--output-format", "json",
        "--no-session-persistence",
    ]
    if system_prompt:
        args.extend(["--system-prompt", system_prompt])

    result = await _run_claude(args)
    return str(result.get("result", ""))


async def ask_claude_structured(
    prompt: str,
    json_schema: dict,
    system_prompt: str = "",
    image_path: str | None = None,
) -> dict:
    schema_str = json.dumps(json_schema)

    if image_path:
        prompt = f"Read the file at {image_path} and then: {prompt}"

    args = [
        "-p", prompt,
        "--model", settings.claude_model,
        "--output-format", "json",
        "--json-schema", schema_str,
        "--no-session-persistence",
    ]

    if image_path:
        args.extend([
            "--allowedTools", "Read",
            "--dangerously-skip-permissions",
        ])

    if system_prompt:
        args.extend(["--append-system-prompt", system_prompt])

    timeout = settings.claude_timeout * 2 if image_path else None
    result = await _run_claude(args, timeout=timeout)
    structured = result.get("structured_output")
    if structured is None:
        raise RuntimeError(
            f"Claude returned no structured output. "
            f"Raw result: {str(result.get('result', ''))[:300]}"
        )
    if isinstance(structured, str):
        return json.loads(structured)
    return structured
