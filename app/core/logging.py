"""Color-coded logging for Akasa Corridor Agent.

Colors by:
- Severity: DEBUG=dim, INFO=blue, WARNING=yellow, ERROR=red
- Agent: coordinator=magenta, guardian=cyan, designer=green, compliance=blue
- Tool: simulation=yellow, corridor=cyan, compliance=green
"""

import logging
import sys
from typing import Optional

try:
    from rich.console import Console
    from rich.logging import RichHandler
    from rich.theme import Theme
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


# Agent colors
AGENT_COLORS = {
    "coordinator": "magenta",
    "guardian": "cyan",
    "designer": "green",
    "compliance": "blue",
    "default": "white",
}

# Tool colors
TOOL_COLORS = {
    "start_simulation": "yellow",
    "step_simulation": "yellow",
    "check_block_membership": "bright_yellow",
    "generate_correction": "red",
    "create_corridor": "cyan",
    "validate_corridor": "green",
    "verify_chain_integrity": "green",
    "generate_certificate": "bright_green",
    "default": "white",
}

# Custom theme for Rich console
AKASA_THEME = Theme({
    "agent.coordinator": "bold magenta",
    "agent.guardian": "bold cyan",
    "agent.designer": "bold green",
    "agent.compliance": "bold blue",
    "tool.simulation": "yellow",
    "tool.corridor": "cyan",
    "tool.compliance": "green",
    "status.ok": "bold green",
    "status.error": "bold red",
    "status.warning": "bold yellow",
    "marker.worker_start": "bold magenta",
    "marker.worker_end": "dim magenta",
})


def setup_logging(level: int = logging.INFO, use_rich: bool = True) -> None:
    """Configure color-coded logging."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    if use_rich and HAS_RICH:
        console = Console(theme=AKASA_THEME, force_terminal=True)
        handler = RichHandler(
            console=console,
            show_time=True,
            show_level=True,
            show_path=False,
            rich_tracebacks=True,
            tracebacks_show_locals=False,
            markup=True,
            log_time_format="[%H:%M:%S]",
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
    else:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        ))

    root_logger.addHandler(handler)

    # Reduce noise
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)


def log_agent(logger: logging.Logger, agent: str, message: str) -> None:
    """Log with agent context."""
    color = AGENT_COLORS.get(agent.lower(), "white")
    if HAS_RICH:
        logger.info(f"[bold {color}][{agent}][/] {message}")
    else:
        logger.info(f"[{agent}] {message}")


def log_tool(logger: logging.Logger, tool_name: str, message: str, success: bool = True) -> None:
    """Log tool execution."""
    status = "OK" if success else "ERROR"
    logger.info(f"[TOOL] {tool_name} {status}: {message}")
