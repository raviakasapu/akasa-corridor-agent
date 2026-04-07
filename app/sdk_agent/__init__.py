# Import tool modules to trigger @tool decorator registration.
# This ensures all 18 tools are in the registry when the agent starts.
from .tools.simulation import drone_tools  # noqa: F401 — 10 simulation tools
from .tools.corridor import management  # noqa: F401 — 4 corridor tools
from .tools.compliance import ledger_tools  # noqa: F401 — 4 compliance tools
