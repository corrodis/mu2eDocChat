import os
from dotenv import load_dotenv
load_dotenv()

from .utils import get_data_dir 
from .docdb import docdb
from .parsers import parser
