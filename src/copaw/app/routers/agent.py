# -*- coding: utf-8 -*-
"""Agent file management API."""

import asyncio
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, HTTPException, Request, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ...config import (
    load_config,
    save_config,
    AgentsRunningConfig,
)
from ...config.config import load_agent_config, save_agent_config
from ...agents.memory.agent_md_manager import AgentMdManager
from ...agents.utils import copy_md_files
from ..agent_context import get_agent_for_request

router = APIRouter(prefix="/agent", tags=["agent"])


# Preset files and directories that should not be deletable
PRESET_FILES = {
    "copaw.db",
    "copaw.db-journal",
    "agent.json",
    # Core markdown files
    "AGENTS.md",
    "SOUL.md",
    "PROFILE.md",
    "MEMORY.md",
    "BOOTSTRAP.md",
    "HEARTBEAT.md",
    # Working and memory directories
    "working_dir",
    "memory",
}


class FileTreeNode(BaseModel):
    """File tree node."""

    name: str = Field(..., description="File or folder name")
    path: str = Field(..., description="Relative path from workspace root")
    type: str = Field(..., description="Type: 'file' or 'folder'")
    size: int = Field(..., description="Size in bytes (files only)")
    modified_time: str = Field(..., description="Modified time")
    children: Optional[list["FileTreeNode"]] = Field(None, description="Child nodes (folders only)")


class MdFileInfo(BaseModel):
    """Markdown file metadata."""

    filename: str = Field(..., description="File name")
    path: str = Field(..., description="File path")
    size: int = Field(..., description="Size in bytes")
    created_time: str = Field(..., description="Created time")
    modified_time: str = Field(..., description="Modified time")


class MdFileContent(BaseModel):
    """Markdown file content."""

    content: str = Field(..., description="File content")


@router.get(
    "/files",
    response_model=list[MdFileInfo],
    summary="List working files",
    description="List all working files (uses active agent)",
)
async def list_working_files(
    request: Request,
) -> list[MdFileInfo]:
    """List working directory markdown files."""
    try:
        workspace = await get_agent_for_request(request)
        workspace_manager = AgentMdManager(
            str(workspace.workspace_dir),
        )
        files = [
            MdFileInfo.model_validate(file)
            for file in workspace_manager.list_working_mds()
        ]
        return files
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/files/{md_name}",
    response_model=MdFileContent,
    summary="Read a working file",
    description="Read a working markdown file (uses active agent)",
)
async def read_working_file(
    md_name: str,
    request: Request,
) -> MdFileContent:
    """Read a working directory markdown file."""
    try:
        workspace = await get_agent_for_request(request)
        workspace_manager = AgentMdManager(
            str(workspace.workspace_dir),
        )
        content = workspace_manager.read_working_md(md_name)
        return MdFileContent(content=content)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put(
    "/files/{md_name}",
    response_model=dict,
    summary="Write a working file",
    description="Create or update a working file (uses active agent)",
)
async def write_working_file(
    md_name: str,
    body: MdFileContent,
    request: Request,
) -> dict:
    """Write a working directory markdown file."""
    try:
        workspace = await get_agent_for_request(request)
        workspace_manager = AgentMdManager(
            str(workspace.workspace_dir),
        )
        workspace_manager.write_working_md(md_name, body.content)
        return {"written": True}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/memory",
    response_model=list[MdFileInfo],
    summary="List memory files",
    description="List all memory files (uses active agent)",
)
async def list_memory_files(
    request: Request,
) -> list[MdFileInfo]:
    """List memory directory markdown files."""
    try:
        workspace = await get_agent_for_request(request)
        workspace_manager = AgentMdManager(
            str(workspace.workspace_dir),
        )
        files = [
            MdFileInfo.model_validate(file)
            for file in workspace_manager.list_memory_mds()
        ]
        return files
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/memory/{md_name}",
    response_model=MdFileContent,
    summary="Read a memory file",
    description="Read a memory markdown file (uses active agent)",
)
async def read_memory_file(
    md_name: str,
    request: Request,
) -> MdFileContent:
    """Read a memory directory markdown file."""
    try:
        workspace = await get_agent_for_request(request)
        workspace_manager = AgentMdManager(
            str(workspace.workspace_dir),
        )
        content = workspace_manager.read_memory_md(md_name)
        return MdFileContent(content=content)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put(
    "/memory/{md_name}",
    response_model=dict,
    summary="Write a memory file",
    description="Create or update a memory file (uses active agent)",
)
async def write_memory_file(
    md_name: str,
    body: MdFileContent,
    request: Request,
) -> dict:
    """Write a memory directory markdown file."""
    try:
        workspace = await get_agent_for_request(request)
        workspace_manager = AgentMdManager(
            str(workspace.workspace_dir),
        )
        workspace_manager.write_memory_md(md_name, body.content)
        return {"written": True}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/language",
    summary="Get agent language",
    description="Get the language setting for agent MD files (en/zh/ru)",
)
async def get_agent_language(request: Request) -> dict:
    """Get agent language setting for current agent."""
    workspace = await get_agent_for_request(request)
    agent_config = load_agent_config(workspace.agent_id)
    return {
        "language": agent_config.language,
        "agent_id": workspace.agent_id,
    }


