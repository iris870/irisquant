import os
import sys
import asyncio

# Ensure the root project directory is in the path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Print diagnostic info to PM2 logs
print(f"Starting Onchain Agent with executable: {sys.executable}")
print(f"sys.path: {sys.path}")

try:
    import structlog
    print("structlog successfully imported")
except ImportError as e:
    print(f"CRITICAL: Failed to import structlog: {e}")
    sys.exit(1)

# Now import and run the agent
from agents.onchain import run_agent

async def main():
    try:
        await run_agent()
    except Exception as e:
        print(f"Agent crashed during execution: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
