import os
import time
import asyncio
import argparse
from mu2e import slack

async def cleanup_task(slack_bot):
    """Periodic cleanup of inactive threads"""
    while True:
        await asyncio.sleep(300)  # Cleanup every 5 minutes
        await slack_bot.cleanup_threads()

async def run_bot(args):
    """Run the slack bot with async support"""
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
        
        # Start monitoring (this runs in the background)
        s.monitor()
        
        # Start cleanup task
        cleanup = asyncio.create_task(cleanup_task(s))
        
        print("Bot is running... Press Ctrl+C to stop")
        
        # Keep the event loop running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\nReceived shutdown signal...")
            cleanup.cancel()
            
            # Gracefully shutdown the bot
            await s.shutdown()
            
    except Exception as e:
        print(f"Error: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Mu2e Slack Bot with MCP Integration')
    parser.add_argument('--channel', 
                      default=os.getenv('MU2E_SLACK_CHANNEL'),
                      help='Slack channel name (optional - will respond to DMs and mentions)')
    parser.add_argument('--dm-only', action='store_true',
                      help='Only respond to direct messages')
    args = parser.parse_args()

    if not os.getenv('MU2E_SLACK_BOT_TOKEN'):
        raise ValueError("Slack bot token not found. Please set MU2E_SLACK_BOT_TOKEN environment variable")

    # Run the async bot
    asyncio.run(run_bot(args))

if __name__ == "__main__":
    main()
