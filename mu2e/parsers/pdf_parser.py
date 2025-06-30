"""
PDF parser
"""

import pdfplumber
import io
from PIL import Image
import numpy as np
from tqdm import tqdm
from .base_parser import BaseParser

class PDFParser(BaseParser):
    """Parser for PDF files"""
    
    def get_text(self, rescale_image_max_dim=500):
        """Extract text and images from PDF document"""
        extracted_text = ""
        images = []
        image_cnt = 0
        
        with pdfplumber.open(self.doc) as pdf:
            for i, page in enumerate(tqdm(pdf.pages, desc="Processing pages")):
                crop_box = (0, 0, page.width, page.height * 0.96)
                text = page.crop(crop_box).extract_text()

                # Extract tables
                tables = page.crop(crop_box).extract_tables()
                table_text = ""
                if tables:
                    for table_idx, table in enumerate(tables):
                        table_text += f"\n**Table {table_idx + 1}:**\n"
                        for row in table:
                            # Filter out None values and clean cells
                            cleaned_row = [str(cell).strip() if cell else "" for cell in row]
                            table_text += "| " + " | ".join(cleaned_row) + " |\n"
                        table_text += "\n"

                combined_text = text + table_text

                cleaned_text = self._clean_text(combined_text)
                markdown_text = self._slides_format_as_markdown(cleaned_text)
                if combined_text.strip():
                    extracted_text += f"<page number={i+1}>{markdown_text}"
                    
                    # Extract images
                    for img_info in page.images:
                        #try:
                        if True:
                            if img_info.get("imagemask") == True: # not an image
                                continue
                            stream = img_info['stream']
                            filter_obj = stream.get("Filter")
                            if 'FlateDecode' in str(filter_obj):
                                continue
                                        
                                # Get the raw, decompressed pixel data
                                data = stream.get_data()
                                        
                                # Get the image dimensions
                                width = img_info['width']
                                height = img_info['height']
                                        
                                # Determine the color mode
                                # For now, we'll handle the common RGB and Grayscale cases
                                mode = 'RGB' if '/DeviceRGB' in img_info.get('colorspace', []) else 'L'

                                # Reconstruct the image from the raw bytes
                                img = Image.frombytes(mode, (width, height), data)
                            else:
                                img = Image.open(io.BytesIO(stream.get_data()))
                            img = self._resize_image(img, rescale_image_max_dim)
                            img_base64 = self._image_to_base64(img, img.format)
                            images.append(img_base64)
                            image_cnt += 1
                            extracted_text += f"[Image {image_cnt}]"
                        #except Exception as e:
                        #    print(f"Error processing image on page {i+1}: {e}")
                        #    continue
                    
                    extracted_text += "</page>\n"
        
        return extracted_text, images