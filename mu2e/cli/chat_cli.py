import argparse
from mu2e.chat import chat, InputParser

def main():
    parser = argparse.ArgumentParser(description='Mu2e docdb Chat Assistant')
    parser.add_argument('query', type=str, nargs='?', 
                       help='Query to ask. If not provided, starts interactive mode')
    parser.add_argument('--api', choices=['antropic', 'openAI', 'Argo'], default='antropic',
                       help='Which API to use (default: antropic)')
    parser.add_argument('--list-commands', action='store_true',
                       help='List available chat commands and exit')
    
    args = parser.parse_args()
    
    if args.list_commands:
        InputParser.list_commands(print_help=True)
        return

    agent = chat(api=args.api)
    
    if args.query:
        # One-off question mode
        print(agent(args.query))
    else:
        # Interactive mode
        print("Mu2e docdb chat  (Ctrl+C to exit)")
        print("Type '\\help' to see available commands")
        while True:
            try:
                query = input("\nChat: ")
                if query.strip() == "\\help":
                    InputParser.list_commands(print_help=True)
                    continue
                if not query.strip():
                    continue
                response = agent(query)
                print("\nAssistant:", response)
            except KeyboardInterrupt:
                print("\nGood luck!")
                break
            except Exception as e:
                print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