@router.put(
    "/language",
    summary="Update agent language",
    description=(
        "Update the language for agent MD files (en/zh/ru). "
        "Optionally copies MD files for the new language to agent workspace."
    ),
)
async def put_agent_language(
    request: Request,
    body: dict = Body(
        ...,
        description='Language setting, e.g. {"language": "zh"}',
    ),
) -> dict:
    """
    Update agent language and optionally re-copy MD files to agent workspace.
    """
    language = (body.get("language") or "").strip().lower()
    valid = {"zh", "en", "ru"}
    if language not in valid:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid language '{language}'. "
                f"Must be one of: {', '.join(sorted(valid))}"
            ),
        )

    # Get current agent's workspace
    workspace = await get_agent_for_request(request)
    agent_id = workspace.agent_id

    # Load agent config
    agent_config = load_agent_config(agent_id)
    old_language = agent_config.language

    # Update agent's language
    agent_config.language = language
    save_agent_config(agent_id, agent_config)

    copied_files: list[str] = []
    if old_language != language:
        # Copy MD files to agent's workspace directory
        copied_files = (
            copy_md_files(
                language,
                workspace_dir=workspace.workspace_dir,
            )
            or []
        )

    return {
        "language": language,
        "copied_files": copied_files,
        "agent_id": agent_id,
    }


@router.get(
    "/audio-mode",
    summary="Get audio mode",
    description=(
        "Get the audio handling mode for incoming voice messages. "
        'Values: "auto", "native".'
    ),
)
async def get_audio_mode() -> dict:
    """Get audio mode setting."""
    config = load_config()
    return {"audio_mode": config.agents.audio_mode}


@router.put(
    "/audio-mode",
    summary="Update audio mode",
    description=(
        "Update how incoming audio/voice messages are handled. "
        '"auto": transcribe if provider available, else file placeholder; '
        '"native": send audio directly to model (may need ffmpeg).'
    ),
)
async def put_audio_mode(
    body: dict = Body(
        ...,
        description='Audio mode, e.g. {"audio_mode": "auto"}',
    ),
) -> dict:
    """Update audio mode setting."""
    raw = body.get("audio_mode")
    audio_mode = (str(raw) if raw is not None else "").strip().lower()
    valid = {"auto", "native"}
    if audio_mode not in valid:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid audio_mode '{audio_mode}'. "
                f"Must be one of: {', '.join(sorted(valid))}"
            ),
        )
    config = load_config()
    config.agents.audio_mode = audio_mode
    save_config(config)
    return {"audio_mode": audio_mode}


@router.get(
    "/transcription-provider-type",
    summary="Get transcription provider type",
    description=(
        "Get the transcription provider type. "
        'Values: "disabled", "whisper_api", "local_whisper".'
    ),
)
async def get_transcription_provider_type() -> dict:
    """Get transcription provider type setting."""
    config = load_config()
    return {
        "transcription_provider_type": (
            config.agents.transcription_provider_type
        ),
    }


