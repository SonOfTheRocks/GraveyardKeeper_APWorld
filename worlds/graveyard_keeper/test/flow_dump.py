import os
from pathlib import Path


FLOW_DUMP_ROOT = Path(
    os.environ.get("GK_FLOWGRAPH_DUMP_DIR")
    or Path(__file__).parents[1] / "dumps" / "FlowGraphExports"
)
