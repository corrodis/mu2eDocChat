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
    
    def add_image_descriptions(self, text, images, max_workers=None):
        """
        Add image descriptions to text by replacing [Image X] with [Image X: DESCRIPTION]
        
        Args:
            text (str): Text with [Image X] placeholders
            images (list): List of base64 encoded images
            max_workers (int): Number of parallel workers for API calls (None = use env var)
            
        Returns:
            str: Text with image descriptions added
        """
        import os
        import re
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from ..utils import should_add_image_descriptions, getOpenAIClientForImages
        
        # Get max_workers from environment if not specified
        if max_workers is None:
            max_workers = int(os.getenv('MU2E_IMAGE_WORKERS', '6'))
        
        # Check if image descriptions should be added
        if not should_add_image_descriptions():
            return text
            
        # Find all [Image X] patterns
        image_pattern = r'\[Image (\d+)\]'
        image_matches = re.findall(image_pattern, text)
        
        if not image_matches or not images:
            return text
            
        print(f"Generating descriptions for {len(image_matches)} images...")
        
        # Get client once for all requests
        try:
            client = getOpenAIClientForImages()
        except ValueError as e:
            print(f"Warning: {e}, skipping image descriptions")
            return text
        
        # Get descriptions in parallel
        descriptions = [None] * len(image_matches)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_index = {
                executor.submit(self._get_single_image_description, client, text, images[i], i+1): i 
                for i in range(min(len(images), len(image_matches)))
            }
            
            # Collect results
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    descriptions[index] = future.result()
                    print(f"✓ Image {index+1} description generated")
                except Exception as e:
                    print(f"✗ Error getting description for image {index+1}: {e}")
                    descriptions[index] = "Image description unavailable"
        
        # Replace [Image X] with [Image X: DESCRIPTION]
        result_text = text
        for i, description in enumerate(descriptions, 1):
            if description:
                old_pattern = f"[Image {i}]"
                new_pattern = f"[Image {i}: {description}]"
                result_text = result_text.replace(old_pattern, new_pattern)
                
        return result_text
    
    def _detect_image_format(self, image_base64):
        """Detect image format from base64 data"""
        if image_base64.startswith('/9j/'):
            return 'jpeg'
        elif image_base64.startswith('iVBORw0KGgo'):
            return 'png'
        elif image_base64.startswith('UklGR'):
            return 'webp'
        elif image_base64.startswith('R0lGOD'):
            return 'gif'
        else:
            return 'jpeg'  # Default fallback
    
    def _get_single_image_description(self, client, document_text, image_base64, image_number):
        """Get description for a single image using OpenAI client"""
        import os
        
        # Get model configuration
        model = os.getenv('MU2E_IMAGE_LLM_MODEL', 'gpt-4o-mini')
        
        # Detect image format
        image_format = self._detect_image_format(image_base64)
        
        # Create prompt with document context
        prompt = self._create_image_description_prompt(document_text, image_number)
        
        # Make request using OpenAI client
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{image_format};base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=600  # Increased for detailed technical descriptions
        )
        
        return response.choices[0].message.content.strip()
    
    def _create_image_description_prompt(self, document_text, image_number):
        """Create adaptive prompt based on document context"""
        # Extract context around the image reference
        context_lines = []
        lines = document_text.split('\n')
        for i, line in enumerate(lines):
            if f'[Image {image_number}]' in line:
                # Get surrounding context (3 lines before and after)
                start = max(0, i-3)
                end = min(len(lines), i+4)
                context_lines = lines[start:end]
                break
        
        context = '\n'.join(context_lines) if context_lines else "No context available"
        
        return f"""Analyze this image and provide a description for document embedding and chat purposes.

Document context around this image:
{context}

Instructions:
- If this is a technical diagram, graph, plot, chart, or schema: Provide detailed description including axes labels, data trends, key values, relationships shown, and technical details
- If this is a photo, artwork, or general image: Provide a broad but informative description of what's visible
- If this is a screenshot or interface: Describe the interface elements, layout, and functionality shown
- Keep the description informative but concise (2-4 sentences)
- Focus on information that would be useful for search and understanding the document content
- Do not include phrases like "This image shows" or "The image depicts" - start directly with the description

Description:"""