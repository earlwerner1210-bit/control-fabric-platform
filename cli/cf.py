#!/usr/bin/env python3
"""
Control Fabric Platform CLI.

Usage:
    python cli/cf.py cases list
    python cli/cf.py cases resolve <case_id>
    python cli/cf.py reconciliation run
    python cli/cf.py audit export
    python cli/cf.py health
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import click

from sdk.control_fabric.client import ControlFabricClient

API_URL = os.getenv("CF_API_URL", "http://localhost:8000")
CF_USER = os.getenv("CF_USER", "admin")
CF_PASS = os.getenv("CF_PASS", "admin")


def get_client() -> ControlFabricClient:
    client = ControlFabricClient(API_URL)
    try:
        client.login(CF_USER, CF_PASS)
    except Exception:
        click.echo("Warning: login failed — some commands may not work", err=True)
    return client


@click.group()
def cli():
    """Control Fabric Platform CLI"""


@cli.group()
def cases():
    """Manage reconciliation cases."""


@cases.command("list")
@click.option("--format", "fmt", default="table", type=click.Choice(["table", "json"]))
def cases_list(fmt: str):
    """List all open cases."""
    data = get_client().cases.list()
    if fmt == "json":
        click.echo(json.dumps(data, indent=2))
        return
    click.echo(f"\nOpen cases: {data.get('open_case_count', 0)}\n")
    for c in data.get("cases", [])[:20]:
        sev = c.get("severity", "").upper()
        color = {
            "CRITICAL": "red",
            "HIGH": "yellow",
            "MEDIUM": "cyan",
            "LOW": "green",
        }.get(sev, "white")
        click.echo(
            f"  {click.style(f'[{sev}]', fg=color):<14} {c['case_id'][:12]}  {c['title'][:55]}"
        )


@cases.command("resolve")
@click.argument("case_id")
@click.option("--by", default="cli-operator", help="Who is resolving")
@click.option("--note", prompt="Resolution note", help="Resolution note")
def cases_resolve(case_id: str, by: str, note: str):
    """Resolve a reconciliation case."""
    get_client().cases.resolve(case_id, by, note)
    click.echo(click.style(f"Case resolved: {case_id}", fg="green"))


@cli.group()
def reconciliation():
    """Run and inspect reconciliation."""


@reconciliation.command("run")
def recon_run():
    """Run cross-plane reconciliation."""
    click.echo("Running reconciliation...")
    result = get_client().reconciliation.run()
    click.echo(
        click.style(f"Complete: {result.get('new_cases_this_run', 0)} new cases", fg="green")
    )
    click.echo(f"  Critical: {result.get('by_severity', {}).get('critical', 0)}")
    click.echo(f"  High:     {result.get('by_severity', {}).get('high', 0)}")
    click.echo(f"  Total:    {result.get('open_cases', 0)} open")


@cli.group()
def audit():
    """Audit export commands."""


@audit.command("export")
@click.option("--format", "fmt", default="json", type=click.Choice(["json", "manifest"]))
@click.option("--out", default=None, help="Output file path")
def audit_export(fmt: str, out: str | None):
    """Export audit records."""
    client = get_client()
    data = client.audit.manifest() if fmt == "manifest" else client.audit.export_json()
    output = json.dumps(data, indent=2)
    if out:
        with open(out, "w") as f:
            f.write(output)
        click.echo(click.style(f"Exported to {out}", fg="green"))
    else:
        click.echo(output)


@cli.command()
def health():
    """Check platform health."""
    try:
        result = get_client().health()
        health_status = result.get("status", "unknown")
        color = "green" if health_status == "healthy" else "red"
        click.echo(click.style(f"Platform: {health_status}", fg=color))
        for k, v in result.items():
            if k != "status":
                click.echo(f"  {k}: {v}")
    except Exception as e:
        click.echo(click.style(f"Platform unreachable: {e}", fg="red"))


@cli.command()
def stats():
    """Platform statistics."""
    data = get_client().ingress.stats()
    click.echo(f"\nControl Fabric Platform\n{'─' * 30}")
    for k, v in data.items():
        click.echo(f"  {k:<28} {v}")


if __name__ == "__main__":
    cli()
