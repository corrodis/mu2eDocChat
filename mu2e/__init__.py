import os
from dotenv import load_dotenv
load_dotenv()

required_vars = [
    'MU2E_DOCDB_USERNAME',
    'MU2E_DOCDB_PASSWORD',
]

missing = [var for var in required_vars if not os.getenv(var)]
if missing:
    print(f"Warning: Missing environment variables: {', '.join(missing)}")
    print("Please ensure you have a .env file with these variables set")

from .utils import get_data_dir 
from .docdb import docdb
from .parser import pdf
