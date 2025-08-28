import argparse
from mu2e import validation
import asyncio

def generate(filename: str = "benchmark_questions", num=None):
    val = validation.BenchmarkGenerator()
    val.generate_dataset(num=num)
    val.save(filename)

def generate_keywords(filename: str = "keyword_queries", num=None):
    val = validation.BenchmarkGenerator()
    val.reform_questions(num=num)
    val.save(filename)
    

def check_retrieval(collection: str = "default", test_zeros: bool=False):
    val = validation.BenchmarkGenerator()
    asyncio.run(val.check_retrieval(collection, test_zeros=test_zeros))
    val.save_retrieval(collection)
    

def chATLAS_generate(filename: str = "chATLAS_questions", num=None):
    val = validation.BenchmarkGenerator()
    val.chATLAS_generate_qa_pair(num=num)
    val.save(filename)
    

def check_chATLAS(collection: str = "default", question_num: int=1):
    val = validation.BenchmarkGenerator()
    val.check_chATLAS(collection, question_num=question_num)
    val.save_retrieval(collection, filename="chATLAS_benchmark_scores")

    
def main():
    parser = argparse.ArgumentParser(description='Benchmarking tools')
    subparsers = parser.add_subparsers(dest='command', required=True)

    generate_parser = subparsers.add_parser('generate', help='Generate dataset from recent documents')
    generate_parser.add_argument("--filename", default="benchmark_questions", help='Specify output filename')
    generate_parser.add_argument("--num", type=int, default=100, help='Number of questions to be generated') 
        
    chATLAS_parser = subparsers.add_parser('generate-chATLAS', help='Generate dataset from chATLAS system prompt')
    chATLAS_parser.add_argument("--filename", default="chATLAS_questions", help='Specify chATLAS output filename')
    chATLAS_parser.add_argument("--num", type=int, default=100, help='Number of questions to be generated') 

    queries_parser = subparsers.add_parser('keyword-queries', help='Generate queries containing keywords')
    queries_parser.add_argument("--num", type=int, default=100, help='Number of queries to generate')
    
    test_parser = subparsers.add_parser('test-retrieval', help ='Evaluate the dataset')
    test_parser.add_argument(
            '--collection',
            type=str,     
            default='default',    
            help='Specify a collection (default if not given)'
        )
    test_parser.add_argument('--test-zeros', action='store_true', help='Test mc for retrievals that score 0')

    chATLAS_test_parser = subparsers.add_parser('test-chATLAS', help='Test qa pairs from chATLAS questions')

    

    chATLAS_test_parser.add_argument(
        "--rigor",
        type=str,
        default="early_career",
        help="Determine which difficulty of question to use"
    )

    chATLAS_test_parser.add_argument(
            '--collection',
            type=str,     
            default='default',    
            help='Specify a collection (default if not given)'
        )
    

    args = parser.parse_args()

    if args.command == 'generate':
        generate(filename=args.filename, num=args.num)
    elif args.command == 'generate-chATLAS':
        chATLAS_generate(filename=args.filename, num=args.num)
    elif args.command == 'test-retrieval':
        check_retrieval(args.collection, test_zeros=args.test_zeros)
    elif args.command == 'keyword-queries':
        generate_keywords(num=args.num)
    elif args.command == 'test-chATLAS':
        rigor_map = {
            "early_career": 0,
            "established_worker": 1,
            "experienced_professional": 2
        }
        check_chATLAS(args.collection, question_num=rigor_map[args.rigor])
        

if __name__ == "__main__":
    main()