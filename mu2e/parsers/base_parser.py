"""
Base parser class with common functionality
"""

import re
import base64
import io
from abc import ABC, abstractmethod
from PIL import Image

class BaseParser(ABC):
    """Base class for all document parsers"""
    
    def __init__(self, document, doc_type):
        self.doc = document
        self.doc_type = doc_type
    
    def _clean_text(self, text):
        """Clean extracted text - remove latex formulas etc."""
        text = re.sub(r'<latexit[^>]*>.*?</latexit>', '[equation]', text)
        return text
    
    def _slides_format_as_markdown(self, text):
        """Format slide-like text as markdown"""
        lines = text.split('\n')
        formatted_lines = []
        in_list = False
    
        for line in lines:
            line = line.strip()
            if not line:
                if in_list:
                    formatted_lines.append('')
                in_list = False
                continue
            
            # Make first non-empty line a title
            if not formatted_lines:
                formatted_lines.append(f'# {line}')
                continue
    
            # Check for bullet points
            if line.startswith('•') or line.startswith('-') or line.startswith('●'):
                if not line[1:].strip():
                    continue
                formatted_lines.append(f'- {line[1:].strip()}')
                in_list = True
            elif in_list and not line[0].isupper():
                # Continuation of previous bullet point
                formatted_lines[-1] += f' {line}'
            elif line.startswith('○'):  # Second order list
                if not line[1:].strip():
                    continue
                formatted_lines.append(f'    - {line[1:].strip()}')
                in_list = True
            else:
                # Regular text
                formatted_lines.append(line)
                in_list = False
    
        return '\n'.join(formatted_lines)
    
    @abstractmethod
    def get_text(self, rescale_image_max_dim=500):
        """Extract text from document - must be implemented by subclasses"""
        pass
    
    def _resize_image(self, img, max_dim):
        """Resize image to max dimension while maintaining aspect ratio"""
        if max_dim is None:
            return img
            
        width, height = img.size
        if max(width, height) <= max_dim:
            return img
        
        if width > height:
            new_width = max_dim
            new_height = int(height * max_dim / width)
        else:
            new_height = max_dim
            new_width = int(width * max_dim / height)
        
        return img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    def _image_to_base64(self, img, format=None):
        """Convert PIL image to base64 string, preserving format when possible"""
        buffered = io.BytesIO()
        
        # Try to preserve original format, fallback to PNG
        if format and format.upper() in ['JPEG', 'JPG', 'PNG', 'WEBP', 'GIF']:
            save_format = 'JPEG' if format.upper() == 'JPG' else format.upper()
        else:
            save_format = 'PNG'
        
        img.save(buffered, format=save_format)
        return base64.b64encode(buffered.getvalue()).decode()
    
    def add_image_descriptions(self, text=None, images=None, method="claude-haiku"):
        """Add image descriptions to text - optional for subclasses"""
        return text