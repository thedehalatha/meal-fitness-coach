import asyncio
import sys
import traceback

from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters


async def main():
    print("Initializing McpToolset...")
    mcp_toolset = McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=sys.executable,
                args=["app/mcp_server.py"],
            )
        )
    )
    print("Fetching tools...")
    try:
        session_manager = mcp_toolset._mcp_session_manager
        # Manually create session to get the trace
        session = await session_manager.create_session()
        async with session:
            tools = await session.list_tools()
            print("Tools found:", tools)
    except Exception:
        print("Connection failed with error:")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