@router.put(
    "/transcription-provider-type",
    summary="Set transcription provider type",
    description=(
        "Set the transcription provider type. "
        '"disabled": no transcription; '
        '"whisper_api": remote Whisper endpoint; '
        '"local_whisper": locally installed openai-whisper.'
    ),
)
async def put_transcription_provider_type(
    body: dict = Body(
        ...,
        description=(
            "Provider type, e.g. "
            '{"transcription_provider_type": "whisper_api"}'
        ),
    ),
) -> dict:
    """Set the transcription provider type."""
    raw = body.get("transcription_provider_type")
    provider_type = (str(raw) if raw is not None else "").strip().lower()
    valid = {"disabled", "whisper_api", "local_whisper"}
    if provider_type not in valid:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid transcription_provider_type '{provider_type}'. "
                f"Must be one of: {', '.join(sorted(valid))}"
            ),
        )
    config = load_config()
    config.agents.transcription_provider_type = provider_type
    save_config(config)
    return {"transcription_provider_type": provider_type}


@router.get(
    "/local-whisper-status",
    summary="Check local whisper availability",
    description=(
        "Check whether the local whisper provider can be used. "
        "Returns availability of ffmpeg and openai-whisper."
    ),
)
async def get_local_whisper_status() -> dict:
    """Check local whisper dependencies."""
    from ...agents.utils.audio_transcription import (
        check_local_whisper_available,
    )

    return check_local_whisper_available()


@router.get(
    "/transcription-providers",
    summary="List transcription providers",
    description=(
        "List providers capable of audio transcription (Whisper API). "
        "Returns available providers and the configured selection."
    ),
)
async def get_transcription_providers() -> dict:
    """List transcription-capable providers and configured selection."""
    from ...agents.utils.audio_transcription import (
        get_configured_transcription_provider_id,
        list_transcription_providers,
    )

    return {
        "providers": list_transcription_providers(),
        "configured_provider_id": (get_configured_transcription_provider_id()),
    }


@router.put(
    "/transcription-provider",
    summary="Set transcription provider",
    description=(
        "Set the provider to use for audio transcription. "
        'Use empty string "" to unset.'
    ),
)
async def put_transcription_provider(
    body: dict = Body(
        ...,
        description=(
            'Provider ID, e.g. {"provider_id": "openai"} '
            'or {"provider_id": ""} to unset'
        ),
    ),
) -> dict:
    """Set the transcription provider."""
    provider_id = (body.get("provider_id") or "").strip()
    config = load_config()
    config.agents.transcription_provider_id = provider_id
    save_config(config)
    return {"provider_id": provider_id}


@router.get(
    "/running-config",
    response_model=AgentsRunningConfig,
    summary="Get agent running config",
    description="Get running configuration for active agent",
)
async def get_agents_running_config(
    request: Request,
) -> AgentsRunningConfig:
    """Get agent running configuration."""
    workspace = await get_agent_for_request(request)
    agent_config = load_agent_config(workspace.agent_id)
    return agent_config.running or AgentsRunningConfig()


@router.put(
    "/running-config",
    response_model=AgentsRunningConfig,
    summary="Update agent running config",
    description="Update running configuration for active agent",
)
async def put_agents_running_config(
    running_config: AgentsRunningConfig = Body(
        ...,
        description="Updated agent running configuration",
    ),
    request: Request = None,
) -> AgentsRunningConfig:
    """Update agent running configuration."""
    workspace = await get_agent_for_request(request)
    agent_config = load_agent_config(workspace.agent_id)
    agent_config.running = running_config
    save_agent_config(workspace.agent_id, agent_config)

    # Hot reload config (async, non-blocking)
    # IMPORTANT: Get manager and agent_id before creating background task
    # to avoid accessing request/workspace after their lifecycle ends
    manager = request.app.state.multi_agent_manager
    agent_id = workspace.agent_id

    async def reload_in_background():
        try:
            await manager.reload_agent(agent_id)
        except Exception as e:
            logging.getLogger(__name__).warning(
                f"Background reload failed: {e}",
            )

    asyncio.create_task(reload_in_background())

    return running_config


