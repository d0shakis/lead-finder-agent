"""Command line interface."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress
from rich.table import Table

from leadfinder import cache
from leadfinder.agent import find_leads
from leadfinder.demo import DEMO_CITY, DEMO_TERM, load_demo
from leadfinder.export import save
from leadfinder.llm import PROVIDERS
from leadfinder.models import Lead
from leadfinder.sources.categories import ALIASES, CATEGORIES
from leadfinder.sources.osm import GeocodeError, OverpassError

app = typer.Typer(help="Find local businesses and score them as sales leads.", no_args_is_help=True)
console = Console()


def print_leads(leads: list[Lead], title: str, top: int) -> None:
    table = Table(title=title, show_lines=True)
    for col in ("Score", "Business", "Website", "Key problems"):
        table.add_column(col, overflow="fold")
    for lead in leads[:top]:
        a = lead.analysis
        color = "green" if a.score >= 70 else "yellow" if a.score >= 45 else "white"
        table.add_row(
            f"[{color}]{a.score}[/{color}]",
            lead.business.name,
            lead.business.website or "-",
            "\n".join(a.problems[:3]),
        )
    console.print(table)

    fallbacks = {l.analysis.provider for l in leads if "fallback" in l.analysis.provider}
    if fallbacks:
        console.print(
            f"[yellow]Warning: the LLM failed for some leads and rule-based scoring was used instead "
            f"({', '.join(sorted(fallbacks))}). Check your API key / model.[/yellow]"
        )


@app.command()
def search(
    term: str = typer.Argument(..., help='Business type, e.g. "plumber", "dentist", "gym".'),
    city: str = typer.Option(..., "--city", "-c", help='City or area, e.g. "Thessaloniki".'),
    limit: int = typer.Option(30, "--limit", "-n", min=1, max=200),
    provider: str = typer.Option("auto", "--provider", "-p", help=f"One of: {', '.join(PROVIDERS)}"),
    model: str = typer.Option(None, "--model", "-m", help="Override the provider's default model."),
    output: Path = typer.Option(Path("leads.csv"), "--output", "-o", help=".csv or .json"),
    skip_websites: bool = typer.Option(False, "--skip-websites", help="Don't fetch business websites."),
    top: int = typer.Option(10, help="How many leads to print."),
):
    """Find and score leads, e.g.  leadfinder search plumber --city Thessaloniki"""
    load_dotenv()
    with Progress(console=console, transient=True) as bar:
        task = bar.add_task("Starting...", total=1.0)

        def progress(msg: str, frac: float) -> None:
            bar.update(task, description=msg, completed=frac)

        try:
            result = asyncio.run(find_leads(term, city, limit, provider, model, skip_websites, progress=progress))
        except (GeocodeError, OverpassError, httpx.HTTPError) as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1) from None
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(2) from None

    if not result.leads:
        console.print(f"No '{term}' businesses found in {city}. Try another term (see `leadfinder categories`).")
        raise typer.Exit(0)

    print_leads(result.leads, f"Top leads: {term} in {result.area_name}", top)

    save(result.leads, output)
    console.print(
        f"Saved {len(result.leads)} leads to [bold]{output}[/bold] (scored by {result.leads[0].analysis.provider})"
    )


@app.command()
def categories():
    """List built-in business categories (other terms fall back to a name search)."""
    for name, tags in sorted(CATEGORIES.items()):
        aliases = [a for a, target in ALIASES.items() if target == name]
        tag_str = ", ".join(f"{k}={v}" for k, v in tags)
        console.print(f"[bold]{name}[/bold]  [dim]{tag_str}[/dim]" + (f"  aka {', '.join(aliases)}" if aliases else ""))


@app.command()
def demo(
    output: Path = typer.Option(None, "--output", "-o", help="Also save the demo leads (.csv or .json)."),
    top: int = typer.Option(10, help="How many leads to print."),
):
    """Show bundled sample results (no network needed)."""
    result = load_demo()
    print_leads(result.leads, f"Demo: {DEMO_TERM} in {DEMO_CITY} ({len(result.leads)} leads)", top)
    if output:
        save(result.leads, output)
        console.print(f"Saved {len(result.leads)} leads to [bold]{output}[/bold]")


@app.command("clear-cache")
def clear_cache():
    """Delete cached OpenStreetMap responses."""
    console.print(f"Removed {cache.clear()} cached responses from {cache.cache_dir()}")


if __name__ == "__main__":
    app()
