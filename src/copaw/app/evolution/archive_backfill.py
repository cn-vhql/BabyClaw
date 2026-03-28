# -*- coding: utf-8 -*-
"""Backfill evolution archive details from persisted session state."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .models import EvolutionArchive, EvolutionRecord
from ..runner.session import sanitize_filename

logger = logging.getLogger(__name__)


def enrich_archive_from_sessions(
    *,
    workspace_dir: Path,
    archive: EvolutionArchive,
    record: EvolutionRecord | None,
) -> EvolutionArchive:
    """Best-effort fill missing archive details from saved evolution sessions."""
    if record is None:
        return archive

    reconstructed = _reconstruct_archive_from_sessions(
        workspace_dir=Path(workspace_dir),
        archive=archive,
        record=record,
    )
    if not reconstructed:
        return archive

    tool_logs = reconstructed.get("tool_execution_log") or []
    structured_records = reconstructed.get("structured_records") or []
    full_output = reconstructed.get("full_output") or ""

    if tool_logs:
        archive.tool_execution_log = tool_logs
    if structured_records:
        archive.structured_records = structured_records
    if full_output:
        archive.full_output = full_output

    return archive


def _reconstruct_archive_from_sessions(
    *,
    workspace_dir: Path,
    archive: EvolutionArchive,
    record: EvolutionRecord,
) -> dict[str, Any] | None:
    sessions_dir = workspace_dir / "sessions"
    if not sessions_dir.exists():
        return None

    candidate_paths = [
        _session_file_path(
            sessions_dir=sessions_dir,
            session_id=f"evolution:{record.id}",
            user_id="evolution_system",
        ),
        _session_file_path(
            sessions_dir=sessions_dir,
            session_id=f"evolution:{record.agent_id}",
            user_id="evolution_system",
        ),
    ]

    for index, session_path in enumerate(candidate_paths):
        if not session_path.exists():
            continue

        messages = _load_session_messages(session_path)
        if not messages:
            continue

        # Legacy runs used one dedicated session per evolution record.
        if index > 0:
            messages = _filter_messages_for_record_window(
                messages=messages,
                record=record,
                archive=archive,
            )
            if not messages:
                continue

        reconstructed = _build_archive_from_messages(messages)
        if reconstructed:
            return reconstructed

    return None


def _session_file_path(*, sessions_dir: Path, session_id: str, user_id: str) -> Path:
    safe_sid = sanitize_filename(session_id)
    safe_uid = sanitize_filename(user_id) if user_id else ""
    filename = f"{safe_uid}_{safe_sid}.json" if safe_uid else f"{safe_sid}.json"
    return sessions_dir / filename


def _load_session_messages(session_path: Path) -> list[dict[str, Any]]:
    try:
        state = json.loads(session_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to read evolution session %s: %s", session_path, exc)
        return []

    content_entries = (
        state.get("agent", {})
        .get("memory", {})
        .get("content", [])
    )
    messages: list[dict[str, Any]] = []
    for entry in content_entries:
        payload = entry[0] if isinstance(entry, list) and entry else entry
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict) and isinstance(item.get("content"), list):
                    messages.append(item)
        elif isinstance(payload, dict) and isinstance(payload.get("content"), list):
            messages.append(payload)

    return messages


def _filter_messages_for_record_window(
    *,
    messages: list[dict[str, Any]],
    record: EvolutionRecord,
    archive: EvolutionArchive,
) -> list[dict[str, Any]]:
    start_at = _parse_datetime(record.timestamp)
    if start_at is None:
        return []

    end_candidates = [start_at]
    if record.duration_seconds:
        end_candidates.append(start_at + timedelta(seconds=record.duration_seconds))

    archive_timestamp = _parse_datetime(archive.timestamp)
    if archive_timestamp is not None:
        end_candidates.append(archive_timestamp)

    end_at = max(end_candidates)
    window_start = start_at - timedelta(seconds=5)
    window_end = end_at + timedelta(seconds=8)

    filtered: list[dict[str, Any]] = []
    for message in messages:
        timestamp = _parse_datetime(message.get("timestamp"))
        if timestamp is None:
            continue
        if window_start <= timestamp <= window_end:
            filtered.append(message)

    return filtered


def _build_archive_from_messages(messages: list[dict[str, Any]]) -> dict[str, Any]:
    tool_logs: list[dict[str, Any]] = []
    structured_records: list[dict[str, Any]] = []
    full_output_parts: list[str] = []

    for message in messages:
        role = message.get("role")
        message_type = _normalize_message_type(message.get("type"))
        timestamp = _normalize_timestamp(message.get("timestamp"))

        _record_metadata(
            structured_records,
            _serialize_value(message.get("metadata")),
            message_type=message_type,
            timestamp=timestamp,
        )

        for block in message.get("content") or []:
            if not isinstance(block, dict):
                continue

            block_type = block.get("type")
            if block_type == "tool_use":
                _append_tool_call(
                    tool_logs,
                    tool_name=block.get("name"),
                    tool_input=_deserialize_json_like(block.get("input")),
                    call_id=block.get("id"),
                    timestamp=timestamp,
                )
            elif block_type == "tool_result":
                output = _normalize_tool_output(block.get("output"))
                _attach_tool_result(
                    tool_logs,
                    output=output,
                    tool_name=block.get("name"),
                    call_id=block.get("id"),
                    timestamp=timestamp,
                )
                _append_output_part(
                    full_output_parts,
                    output,
                    prefix=f"[工具结果:{block.get('name') or 'unknown_tool'}]",
                )
            elif block_type == "thinking" and role == "assistant":
                thinking = block.get("thinking", "")
                if thinking:
                    _append_output_part(
                        full_output_parts,
                        thinking,
                        prefix="[思考]",
                        inline_prefix=True,
                    )
            elif block_type == "text" and role != "user":
                text = block.get("text", "")
                if text:
                    _append_output_part(
                        full_output_parts,
                        text,
                        prefix="[思考]" if message_type == "reasoning" else None,
                        inline_prefix=message_type == "reasoning",
                    )
            elif block_type == "data":
                _process_data_payload(
                    tool_logs,
                    structured_records,
                    full_output_parts,
                    payload=block.get("data"),
                    message_type=message_type,
                    timestamp=timestamp,
                )

    return {
        "tool_execution_log": tool_logs,
        "structured_records": structured_records,
        "full_output": "\n".join(part for part in full_output_parts if part).strip(),
    }


def _process_data_payload(
    tool_logs: list[dict[str, Any]],
    structured_records: list[dict[str, Any]],
    full_output_parts: list[str],
    *,
    payload: Any,
    message_type: str | None,
    timestamp: str | None,
) -> None:
    payload = _deserialize_json_like(payload)
    if payload in (None, "", {}, []):
        return

    if isinstance(payload, dict):
        call_id = payload.get("call_id") or payload.get("id")
        tool_name = payload.get("name") or payload.get("tool")

        if message_type in {
            "plugin_call",
            "function_call",
            "mcp_call",
        } or (tool_name and ("input" in payload or "arguments" in payload)):
            _append_tool_call(
                tool_logs,
                tool_name=tool_name,
                tool_input=_deserialize_json_like(
                    payload.get("input", payload.get("arguments")),
                ),
                call_id=call_id,
                timestamp=timestamp,
            )
            return

        if message_type in {
            "plugin_call_output",
            "function_call_output",
            "mcp_call_output",
        } or ("output" in payload or "result" in payload):
            output = _deserialize_json_like(
                payload.get("output", payload.get("result")),
            )
            _attach_tool_result(
                tool_logs,
                output=output,
                tool_name=tool_name,
                call_id=call_id,
                timestamp=timestamp,
            )
            _append_output_part(
                full_output_parts,
                _normalize_tool_output(output),
                prefix=f"[工具结果:{tool_name or 'unknown_tool'}]",
            )
            return

    _append_structured_record(
        structured_records,
        payload,
        record_type="data",
        source=message_type,
        timestamp=timestamp,
    )


def _append_tool_call(
    tool_logs: list[dict[str, Any]],
    *,
    tool_name: str | None,
    tool_input: Any,
    call_id: str | None,
    timestamp: str | None,
) -> None:
    normalized_tool_name = tool_name or "unknown_tool"
    existing = _find_tool_log(
        tool_logs,
        call_id=call_id,
        tool_name=normalized_tool_name,
        require_open=False,
    )
    if existing is None:
        existing = {
            "tool": normalized_tool_name,
            "timestamp": timestamp or datetime.now().isoformat(),
        }
        if call_id:
            existing["call_id"] = call_id
        tool_logs.append(existing)

    if tool_input not in (None, "", {}, []):
        existing["args"] = tool_input


def _attach_tool_result(
    tool_logs: list[dict[str, Any]],
    *,
    output: Any,
    tool_name: str | None,
    call_id: str | None,
    timestamp: str | None,
) -> None:
    target = _find_tool_log(
        tool_logs,
        call_id=call_id,
        tool_name=tool_name,
        require_open=True,
    )
    if target is None:
        target = {
            "tool": tool_name or "unknown_tool",
            "timestamp": timestamp or datetime.now().isoformat(),
        }
        if call_id:
            target["call_id"] = call_id
        tool_logs.append(target)

    target["result"] = output


def _find_tool_log(
    tool_logs: list[dict[str, Any]],
    *,
    call_id: str | None,
    tool_name: str | None,
    require_open: bool,
) -> dict[str, Any] | None:
    if call_id:
        for log in reversed(tool_logs):
            if require_open and "result" in log:
                continue
            if log.get("call_id") == call_id:
                return log

        if tool_name:
            for log in reversed(tool_logs):
                if require_open and "result" in log:
                    continue
                if log.get("tool") == tool_name and not log.get("call_id"):
                    return log
        return None

    if tool_name:
        for log in reversed(tool_logs):
            if require_open and "result" in log:
                continue
            if log.get("tool") == tool_name:
                return log
    return None


def _record_metadata(
    structured_records: list[dict[str, Any]],
    metadata: Any,
    *,
    message_type: str | None,
    timestamp: str | None,
) -> None:
    if metadata in (None, "", {}, []):
        return

    if isinstance(metadata, dict):
        structured_output = metadata.get("structured_output")
        if structured_output not in (None, "", {}, []):
            _append_structured_record(
                structured_records,
                _serialize_value(structured_output),
                record_type="structured_output",
                source=message_type,
                timestamp=timestamp,
            )
            remaining_metadata = {
                key: value
                for key, value in metadata.items()
                if key != "structured_output" and value not in (None, "", {}, [])
            }
            if remaining_metadata:
                _append_structured_record(
                    structured_records,
                    remaining_metadata,
                    record_type="metadata",
                    source=message_type,
                    timestamp=timestamp,
                )
            return

    _append_structured_record(
        structured_records,
        metadata,
        record_type="metadata",
        source=message_type,
        timestamp=timestamp,
    )


def _append_structured_record(
    structured_records: list[dict[str, Any]],
    data: Any,
    *,
    record_type: str,
    source: str | None,
    timestamp: str | None,
) -> None:
    if data in (None, "", {}, []):
        return

    record = {
        "type": record_type,
        "timestamp": timestamp or datetime.now().isoformat(),
        "data": data,
    }
    if source:
        record["source"] = source
    structured_records.append(record)


def _normalize_tool_output(output: Any) -> Any:
    output = _deserialize_json_like(output)
    if isinstance(output, list):
        text_parts = [
            block.get("text", "")
            for block in output
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        if text_parts and len(text_parts) == len(output):
            return "\n".join(part for part in text_parts if part).strip()
    return output


def _stringify_output_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, str):
        return value.strip()
    try:
        return json.dumps(value, ensure_ascii=False, indent=2).strip()
    except Exception:
        return str(value).strip()


def _append_output_part(
    full_output_parts: list[str],
    value: Any,
    *,
    prefix: str | None = None,
    inline_prefix: bool = False,
) -> None:
    rendered = _stringify_output_text(value)
    if not rendered:
        return

    if prefix:
        rendered = (
            f"{prefix}{rendered}"
            if inline_prefix
            else f"{prefix}\n{rendered}"
        )

    rendered = rendered.rstrip()
    if not rendered:
        return

    if full_output_parts and full_output_parts[-1] == rendered:
        return
    full_output_parts.append(rendered)


def _deserialize_json_like(value: Any) -> Any:
    value = _serialize_value(value)
    if not isinstance(value, str):
        return value

    stripped = value.strip()
    if not stripped or stripped[0] not in "[{":
        return value

    try:
        return json.loads(stripped)
    except Exception:
        return value


def _serialize_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump()
        except Exception:
            logger.debug("model_dump failed for %s", type(value), exc_info=True)
    return value


def _normalize_message_type(message_type: Any) -> str | None:
    if hasattr(message_type, "value"):
        return message_type.value
    if isinstance(message_type, str):
        return message_type
    return None


def _normalize_timestamp(value: Any) -> str | None:
    parsed = _parse_datetime(value)
    if parsed is not None:
        return parsed.isoformat()
    if isinstance(value, str) and value:
        return value
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if not isinstance(value, str) or not value:
        return None

    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is not None:
            return parsed.astimezone().replace(tzinfo=None)
        return parsed
    except ValueError:
        return None
