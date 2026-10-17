import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from mcp.server.fastmcp import FastMCP
from knowledge import engine

mcp = FastMCP("risk-chain")


@mcp.tool()
def simulate_metrics(goal: str = "提高满意度", scope: str = "部分群体", strength: str = "中等",
                     data_source: str = "", live: dict = None) -> dict:
    return engine.simulate_metrics(goal, scope, strength, data_source, live or None)


@mcp.tool()
def deduce_groups(society_id: str, category_name: str, goal: str = "提高满意度",
                  scope: str = "部分群体", strength: str = "中等") -> dict:
    return {"groups": engine.deduce_groups(society_id, category_name, goal, scope, strength)}


@mcp.tool()
def deduce_chains(society_id: str, category_name: str, goal: str = "提高满意度",
                  scope: str = "部分群体", strength: str = "中等") -> dict:
    return engine.deduce_chains(society_id, category_name, goal, scope, strength)


if __name__ == "__main__":
    mcp.run()
