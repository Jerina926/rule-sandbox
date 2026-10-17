import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from mcp.server.fastmcp import FastMCP
from knowledge import engine

mcp = FastMCP("plan-generation")


@mcp.tool()
def generate_plans(society_id: str, category_name: str, risk: int, hole: str, rec_plan: str,
                   goal: str = "提高满意度", scope: str = "部分群体", strength: str = "中等") -> dict:
    return engine.generate_plans(society_id, category_name,
                                  {"risk": risk, "hole": hole, "recPlan": rec_plan,
                                   "goal": goal, "scope": scope, "strength": strength})


if __name__ == "__main__":
    mcp.run()