@router.get(
    "/system-prompt-files",
    response_model=list[str],
    summary="Get system prompt files",
    description="Get system prompt files for active agent",
)
async def get_system_prompt_files(
    request: Request,
) -> list[str]:
    """Get list of enabled system prompt files."""
    workspace = await get_agent_for_request(request)
    agent_config = load_agent_config(workspace.agent_id)
    return agent_config.system_prompt_files or []


@router.put(
    "/system-prompt-files",
    response_model=list[str],
    summary="Update system prompt files",
    description="Update system prompt files for active agent",
)
async def put_system_prompt_files(
    files: list[str] = Body(
        ...,
        description="Markdown filenames to load into system prompt",
    ),
    request: Request = None,
) -> list[str]:
    """Update list of enabled system prompt files."""
    workspace = await get_agent_for_request(request)
    agent_config = load_agent_config(workspace.agent_id)
    agent_config.system_prompt_files = files
    save_agent_config(workspace.agent_id, agent_config)

    # Hot reload config (async, non-blocking)
    # IMPORTANT: Get manager before creating background task to avoid
    # accessing request object after its lifecycle ends
    manager = request.app.state.multi_agent_manager
    agent_id = workspace.agent_id

    async def reload_in_background():
        try:
            await manager.reload_agent(agent_id)
        except Exception as e:
            logging.getLogger(__name__).warning(
                f"Background reload failed: {e}",
            )

    asyncio.create_task(reload_in_background())

    return files


# ---------------------------------------------------------------------------
# File Management API
# ---------------------------------------------------------------------------


def _build_file_tree(
    root: Path,
    current: Path,
    relative_path: str = "",
) -> dict:
    """Build file tree structure for a directory."""
    name = current.name
    rel_path = str(Path(relative_path) / name) if relative_path else name

    if current.is_file():
        stat = current.stat()
        return {
            "name": name,
            "path": rel_path,
            "type": "file",
            "size": stat.st_size,
            "modified_time": datetime.fromtimestamp(
                stat.st_mtime,
                tz=timezone.utc,
            ).isoformat(),
            "children": None,
        }
    elif current.is_dir():
        children = []
        try:
            for item in sorted(current.iterdir(), key=lambda x: (not x.is_dir(), x.name)):
                children.append(_build_file_tree(root, item, rel_path))
        except PermissionError:
            pass
        return {
            "name": name,
            "path": rel_path,
            "type": "folder",
            "size": 0,
            "modified_time": "",
            "children": children,
        }
    else:
        return None


