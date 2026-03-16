"""
SFG Lead-Generation Agent
--------------------------
Uses Claude Opus 4.6 with built-in web-search + web-fetch tools to scout the
internet for potential SFG customers, then saves every discovered lead into
the local SQLite CRM.

Architecture
  Claude orchestrates:
    web_search  — queries Google/Bing for relevant companies / contacts
    web_fetch   — reads landing pages / LinkedIn / directories for details
    save_lead   — a user-defined tool that writes the extracted lead to the CRM

The manual agentic loop runs until Claude signals "end_turn" (no more tool calls).
"""

import json
import os
from typing import Any

import anthropic
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

import crm

load_dotenv()
console = Console()


# ---------------------------------------------------------------------------
# User-defined tool: save_lead
# ---------------------------------------------------------------------------

SAVE_LEAD_TOOL: dict[str, Any] = {
    "name": "save_lead",
    "description": (
        "Save a potential SFG customer lead to the CRM database. "
        "Call this once per discovered lead with as much detail as you found."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "name":        {"type": "string", "description": "Contact person's full name"},
            "company":     {"type": "string", "description": "Company or organisation name"},
            "email":       {"type": "string", "description": "Contact email address"},
            "phone":       {"type": "string", "description": "Phone number"},
            "website":     {"type": "string", "description": "Company website URL"},
            "location":    {"type": "string", "description": "City, state / country"},
            "industry":    {"type": "string", "description": "Industry or business sector"},
            "description": {
                "type": "string",
                "description": "Why this company is a good SFG prospect — one or two sentences",
            },
            "source_url":  {"type": "string", "description": "URL where the lead was found"},
            "tags":        {
                "type": "array",
                "items": {"type": "string"},
                "description": "Relevant tags e.g. ['SMB','finance','US']",
            },
        },
        "required": ["company"],
    },
}


# ---------------------------------------------------------------------------
# Server-side tools (Anthropic-hosted)
# ---------------------------------------------------------------------------

WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search"}
WEB_FETCH_TOOL  = {"type": "web_fetch_20260209",  "name": "web_fetch"}


# ---------------------------------------------------------------------------
# Execute user-defined tools
# ---------------------------------------------------------------------------

def execute_save_lead(tool_input: dict) -> str:
    lead_id = crm.upsert_lead(
        name=tool_input.get("name"),
        company=tool_input.get("company"),
        email=tool_input.get("email"),
        phone=tool_input.get("phone"),
        website=tool_input.get("website"),
        location=tool_input.get("location"),
        industry=tool_input.get("industry"),
        description=tool_input.get("description"),
        source_url=tool_input.get("source_url"),
        tags=tool_input.get("tags", []),
    )
    company = tool_input.get("company", "unknown")
    console.print(f"  [green]✔ Lead saved[/green] → {company} (CRM id {lead_id})")
    return json.dumps({"status": "saved", "lead_id": lead_id, "company": company})


# ---------------------------------------------------------------------------
# Agentic loop
# ---------------------------------------------------------------------------

def run_scraper(search_query: str, sfg_description: str, max_leads: int = 20) -> int:
    """
    Run one scraping session. Returns number of leads saved.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set in the environment.")

    client = anthropic.Anthropic(api_key=api_key)
    crm.init_db()

    system_prompt = f"""You are an expert B2B lead-generation researcher for SFG.

SFG description:
{sfg_description}

Your job:
1. Use web_search and web_fetch to find companies or individuals who are strong
   prospects for SFG — people or businesses that would genuinely benefit from
   what SFG offers.
2. For each prospect you identify, call save_lead with every detail you can find
   (name, company, email, website, location, industry, why they're a good fit).
3. Aim for at least {max_leads} high-quality, distinct leads before finishing.
4. Avoid duplicates — if you've already saved a company, move on.
5. Be thorough: search directories, LinkedIn company pages, industry forums,
   news articles, conference attendee lists, etc.
6. After saving all leads, summarise what you found in plain text.

Be methodical: pick diverse search angles so you don't just find the same
companies again and again."""

    messages: list[dict] = [
        {"role": "user", "content": f"Research query: {search_query}"}
    ]

    all_tools = [WEB_SEARCH_TOOL, WEB_FETCH_TOOL, SAVE_LEAD_TOOL]

    console.rule("[bold cyan]SFG Lead Scraper Agent[/bold cyan]")
    console.print(f"Query: [italic]{search_query}[/italic]")
    console.print()

    leads_saved = 0
    iteration = 0

    while True:
        iteration += 1
        console.print(f"[dim]── Iteration {iteration} ──[/dim]")

        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=8192,
            thinking={"type": "adaptive"},
            system=system_prompt,
            tools=all_tools,
            messages=messages,
        )

        # Append assistant turn to history
        messages.append({"role": "assistant", "content": response.content})

        # Process content blocks
        tool_results: list[dict] = []
        has_user_tool = False

        for block in response.content:
            if block.type == "thinking":
                console.print(f"  [dim]💭 {block.thinking[:120]}…[/dim]")

            elif block.type == "text" and block.text.strip():
                console.print(Panel(block.text, title="Claude", border_style="blue"))

            elif block.type == "tool_use":
                if block.name == "save_lead":
                    has_user_tool = True
                    result_str = execute_save_lead(block.input)
                    leads_saved += 1
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    })
                # web_search / web_fetch are server-side — Anthropic handles them;
                # their results appear as server_tool_use / web_search_tool_result
                # blocks automatically.
                else:
                    console.print(f"  [cyan]🔍 {block.name}[/cyan]: {json.dumps(block.input)[:120]}")

            elif block.type == "server_tool_use":
                console.print(f"  [cyan]🌐 {block.name}[/cyan]")

            elif block.type == "web_search_tool_result":
                results = getattr(block, "content", [])
                count = len(results) if isinstance(results, list) else "?"
                console.print(f"  [green]↩ {count} search results[/green]")

            elif block.type == "web_fetch_tool_result":
                console.print("  [green]↩ page fetched[/green]")

        # Feed user-defined tool results back
        if tool_results:
            messages.append({"role": "user", "content": tool_results})

        # Stop when done
        if response.stop_reason == "end_turn":
            break

        # pause_turn means server-side tools hit their iteration limit — re-send
        if response.stop_reason == "pause_turn":
            continue

        # If no tool calls of any kind and stop_reason isn't tool_use, we're done
        if response.stop_reason not in ("tool_use", "pause_turn") and not has_user_tool:
            break

    crm.log_search_run(search_query, leads_saved)
    return leads_saved
