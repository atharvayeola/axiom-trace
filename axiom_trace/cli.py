"""
Axiom Trace CLI.

Provides commands for recording, querying, exporting, verifying, and
inspecting trace vaults.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer
from typing_extensions import Annotated

from axiom_trace.core import AxiomTrace
from axiom_trace.schema import AxiomValidationError
from axiom_trace.backend import AxiomLockError


app = typer.Typer(
    name="axiom",
    help="Axiom Trace - Local-first trace vault for AI agents",
    add_completion=False
)


@app.command()
def record(
    vault: Annotated[str, typer.Option("--vault", "-v", help="Path to vault directory")],
    event: Annotated[str, typer.Option("--event", "-e", help="Path to JSON event file")]
):
    """
    Record an event to the vault.
    
    Reads a JSON event from file and appends it to the vault.
    Prints the frame_id on success.
    """
    vault_path = Path(vault)
    event_path = Path(event)
    
    if not event_path.exists():
        typer.echo(f"Error: Event file not found: {event}", err=True)
        raise typer.Exit(1)
    
    try:
        with open(event_path, "r", encoding="utf-8") as f:
            event_data = json.load(f)
    except json.JSONDecodeError as e:
        typer.echo(f"Error: Invalid JSON in event file: {e}", err=True)
        raise typer.Exit(1)
    
    try:
        with AxiomTrace(str(vault_path)) as trace:
            frame_id = trace.record(event_data)
            typer.echo(frame_id)
    except AxiomValidationError as e:
        typer.echo(f"Validation error: {e.message}", err=True)
        for err in e.errors:
            typer.echo(f"  - {err}", err=True)
        raise typer.Exit(1)
    except AxiomLockError as e:
        typer.echo(f"Lock error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def query(
    vault: Annotated[str, typer.Option("--vault", "-v", help="Path to vault directory")],
    prompt: Annotated[str, typer.Option("--prompt", "-p", help="Search prompt")],
    limit: Annotated[int, typer.Option("--limit", "-l", help="Maximum results")] = 5,
    filters: Annotated[Optional[str], typer.Option("--filters", "-f", help="JSON filters")] = None
):
    """
    Query the vault for matching frames.
    
    Prints matching frames as a JSON array.
    """
    vault_path = Path(vault)
    
    if not vault_path.exists():
        typer.echo(f"Error: Vault not found: {vault}", err=True)
        raise typer.Exit(1)
    
    filter_dict = None
    if filters:
        try:
            filter_dict = json.loads(filters)
        except json.JSONDecodeError as e:
            typer.echo(f"Error: Invalid JSON in filters: {e}", err=True)
            raise typer.Exit(1)
    
    try:
        with AxiomTrace(str(vault_path), auto_flush=False) as trace:
            results = trace.query(prompt, limit, filter_dict)
            typer.echo(json.dumps(results, indent=2))
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command("export")
def export_session(
    vault: Annotated[str, typer.Option("--vault", "-v", help="Path to vault directory")],
    session: Annotated[str, typer.Option("--session", "-s", help="Session ID to export")],
    out: Annotated[str, typer.Option("--out", "-o", help="Output file path")],
    format: Annotated[str, typer.Option("--format", "-f", help="Export format")] = "md"
):
    """
    Export a session to a file.
    
    Generates a Markdown document with all frames from the session.
    """
    vault_path = Path(vault)
    
    if not vault_path.exists():
        typer.echo(f"Error: Vault not found: {vault}", err=True)
        raise typer.Exit(1)
    
    try:
        with AxiomTrace(str(vault_path), auto_flush=False) as trace:
            trace.export_session(session, out, format)
            typer.echo(f"Exported session {session} to {out}")
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def verify(
    vault: Annotated[str, typer.Option("--vault", "-v", help="Path to vault directory")]
):
    """
    Verify vault integrity.
    
    Checks hash chain and manifest consistency.
    Returns non-zero exit code on failure.
    """
    vault_path = Path(vault)
    
    if not vault_path.exists():
        typer.echo(f"Error: Vault not found: {vault}", err=True)
        raise typer.Exit(1)
    
    try:
        with AxiomTrace(str(vault_path), auto_flush=False) as trace:
            result = trace.verify_integrity()
            
            typer.echo("=" * 50)
            typer.echo("AXIOM TRACE INTEGRITY VERIFICATION")
            typer.echo("=" * 50)
            typer.echo(f"Vault: {vault}")
            typer.echo(f"Frames checked: {result['checked_frames']}")
            typer.echo(f"Head hash: {result['head_hash'][:32]}..." if result['head_hash'] else "Head hash: (empty)")
            typer.echo("")
            
            if result["ok"]:
                typer.echo("✓ Integrity verification PASSED")
            else:
                typer.echo(f"✗ Integrity verification FAILED")
                typer.echo(f"  Error: {result['error']}")
                raise typer.Exit(1)
                
    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def stats(
    vault: Annotated[str, typer.Option("--vault", "-v", help="Path to vault directory")]
):
    """
    Display vault statistics.
    
    Shows frame count, size, and other metrics.
    """
    vault_path = Path(vault)
    
    if not vault_path.exists():
        typer.echo(f"Error: Vault not found: {vault}", err=True)
        raise typer.Exit(1)
    
    try:
        with AxiomTrace(str(vault_path), auto_flush=False) as trace:
            result = trace.stats()
            
            typer.echo("=" * 50)
            typer.echo("AXIOM TRACE STATISTICS")
            typer.echo("=" * 50)
            typer.echo(f"Vault: {vault}")
            typer.echo(f"Frame count: {result['frame_count']}")
            typer.echo(f"Bytes written: {result['bytes_written']:,}")
            typer.echo(f"Approx size: {result['approx_size_mb']:.2f} MB")
            typer.echo(f"Head hash: {result['head_hash'][:32]}..." if result['head_hash'] else "Head hash: (empty)")
            
            if result["over_limit"]:
                typer.echo("")
                typer.echo("⚠️  WARNING: Vault size exceeds configured limit!")
                
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


# Color codes for event types
EVENT_COLORS = {
    "thought": "\033[36m",      # Cyan
    "tool_call": "\033[33m",    # Yellow
    "tool_output": "\033[32m",  # Green
    "user_input": "\033[35m",   # Magenta
    "final_result": "\033[32m", # Green
    "error": "\033[31m",        # Red
    "system_event": "\033[90m", # Gray
}
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"


def _format_frame(frame: dict, colorize: bool = True) -> str:
    """Format a frame for display."""
    event_type = frame.get("event_type", "unknown")
    timestamp = frame.get("timestamp", "")[:19]  # Trim to seconds
    content = frame.get("content", {})
    
    # Get display text
    text = content.get("text", "")
    if not text and "output" in content:
        text = content["output"]
    if not text and "input" in content:
        text = content["input"]
    if not text and "json" in content:
        text = json.dumps(content["json"])[:100]
    
    # Truncate long text
    if len(text) > 120:
        text = text[:117] + "..."
    
    # Format with colors
    if colorize:
        color = EVENT_COLORS.get(event_type, "")
        success_icon = ""
        if "success" in frame:
            success_icon = " ✓" if frame["success"] else " ✗"
        return f"{DIM}{timestamp}{RESET} {color}{BOLD}{event_type:13}{RESET}{success_icon} {text}"
    else:
        return f"{timestamp} {event_type:13} {text}"


@app.command()
def log(
    vault: Annotated[str, typer.Option("--vault", "-v", help="Path to vault")] = ".axiom_trace",
    limit: Annotated[int, typer.Option("--limit", "-l", help="Number of entries")] = 20,
    session_filter: Annotated[Optional[str], typer.Option("--session", "-s", help="Filter by session ID")] = None,
    event_type: Annotated[Optional[str], typer.Option("--type", "-t", help="Filter by event type")] = None,
    no_color: Annotated[bool, typer.Option("--no-color", help="Disable colors")] = False
):
    """
    Show recent traces in a pretty format.
    
    Displays traces with colors and easy-to-read formatting.
    Perfect for quick debugging and monitoring.
    
    Examples:
        axiom log                    # Show last 20 traces
        axiom log --limit 50         # Show last 50 traces
        axiom log --type thought     # Show only thoughts
        axiom log --session abc123   # Filter by session
    """
    import orjson
    
    vault_path = Path(vault)
    frames_file = vault_path / "frames.jsonl"
    
    if not frames_file.exists():
        typer.echo(f"No traces found in {vault}", err=True)
        typer.echo("Start tracing with: from axiom_trace import trace; trace.log('hello')")
        raise typer.Exit(0)
    
    # Read frames
    frames = []
    with open(frames_file, "rb") as f:
        for line in f:
            if line.strip():
                frame = orjson.loads(line)
                
                # Apply filters
                if session_filter and frame.get("session_id") != session_filter:
                    continue
                if event_type and frame.get("event_type") != event_type:
                    continue
                    
                frames.append(frame)
    
    # Show last N frames
    frames = frames[-limit:]
    
    if not frames:
        typer.echo("No matching traces found.")
        raise typer.Exit(0)
    
    # Header
    colorize = not no_color and sys.stdout.isatty()
    if colorize:
        typer.echo(f"{BOLD}{'─' * 80}{RESET}")
        typer.echo(f"{BOLD}AXIOM TRACE LOG{RESET} ({len(frames)} entries)")
        typer.echo(f"{BOLD}{'─' * 80}{RESET}")
    else:
        typer.echo("-" * 80)
        typer.echo(f"AXIOM TRACE LOG ({len(frames)} entries)")
        typer.echo("-" * 80)
    
    # Frames
    for frame in frames:
        typer.echo(_format_frame(frame, colorize))
    
    if colorize:
        typer.echo(f"{BOLD}{'─' * 80}{RESET}")


@app.command()
def watch(
    vault: Annotated[str, typer.Option("--vault", "-v", help="Path to vault")] = ".axiom_trace",
    session_filter: Annotated[Optional[str], typer.Option("--session", "-s", help="Filter by session")] = None,
    no_color: Annotated[bool, typer.Option("--no-color", help="Disable colors")] = False
):
    """
    Watch traces in real-time (like tail -f).
    
    Monitors the trace file and displays new entries as they arrive.
    Press Ctrl+C to stop.
    
    Examples:
        axiom watch                  # Watch all traces
        axiom watch --session abc    # Watch specific session
    """
    import time
    import orjson
    
    vault_path = Path(vault)
    frames_file = vault_path / "frames.jsonl"
    
    colorize = not no_color and sys.stdout.isatty()
    
    if colorize:
        typer.echo(f"{BOLD}Watching {vault} for new traces...{RESET}")
        typer.echo(f"{DIM}Press Ctrl+C to stop{RESET}")
        typer.echo(f"{BOLD}{'─' * 80}{RESET}")
    else:
        typer.echo(f"Watching {vault} for new traces...")
        typer.echo("Press Ctrl+C to stop")
        typer.echo("-" * 80)
    
    # Track file position
    last_pos = 0
    if frames_file.exists():
        last_pos = frames_file.stat().st_size
    
    try:
        while True:
            if not frames_file.exists():
                time.sleep(0.5)
                continue
            
            current_size = frames_file.stat().st_size
            
            if current_size > last_pos:
                with open(frames_file, "rb") as f:
                    f.seek(last_pos)
                    new_data = f.read()
                    last_pos = f.tell()
                
                for line in new_data.split(b"\n"):
                    if line.strip():
                        try:
                            frame = orjson.loads(line)
                            
                            # Apply filter
                            if session_filter and frame.get("session_id") != session_filter:
                                continue
                            
                            typer.echo(_format_frame(frame, colorize))
                        except Exception:
                            pass
            
            time.sleep(0.2)
            
    except KeyboardInterrupt:
        typer.echo("\nStopped watching.")


def main():
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()
