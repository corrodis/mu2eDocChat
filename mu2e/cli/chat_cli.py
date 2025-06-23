import argparse
import asyncio
import signal
from mu2e.chat_mcp import Chat
import sys


async def health_check():
    """Check health of chat services."""
    print("Checking chat services health...")
    
    chat = Chat()
    status = await chat.health_check()
    
    print(f"\nHealth Check Results:")
    print(f"Overall Status: {'Healthy' if status['overall'] == 'healthy' else 'Degraded'}")
    print(f"\nServices:")
    
    for service, info in status.items():
        if service == "overall":
            continue
        status_text = "OK" if info["status"] == "healthy" else "FAIL"
        print(f"  {service}: {status_text} ({info['url']})")
    
    # Provide helpful instructions if services are down
    if status["overall"] != "healthy":
        print(f"\nTroubleshooting:")
        
        if "unreachable" in status["openai_api"]["status"]:
            print(f"  - OpenAI API not reachable. Check if your API server is running at {status['openai_api']['url']}")
            print(f"  - if you are usiing an ssh tunnel, check that the port is forwarded")
            print(f"  - Set MU2E_CHAT_BASE_URL environment variable if using a different URL")
        
        if "unreachable" in status["mcp_server"]["status"]:
            print(f"  - MCP server not reachable. Start it with:")
            print(f"    python -m mu2e.mcp.docdb.server_fastmcp --port 1223")
            print(f"  - Set MU2E_CHAT_MCP_URL environment variable if using a different URL")
    else:
        print(f"\nAll services are healthy! Ready to chat.")
    await chat.cleanup()


async def chat_main(args):
    """Main chat function."""
    # Create chat instance
    chat = Chat()
    shutdown_requested = False

    def signal_handler(signum, frame):
        nonlocal shutdown_requested
        print("\nGood luck!")
        shutdown_requested = True
    signal.signal(signal.SIGINT, signal_handler)
    
    # Quick health check before starting
    status = await chat.health_check()
    if status["overall"] != "healthy":
        print("Warning: Some services are not healthy. Run 'mu2e-chat --health' for details.")
        print("Chat may not work properly until services are restored.\n")
    if status["openai_api"]["status"] != "healthy":
        print("LLM interface is not running properly.")
        await chat.cleanup()
        sys.exit(1)
    try:
        if args.query:
            # One-off question mode
            response = await chat.chat(args.query)
            print(response)
        else:
            # Interactive mode
            print("Mu2e docdb chat (Ctrl+C to exit)")
            print("Ask questions about Mu2e documents, procedures, or analysis\n")
            
            while not shutdown_requested:
                try:
                    query = input("Chat: ")
                    if not query.strip():
                        continue
                    
                    response = await chat.chat(query)
                    print(f"\nAssistant: {response}\n")
                    
                except Exception as e:
                    print(f"Error: {str(e)}")
    finally:
        await chat.cleanup()
        # Clean up
        #if chat.mcp:
        #    await chat.cleanup()


def main():
    parser = argparse.ArgumentParser(description='Mu2e docdb Chat Assistant')
    parser.add_argument('query', type=str, nargs='?', 
                       help='Query to ask. If not provided, starts interactive mode')
    parser.add_argument('--health', action='store_true',
                       help='Check health of chat services and exit')
    
    args = parser.parse_args()
    
    if args.health:
        asyncio.run(health_check())
        return
    
    asyncio.run(chat_main(args))


if __name__ == "__main__":
    main()
