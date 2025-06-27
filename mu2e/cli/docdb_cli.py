# mu2e/cli.py
import argparse
from mu2e.docdb import docdb
from mu2e import search, tools
from mu2e.collections import get_collection, collection_names

def main():
    parser = argparse.ArgumentParser(description='Mu2e DocDB utilities')
    parser.add_argument('--collection', type=str, default='default',
                       help=f'Collection to use (choices: {", ".join(collection_names)}, default: default)')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Generate database
    generate_parser = subparsers.add_parser('generate', help='Generate embeddings for recent documents')
    generate_parser.add_argument('--days', type=int, default=30,
                               help='Number of days to look back (default: 30)')
    generate_parser.add_argument('--force-reload', action='store_true',
                               help='Force reload documents even if they already exist locally')
    
    # Generate from local
    local_parser = subparsers.add_parser('generate-local', help='Generate embeddings from locally stored documents')
    
    # Generate from local for all collections
    local_all_parser = subparsers.add_parser('generate-local-all', help='Generate embeddings for all non-default collections from locally stored documents')
    
    # Vector Search
    search_parser = subparsers.add_parser('search', help='Vector search in documents')
    search_parser.add_argument('query', type=str, help='Search query')
    search_parser.add_argument('--top', type=int, default=3,
                             help='Number of results to show (default: 3)')
    search_parser.add_argument('--fulltext', action='store_true',
                             help='Use full-text search instead of vector search')
    search_parser.add_argument('--days', type=int,
                             help='Limit search to documents from last N days')

    # List command
    list_parser = subparsers.add_parser('list', help='List recent documents')
    list_parser.add_argument('--days', type=int, default=1,
                           help='Number of days to look back (default: 1)')
    
    args = parser.parse_args()
    
    if args.command == 'generate':
        collection = get_collection(args.collection) if args.collection != 'default' else None
        force_text = " (force reload)" if args.force_reload else ""
        print(f"Generating {args.collection} embeddings for documents from the last {args.days} days{force_text}...")
        db = docdb(collection=collection)
        db.generate(days=args.days, force_reload=args.force_reload)
        print("Done!")
        
    elif args.command == 'generate-local':
        collection = get_collection(args.collection) if args.collection != 'default' else None
        print(f"Generating {args.collection} embeddings from locally stored documents...")
        processed = tools.generate_from_local(collection=collection)
        print(f"Done! Processed {processed} documents")
        
    elif args.command == 'generate-local-all':
        print("Generating embeddings for all non-default collections from locally stored documents...")
        tools.generate_from_local_all()
        print("Done! Processed all collections")
        
    elif args.command == 'search':
        # Select collection
        collection = get_collection(args.collection) if args.collection != 'default' else None
        
        # Perform search
        if args.fulltext:
            print(f"Full-text search for: '{args.query}'")
            results = search.search_fulltext(args.query, n_results=args.top, collection=collection)
            search_type = "Full-text"
        else:
            print(f"Vector search using {args.collection} embeddings for: '{args.query}'")
            # Vector search with optional date filtering
            if args.days:
                results = search.search_by_date(args.query, days_back=args.days, 
                                               collection=collection, n_results=args.top)
            else:
                results = search.search(args.query, collection=collection, n_results=args.top)
            search_type = "Vector"
        
        print(f"\n{search_type} search results:")
        for i, (doc_text, distance, doc_id, metadata) in enumerate(zip(
            results['documents'], results['distances'], results['ids'], results['metadata']
        )):
            print(f"\n{i+1}. Distance: {distance:.3f}")
            print(f"Title: {metadata.get('title', 'N/A')}")
            print(f"DocID: {metadata.get('docid', 'N/A')}")
            print(f"Link: https://mu2e-docdb.fnal.gov/cgi-bin/sso/ShowDocument?docid={metadata.get('docid', 'N/A')}")
            if 'abstract' in metadata:
                print(f"Abstract: {metadata['abstract'][:200]}...")
            print(f"Chunk: {doc_text[:300]}...")
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
