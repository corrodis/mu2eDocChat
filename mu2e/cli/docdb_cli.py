# mu2e/cli.py
import argparse
from mu2e.docdb import docdb
from mu2e import search, tools, anl

def main():
    parser = argparse.ArgumentParser(description='Mu2e DocDB utilities')
    parser.add_argument('--argo', action='store_true',
                       help='Use Argo embeddings instead of default collection')
    parser.add_argument('--argo-remote', action='store_true',
                       help='Use Argo embeddings instead of default collection, connect to argo-proxy through ssh tunnel')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Generate database
    generate_parser = subparsers.add_parser('generate', help='Generate embeddings for recent documents')
    generate_parser.add_argument('--days', type=int, default=30,
                               help='Number of days to look back (default: 30)')
    
    # Generate from local
    local_parser = subparsers.add_parser('generate-local', help='Generate embeddings from locally stored documents')
    
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
        collection = anl.get_collection() if args.argo else None
        collection = anl.get_collection(url="http://localhost:55019/v1/embed") if args.argo_remote else\
                     anl.get_collection() if args.argo else None
        collection_type = "Argo" if args.argo or args.argo_remote else "default"
        print(f"Generating {collection_type} embeddings for documents from the last {args.days} days...")
        db = docdb(collection=collection)
        db.generate(days=args.days)
        print("Done!")
        
    elif args.command == 'generate-local':
        collection = anl.get_collection() if args.argo else None
        collection = anl.get_collection(url="http://localhost:55019/v1/embed") if args.argo_remote else\
                     anl.get_collection() if args.argo else None
        collection_type = "Argo" if args.argo or args.argo_remote else "default"
        collection_type = "Argo" if args.argo else "default"
        print(f"Generating {collection_type} embeddings from locally stored documents...")
        processed = tools.generate_from_local(collection=collection)
        print(f"Done! Processed {processed} documents")
        
    elif args.command == 'search':
        # Select collection
        collection = anl.get_collection() if args.argo else None
        collection = anl.get_collection(url="http://localhost:55019/v1/embed") if args.argo_remote else\
                     anl.get_collection() if args.argo else None
        collection_type = "Argo" if args.argo or args.argo_remote else "default"
        collection_type = "Argo" if args.argo else "default"
        
        # Perform search
        if args.fulltext:
            print(f"Full-text search for: '{args.query}'")
            results = search.search_fulltext(args.query, n_results=args.top, collection=collection)
            search_type = "Full-text"
        else:
            print(f"Vector search using {collection_type} embeddings for: '{args.query}'")
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
