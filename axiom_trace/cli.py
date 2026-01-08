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


def main():
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()
