#!/usr/bin/env python3
"""
SFG Web-Scraper CRM — command-line interface

Usage examples
--------------
  # Run a scraping session
  python src/main.py scrape --query "SaaS companies in Texas needing fleet management"

  # List all leads
  python src/main.py leads

  # List only new leads
  python src/main.py leads --status new

  # Update a lead's status
  python src/main.py update 7 --status contacted --notes "Called on Monday"

  # Show CRM stats
  python src/main.py stats
"""

import argparse
import os
import sys

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import box

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))
import crm
import agent as agent_module

console = Console()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def render_leads_table(leads: list[dict]):
    if not leads:
        console.print("[yellow]No leads found.[/yellow]")
        return

    table = Table(
        title=f"SFG CRM — {len(leads)} lead(s)",
        box=box.ROUNDED,
        show_lines=True,
    )
    table.add_column("#",         style="dim",    width=4)
    table.add_column("Company",   style="bold",   min_width=18)
    table.add_column("Name",      min_width=14)
    table.add_column("Email",     min_width=20)
    table.add_column("Industry",  min_width=14)
    table.add_column("Location",  min_width=14)
    table.add_column("Status",    min_width=10)
    table.add_column("Why SFG?",  min_width=28)

    status_colours = {
        "new":       "cyan",
        "contacted": "yellow",
        "qualified": "green",
        "closed":    "bright_green",
        "rejected":  "red",
    }

    for lead in leads:
        status = lead.get("status", "new")
        colour = status_colours.get(status, "white")
        table.add_row(
            str(lead["id"]),
            lead.get("company") or "",
            lead.get("name") or "",
            lead.get("email") or "",
            lead.get("industry") or "",
            lead.get("location") or "",
            f"[{colour}]{status}[/{colour}]",
            (lead.get("description") or "")[:60],
        )

    console.print(table)


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------

def cmd_scrape(args):
    sfg_description = (
        args.sfg_description
        or os.environ.get("SFG_DESCRIPTION")
        or "SFG — a business services company looking for new clients"
    )
    query = args.query
    max_leads = args.max_leads

    console.print(f"[bold]SFG Description:[/bold] {sfg_description}")
    console.print(f"[bold]Search Query:[/bold]    {query}")
    console.print(f"[bold]Target Leads:[/bold]    {max_leads}")
    console.print()

    saved = agent_module.run_scraper(
        search_query=query,
        sfg_description=sfg_description,
        max_leads=max_leads,
    )
    console.print()
    console.print(f"[bold green]✅ Session complete — {saved} lead(s) saved to CRM.[/bold green]")


def cmd_leads(args):
    crm.init_db()
    leads = crm.get_all_leads(status=args.status)
    render_leads_table(leads)


def cmd_update(args):
    crm.init_db()
    crm.update_lead_status(args.id, status=args.status, notes=args.notes)
    console.print(f"[green]Lead {args.id} updated → status={args.status}[/green]")


def cmd_stats(args):
    crm.init_db()
    stats = crm.get_stats()
    console.print()
    console.print("[bold underline]CRM Stats[/bold underline]")
    console.print(f"  Total leads   : [cyan]{stats['total_leads']}[/cyan]")
    console.print(f"  Search runs   : [cyan]{stats['search_runs']}[/cyan]")
    console.print()
    table = Table(box=box.SIMPLE)
    table.add_column("Status")
    table.add_column("Count", justify="right")
    for status, count in stats["by_status"].items():
        table.add_row(status, str(count))
    console.print(table)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sfg-crm",
        description="SFG Web-Scraper CRM — find & track potential customers",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # scrape
    p_scrape = sub.add_parser("scrape", help="Run a lead-generation scraping session")
    p_scrape.add_argument(
        "--query", "-q",
        required=True,
        help='Natural-language search goal, e.g. "logistics companies in Ohio"',
    )
    p_scrape.add_argument(
        "--max-leads", "-n",
        type=int,
        default=20,
        dest="max_leads",
        help="Target number of leads to discover (default: 20)",
    )
    p_scrape.add_argument(
        "--sfg-description",
        default=None,
        dest="sfg_description",
        help="Override SFG description (also via SFG_DESCRIPTION env var)",
    )

    # leads
    p_leads = sub.add_parser("leads", help="List CRM leads")
    p_leads.add_argument(
        "--status",
        default=None,
        choices=["new", "contacted", "qualified", "closed", "rejected"],
        help="Filter by status",
    )

    # update
    p_update = sub.add_parser("update", help="Update a lead's status")
    p_update.add_argument("id", type=int, help="Lead ID")
    p_update.add_argument(
        "--status", "-s",
        required=True,
        choices=["new", "contacted", "qualified", "closed", "rejected"],
    )
    p_update.add_argument("--notes", default=None)

    # stats
    sub.add_parser("stats", help="Show CRM statistics")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "scrape": cmd_scrape,
        "leads":  cmd_leads,
        "update": cmd_update,
        "stats":  cmd_stats,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
