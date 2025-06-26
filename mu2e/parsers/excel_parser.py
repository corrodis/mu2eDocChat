"""
Excel (XLSX/XLS) parser
"""

from .base_parser import BaseParser

class ExcelParser(BaseParser):
    """Parser for Excel files"""
    
    def get_text(self, rescale_image_max_dim=500):
        """Extract text from Excel document"""
        try:
            import pandas as pd
            
            # Read all sheets
            excel_data = pd.read_excel(self.doc, sheet_name=None, header=None)
            text_parts = []
            
            for sheet_name, df in excel_data.items():
                text_parts.append(f"# Sheet: {sheet_name}\n")
                
                # Convert dataframe to markdown-like table
                for _, row in df.iterrows():
                    # Skip completely empty rows
                    if row.notna().any():
                        row_text = " | ".join([str(cell) if pd.notna(cell) else "" for cell in row])
                        text_parts.append(f"| {row_text} |")
                
                text_parts.append("")  # Empty line between sheets
            
            full_text = '\n'.join(text_parts)
            cleaned_text = self._clean_text(full_text)
            
            # Excel files typically don't have easily extractable images
            return cleaned_text, []
            
        except ImportError:
            print("pandas not installed. Install with: pip install pandas")
            return "", []
        except Exception as e:
            print(f"Error parsing Excel document: {e}")
            return "", []