@router.get(
    "/file-tree",
    response_model=FileTreeNode,
    summary="Get workspace file tree",
    description="Get all files and folders in workspace (tree structure)",
)
async def get_file_tree(request: Request) -> dict:
    """Get complete file tree of workspace."""
    try:
        workspace = await get_agent_for_request(request)
        workspace_dir = workspace.workspace_dir

        if not workspace_dir.exists():
            return {
                "name": workspace_dir.name,
                "path": "",
                "type": "folder",
                "size": 0,
                "modified_time": "",
                "children": [],
            }

        # Build children of workspace root (don't include root itself)
        children = []
        try:
            for item in sorted(workspace_dir.iterdir(), key=lambda x: (not x.is_dir(), x.name)):
                node = _build_file_tree(workspace_dir, item, "")
                if node:
                    children.append(node)
        except PermissionError:
            pass

        return {
            "name": workspace_dir.name,
            "path": "",
            "type": "folder",
            "size": 0,
            "modified_time": "",
            "children": children,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/file-content",
    summary="Get file content",
    description="Get content of a specific file for preview",
)
async def get_file_content(
    request: Request,
    path: str,
) -> dict:
    """Get content of a file."""
    try:
        workspace = await get_agent_for_request(request)
        file_path = workspace.workspace_dir / path

        logging.getLogger(__name__).info(f"Loading file content: path={path}, file_path={file_path}, exists={file_path.exists()}")

        # Security check: ensure path is within workspace
        if not str(file_path.resolve()).startswith(str(workspace.workspace_dir.resolve())):
            raise HTTPException(status_code=403, detail="Access denied")

        if not file_path.exists() or not file_path.is_file():
            logging.getLogger(__name__).error(f"File not found: {file_path}")
            # List workspace dir for debugging
            if workspace.workspace_dir.exists():
                files = list(workspace.workspace_dir.rglob("*"))
                logging.getLogger(__name__).info(f"Workspace files: {[str(f.relative_to(workspace.workspace_dir)) for f in files[:20]]}")
            raise HTTPException(status_code=404, detail="File not found")

        # Check if file is text-based (preview supported)
        text_extensions = {
            ".txt", ".md", ".py", ".js", ".ts", ".tsx", ".jsx", ".json",
            ".yaml", ".yml", ".xml", ".html", ".css", ".less", ".scss",
            ".sh", ".bash", ".zsh", ".fish", ".cfg", ".conf", ".ini",
            ".toml", ".csv", ".log", ".sql", ".r", ".rb", ".go", ".rs",
            ".java", ".c", ".cpp", ".h", ".hpp", ".cs", ".php", ".vue",
        }
        is_text = file_path.suffix.lower() in text_extensions

        content = None
        if is_text:
            try:
                # Try to read as text with UTF-8
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                is_text = False

        return {
            "path": path,
            "name": file_path.name,
            "size": file_path.stat().st_size,
            "is_text": is_text,
            "content": content if is_text else None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete(
    "/file",
    summary="Delete file or folder",
    description="Delete a file or folder from workspace",
)
async def delete_file(
    request: Request,
    path: str,
) -> dict:
    """Delete a file or folder."""
    try:
        workspace = await get_agent_for_request(request)
        file_path = workspace.workspace_dir / path

        logging.getLogger(__name__).info(f"Deleting file: path={path}, file_path={file_path}, exists={file_path.exists()}")

        # Security check
        if not str(file_path.resolve()).startswith(str(workspace.workspace_dir.resolve())):
            raise HTTPException(status_code=403, detail="Access denied")

        if not file_path.exists():
            logging.getLogger(__name__).error(f"File not found: {file_path}")
            raise HTTPException(status_code=404, detail="File not found")

        # Check if preset file (not deletable)
        if file_path.name in PRESET_FILES:
            raise HTTPException(
                status_code=403,
                detail=f"Cannot delete preset file: {file_path.name}",
            )

        # Delete file or directory
        if file_path.is_file():
            file_path.unlink()
        elif file_path.is_dir():
            shutil.rmtree(file_path)

        return {"deleted": True, "path": path}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/file-upload",
    summary="Upload single file",
    description="Upload a single file to workspace",
)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    path: str = Body("", description="Target path relative to workspace root"),
) -> dict:
    """Upload a single file to workspace."""
    try:
        workspace = await get_agent_for_request(request)

        # Build target path
        if path:
            target_path = workspace.workspace_dir / path / file.filename
        else:
            target_path = workspace.workspace_dir / file.filename

        # Security check
        if not str(target_path.resolve()).startswith(str(workspace.workspace_dir.resolve())):
            raise HTTPException(status_code=403, detail="Access denied")

        # Create parent directories if needed
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        with open(target_path, "wb") as f:
            content = await file.read()
            f.write(content)

        return {
            "uploaded": True,
            "filename": file.filename,
            "path": str(target_path.relative_to(workspace.workspace_dir)),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/file-download",
    summary="Download single file",
    description="Download a single file from workspace",
)
async def download_file(request: Request, path: str):
    """Download a single file from workspace."""
    try:
        workspace = await get_agent_for_request(request)
        file_path = workspace.workspace_dir / path

        # Security check
        if not str(file_path.resolve()).startswith(str(workspace.workspace_dir.resolve())):
            raise HTTPException(status_code=403, detail="Access denied")

        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=404, detail="File not found")

        def iter_file():
            with open(file_path, "rb") as f:
                while chunk := f.read(8192):
                    yield chunk

        return StreamingResponse(
            iter_file(),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{file_path.name}"',
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
