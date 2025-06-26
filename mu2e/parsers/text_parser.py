"""
Plain text parser
"""

from .base_parser import BaseParser

class TextParser(BaseParser):
    """Parser for plain text files"""
    
    def get_text(self, rescale_image_max_dim=500):
        """Extract text from plain text document"""
        try:
            if hasattr(self.doc, 'read'):
                text = self.doc.read().decode('utf-8')
            else:
                text = str(self.doc)
            
            cleaned_text = self._clean_text(text)
            return cleaned_text, []
        except Exception as e:
            print(f"Error parsing text document: {e}")
            return "", []