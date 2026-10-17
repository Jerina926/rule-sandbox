import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from mcp.server.fastmcp import FastMCP
from knowledge import engine

mcp = FastMCP("risk-chain")


@mcp.tool()
def simulate_metrics(scope: str, strength: str, data_source: str = "", live: dict = None) -> dict:
    return engine.simulate_metrics(scope, strength, data_source, live or None)


@mcp.tool()
def deduce_groups(society_id: str, category_name: str) -> dict:
    return {"groups": engine.deduce_groups(society_id, category_name)}


@mcp.tool()
def deduce_chains(society_id: str, category_name: str) -> dict:
    return engine.deduce_chains(society_id, category_name)


if __name__ == "__main__":
    mcp.run()
