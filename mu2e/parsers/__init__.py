"""
Modular document parsers for mu2e DocDB
"""

from .base_parser import BaseParser
from .pdf_parser import PDFParser
from .pptx_parser import PPTXParser
from .docx_parser import DOCXParser
from .excel_parser import ExcelParser
from .text_parser import TextParser

# Parser mapping
PARSER_MAP = {
    'pdf': PDFParser,
    'pptx': PPTXParser,
    'vnd.openxmlformats-officedocument.presentationml.presentation': PPTXParser,
    'docx': DOCXParser,
    'vnd.openxmlformats-officedocument.wordprocessingml.document': DOCXParser,
    'xlsx': ExcelParser,
    'vnd.openxmlformats-officedocument.spreadsheetml.sheet': ExcelParser,
    'txt': TextParser,
    'text/plain': TextParser,
}

def parser(document, doc_type):
    """Create appropriate parser for document type"""
    if doc_type not in PARSER_MAP:
        raise NotImplementedError(f"Document type {doc_type} not supported yet. Available: {', '.join(PARSER_MAP.keys())}")
    
    return PARSER_MAP[doc_type](document, doc_type)

__all__ = ['parser', 'BaseParser']