"""Small Rich presentation seam with a strict plain-text fallback."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Iterable

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

Output = Callable[[str], None]


class Presenter:
    """Render rich terminal affordances only for an interactive terminal."""

    def __init__(self, output: Output = print) -> None:
        self.output = output
        self.enabled = output is print and sys.stdout.isatty() and not os.environ.get("NO_COLOR")
        self.console = Console() if self.enabled else None

    def header(self, text: str) -> None:
        if self.console:
            self.console.print(f"[bold]{text}[/bold]")
        else:
            self.output(text)

    def command(self, text: str) -> None:
        if self.console:
            self.console.print(f"[dim]{text}[/dim]")
        else:
            self.output(text)

    def success(self, text: str) -> None:
        if self.console:
            self.console.print(f"[green]{text}[/green]")
        else:
            self.output(text)

    def warning(self, text: str) -> None:
        if self.console:
            self.console.print(f"[yellow]{text}[/yellow]")
        else:
            self.output(text)

    def failure(self, text: str) -> None:
        if self.console:
            self.console.print(f"[red]{text}[/red]")
        else:
            self.output(text)

    def panel(self, title: str, lines: Iterable[str]) -> None:
        materialized = list(lines)
        if self.console:
            self.console.print(Panel("\n".join(materialized), title=title, border_style="cyan"))
        else:
            self.output(f"Artifact: {title}")
            for line in materialized:
                self.output(f"  {line}")

    def table(self, title: str, columns: list[str], rows: Iterable[list[str]]) -> None:
        materialized = list(rows)
        if self.console:
            table = Table(title=title, border_style="cyan")
            for column in columns:
                table.add_column(column)
            for row in materialized:
                table.add_row(*row)
            self.console.print(table)
        else:
            self.output(f"Artifact: {title}")
            self.output("  " + " | ".join(columns))
            for row in materialized:
                self.output("  " + " | ".join(row))

    def prompt(self, done: str, next_step: str) -> str:
        self.success(f"✓ Done: {done}")
        if self.console:
            self.console.print(f"[magenta]→ Next: {next_step}[/magenta]")
            return "   Continue? [Y/n] "
        self.output(f"→ Next: {next_step}")
        return "Continue? [Y/n] "
