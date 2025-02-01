# mu2e/cli.py
import argparse
from mu2e.docdb import docdb
from mu2e import rag, tools

def main():
    parser = argparse.ArgumentParser(description='Mu2e DocDB utilities')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Generate database
    generate_parser = subparsers.add_parser('generate', help='Generate embeddings for recent documents')
    generate_parser.add_argument('--days', type=int, default=30,
                               help='Number of days to look back (default: 30)')
    
    # RAG Search
    search_parser = subparsers.add_parser('search', help='Search documents using RAG')
    search_parser.add_argument('query', type=str, help='Search query')
    search_parser.add_argument('--top', type=int, default=3,
                             help='Number of results to show (default: 3)')

    # List command
    list_parser = subparsers.add_parser('list', help='List recent documents')
    list_parser.add_argument('--days', type=int, default=1,
                           help='Number of days to look back (default: 1)')
    
    args = parser.parse_args()
    
    if args.command == 'generate':
        print(f"Generating embeddings for documents from the last {args.days} days...")
        db = docdb()
        db.generate(days=args.days)
        print("Done!")
        
    elif args.command == 'search':
        print(f"RAG lookup for: '{args.query}'")
        scores, doc_ids = rag.find(args.query)
        
        print("\nTop matches:")
        for score, doc_id in zip(scores[:args.top], doc_ids[:args.top]):
            doc = tools.load(doc_id)
            print(f"\nScore: {score:.3f}")
            print(f"Title: {doc['title']}")
            print(f"Link: https://mu2e-docdb.fnal.gov/cgi-bin/sso/ShowDocument?docid={doc['docid']}")
            if 'abstract' in doc:
                print(f"Abstract: {doc['abstract'][:200]}...")
            print("-" * 80)

    elif args.command == 'list':
        print(f"Listing documents from the last {args.days} days:")
        db = docdb()
        recent_docs = db.list_latest(days=args.days)
        
        for doc in recent_docs:
            print(f"\nDocID: {doc['id']}")
            print(f"Title: {doc['tite']}")  # Note: there's still that typo in the API
            print(f"Authors: {', '.join(doc['authors'])}")
            print(f"Last Updated: {doc['last_updated']}")
            print(f"Link: https://mu2e-docdb.fnal.gov/cgi-bin/sso/ShowDocument?docid={doc['id']}")
            print("-" * 80)    

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
