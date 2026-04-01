import os
import sys
import asyncio

# Ensure the root project directory is in the path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Print diagnostic info to PM2 logs
print(f"Starting News Agent with executable: {sys.executable}")
print(f"sys.path: {sys.path}")

try:
    import structlog
    print("structlog successfully imported")
except ImportError as e:
    print(f"CRITICAL: Failed to import structlog: {e}")
    sys.exit(1)

# Now import and run the agent
try:
    from agents.news import run_agent
except ImportError as e:
    print(f"CRITICAL: Failed to import run_agent from agents.news: {e}")
    sys.exit(1)

async def main():
    print("In main() async function")
    try:
        print("Calling run_agent()...")
        await run_agent()
    except Exception as e:
        print(f"Agent crashed during execution: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    print("Script __name__ is __main__")
    try:
        print("Running asyncio.run(main())...")
        asyncio.run(main())
        print("asyncio.run(main()) finished")
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
