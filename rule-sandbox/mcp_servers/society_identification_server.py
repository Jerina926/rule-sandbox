import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from mcp.server.fastmcp import FastMCP
from knowledge import engine, kb

mcp = FastMCP("society-identification")


@mcp.tool()
def list_societies() -> dict:
    return {
        "societies": [
            {"id": s["id"], "name": s["name"], "ico": s["ico"], "app": s["app"],
             "groups": s["groups"], "data": s["data"], "categories": [c["name"] for c in s["cats"]]}
            for s in kb.SOC
        ]
    }


@mcp.tool()
def identify(society_id: str, content: str) -> dict:
    return engine.detect(society_id, content)


@mcp.tool()
def build_questionnaire(society_id: str, category_name: str, content: str) -> dict:
    return {"sections": engine.build_questionnaire(society_id, category_name, content)}


if __name__ == "__main__":
    mcp.run()
