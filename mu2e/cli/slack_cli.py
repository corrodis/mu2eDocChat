import os
import time
import argparse
from mu2e import chat, slack

class SlackBot:
    def __init__(self):
        self.chat = chat.chat()
        
    def __call__(self, msg):
        print("bot called", msg)
        return self.chat(msg)

def main():
    parser = argparse.ArgumentParser(description='Mu2e Slack Bot')
    parser.add_argument('--channel', 
                      default=os.getenv('MU2E_SLACK_CHANNEL', 'llm_tests'),
                      help='Slack channel name (default: from MU2E_SLACK_CHANNEL or "llm_tests")')
    args = parser.parse_args()

    if not os.getenv('MU2E_SLACK_BOT_TOKEN'):
        raise ValueError("Slack bot token not found. Please set MU2E_SLACK_BOT_TOKEN environment variable")

    try:
        s = slack.slack(args.channel)
        s.processor = SlackBot
        print(f"Mu2e Slack bot started in channel: {args.channel}")
        s.monitor()
        
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nShutting down bot...")
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
