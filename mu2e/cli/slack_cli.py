import os
import time
import asyncio
import argparse
import signal
import sys
from mu2e import slack

async def cleanup_task(slack_bot):
    """Periodic cleanup of inactive threads"""
    while True:
        await asyncio.sleep(300)  # Cleanup every 5 minutes
        await slack_bot.cleanup_threads()

async def run_bot(args):
    """Run the slack bot with async support"""
    shutdown_event = asyncio.Event()
    
    def signal_handler():
        """Handle shutdown signals gracefully"""
        print("\nReceived shutdown signal...")
        shutdown_event.set()
    
    # Set up signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)
    
    try:
        # Create slack bot instance
        if args.dm_only:
            s = slack.slack(channel_name=None)
            print("Mu2e Slack bot started (DMs only)")
        else:
            s = slack.slack(channel_name=args.channel)
            if args.channel:
                print(f"Mu2e Slack bot started in channel: {args.channel}")
            else:
                print("Mu2e Slack bot started (responds to mentions and DMs)")
        
        # Configure tool notifications
        if args.no_tool_notifications:
            s.show_tool_notifications = False
            print("Tool notifications disabled")
        
        # Start monitoring (this runs in the background)
        s.monitor()
        
        # Start cleanup task
        cleanup = asyncio.create_task(cleanup_task(s))
        
        print("Bot is running... Press Ctrl+C to stop")
        
        # Wait for shutdown signal
        await shutdown_event.wait()
        
        # Cancel cleanup task
        cleanup.cancel()
        try:
            await cleanup
        except asyncio.CancelledError:
            pass
        
        # Gracefully shutdown the bot
        await s.shutdown()
        print("Bot shutdown complete")
            
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Mu2e Slack Bot with MCP Integration')
    parser.add_argument('--channel', 
                      default=os.getenv('MU2E_SLACK_CHANNEL'),
                      help='Slack channel name (optional - will respond to DMs and mentions)')
    parser.add_argument('--dm-only', action='store_true',
                      help='Only respond to direct messages')
    parser.add_argument('--no-tool-notifications', action='store_true',
                      help='Disable tool usage notifications in Slack')
    args = parser.parse_args()

    if not os.getenv('MU2E_SLACK_BOT_TOKEN'):
        raise ValueError("Slack bot token not found. Please set MU2E_SLACK_BOT_TOKEN environment variable")

    # Run the async bot with clean shutdown
    try:
        asyncio.run(run_bot(args))
    except KeyboardInterrupt:
        # This should not happen now, but just in case
        print("\nShutdown complete")
        sys.exit(0)

if __name__ == "__main__":
    main()
