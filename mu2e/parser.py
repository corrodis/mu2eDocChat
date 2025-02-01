import pdfplumber
import re
import base64
import io
from PIL import Image
import numpy as np
import os

class pdf:
    """
    Library to parse pdf documents for the use with LLMs.

    Attributes:

    """

    def __init__(self, document=None):
        """
        Args:
            document (io.BytesI): the document
        """
        self.doc = document

    def _clean_text(self, text):
        """
        Cleans extracted text:
        -- replaces latex formulas with [equation]
        Args:
            text (str): input text
        Returns:
            text (str): the cleaned text
        """
        # latex formulas
        text = re.sub(r'<latexit[^>]*>.*?</latexit>', '[equation]', text)
        return text


    def _slides_format_as_markdown(self, text):
        """
        Adds markdown formating for slide like pdfs.
        Args:
            text (str): input text
        Returns:
            text (str): the formated output text
        """
        lines = text.split('\n')
        formatted_lines = []
        in_list = False
        slide_title = ""
    
        for line in lines:
            line = line.strip()
            if not line:
                if in_list:
                    formatted_lines.append('')
                in_list = False
                continue
            #print(line)
            
            # make the first not empty line a tiltle
            if not formatted_lines:
                formatted_lines.append(f'# {line}')
                continue
    
            # Check for bullet points
            if line.startswith('•') or line.startswith('-') or line.startswith('●') :
                if not line[1:].strip():
                    continue
                formatted_lines.append(f'- {line[1:].strip()}')
                in_list = True
            elif in_list and not line[0].isupper():
                # Continuation of previous bullet point
                formatted_lines[-1] += f' {line}'
            elif line.startswith('○'): ## second order list
                if not line[1:].strip():
                    continue
                formatted_lines.append(f'    - {line[1:].strip()}')
                in_list = True
            else:
                # Regular text
                formatted_lines.append(line)
                in_list = False
    
        return '\n'.join(formatted_lines)

    def get_sldies_text(self, rescale_image_max_dim=500):
        """
        Returns a string of extracted content for slide like pdf files. Images are indicated with [ImageX], a corresponding list with images is returned with PLI.Picture (orignal), and rescaled data64 for potential use with LLMs.
        
        Args:
            rescale_image_max_dim (int, optional): number of pixel of the largest image dimension of the data64 encoded image (for use with LLMs). Defaults to 500px.

        Returns:
            text (str): parsed text
            images (list(dict)): list with all found images. The dict contains img:PLI.Picture, data:data64 (rescaled to rescale_image_max_dim)
        """
        # TODO add table extraction
        extracted_text = ""
        images = []
        image_cnt = 0
        with pdfplumber.open(self.doc) as pdf:
            for i, page in enumerate(pdf.pages):
                print(i+1)
                #if i not in [4]:
                #    continue
                crop_box = (0, 0, page.width, page.height *0.96)
                text = page.crop(crop_box).extract_text()
                cleaned_text = self._clean_text(text)
                markdown_text = self._slides_format_as_markdown(cleaned_text)
                if text:
                    extracted_text += f"<page number={i+1}>{markdown_text}"
                    for img in page.images:
                        try:
                            img = Image.open(io.BytesIO(img['stream'].get_data()))
                        except:
                            continue
                        #resize the image if larger than rescale_image_max_dim (save tokens, LLM limitations)
                        w, h = img.width, img.height
                        if np.max([w,h]) > rescale_image_max_dim:
                            scale = np.max([w,h])/rescale_image_max_dim
                            img_resized = img.resize((int(w/scale), int(h/scale)))
                        else:
                            img_resized = img
                        buffered = io.BytesIO()
                        img_resized.save(buffered, format=img.format)
                        images.append({"page":i+1,
                                       "img":img,
                                       "data":base64.b64encode(buffered.getvalue()).decode('utf-8')
                                       })
                        image_cnt = image_cnt + 1
                        extracted_text += f"[Image{image_cnt}]"
                    extracted_text += "</page>\n"
        self.text = extracted_text
        self.images = images
        return extracted_text, images

    def images_plot(self, images=None):
        """
        Utility to plot all extracted images.
    
        Args:
            images (list(dict), optinalk): second outout of get_sldies_text. By default the self.images is used.
        """
        import matplotlib.pyplot as plt
        import math
        images_ = images if images else self.images
        n = len(images_)
        fig, axes = plt.subplots(math.ceil(n/4.), 4, figsize=(15, 15))
        axes = axes.flatten()
        for i, img in enumerate(images_):
            # Convert PIL Image to numpy array
            img_array = np.array(img['img'])
                
            # Plot the image
            axes[i].imshow(img_array)
            axes[i].axis('off')  # Turn off axis labels
            axes[i].set_title(f'Image {i+1}/page {img["page"]}')
            
        # Adjust the layout and display the plot
        plt.tight_layout()
        plt.show()
        
    def images_get_description(self, images=None, extracted_text=None, method="claude-haiku"):
        """
        Generate text descriptions of images. Different methods/models are avaiable: [claude-haiku, claude-sonnet, openAI-4oMini]

        Args:
            images (list(dict), optinal): second outout of get_sldies_text. By default the self.images is used.
            extracted_text (str, optinal): the extracted thext from get_sldies_text. By default the self.images is used.
            method (str): one of claude-sonnet, claude-haiku, openAI-4oMini. Deafults to claude-haiku.

        Returns:
            dict: image_id, summary
        """
        method_ = method.split("-")
        images_ = images if images else self.images
        text_ = extracted_text if extracted_text else self.text
        if method_[0] == "claude":
            return self._image_get_description_claude(images_, text_, method_[1])
        elif method_[0] == "openAI":
            return self._image_get_description_openAI(images_, text_, method_[1])
        else:
            raise NameError(f"The method {method} is not implemented. method needs to be one of [claude-sonnet, claude-heiku, openAI-?]")
            
    def _image_get_description_claude(self, images=None, extracted_text=None, model="haiku"):
        """
        Using the Claude API to generate image descriptions.
        
        Args:
            images (list(dict)): second outout of get_sldies_text. By default the self.images is used.
            extracted_text (str, optinal): the extracted thext from get_sldies_text. By default the self.text is used.
            model (str, optional): model to use [haiku, sonnet]. Deafults to haiku.

        Returns:
            dict: image_id, summary
        """
        #import mu2e # for the api key
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
             print("Warning: ANTHROPIC_API_KEY not set, skipping image descriptions with claude.")
             return []

        import requests
        import json
        images_ = images if images else self.images
        # limit to max 100 images
        if len(images_)>99:
            images_ = images_[:100]
        text_ = extracted_text if extracted_text else self.text
        
        models = {"haiku":"claude-3-haiku-20240307",
                  "sonnet":"claude-3-5-sonnet-20240620"}
        if model not in models:
            raise NameError(f"Model '{model}' is not implemented. Model needs to be one of {models.keys()}")

        
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        }
        imgs_payload = []
        for i, img in enumerate(images_):
            imgs_payload.append({"type": "text","text":f"Image{i+1}"})
            imgs_payload.append({"type": "image", "source": {"type": "base64","media_type": "image/"+img["img"].format.lower(), "data":img["data"]}})
            
        prompt = "Can you please generate a summary for each attached image focused on what is shown in the image."
        if text_:
            prompt += "These images are mebeded in the presentation below, see the corresponding tags of the form [ImageXX].\
                  The summaires will be used to replace the [ImageXX], it should add additional inforamtion and avoud repeating the inforamtion already present in the text."
        prompt += "Start each summary with Image...\
                   The summary will be used to genrate document embedings. \
                   Format requirements:\
                   - Use double quotes for all strings\
                   - No trailing commas\
                   - Array should be properly wrapped in square brackets\
                   - Each object should have exact format {\"image_id\": \"ImageXX\", \"summary\": \"SUMMARY\"}\
                   - No comments or additional text\
                   Example of expected format:\
[\
  {\"image_id\": \"Image1\", \"summary\": \"A red car parked on street\"},\
  {\"image_id\": \"Image2\", \"summary\": \"A brown dog sleeping\"}\
]\
                  Important: Return a single JSON array containing all summaries, not separate JSON objects.\
                  Use only straight quotes in JSON. For quoted terms within summaries, use single quotes (') or escaped double quotes (\\\").\
                  Do not include [ImageX] headers."
        if text_:
            prompt += "<presentation>"+text_+"<\presentation>"
        payload = {
            #"model": "claude-3-haiku-20240307",
            "model": models[model], # note, sonnet gets quite slow
                "messages": [{
                        "role": "user",
                        "content": imgs_payload + [{"type": "text", "text": prompt}]
                    }],
                "max_tokens": 4000
            }
        response = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
        if response.status_code != 200:
            raise RuntimeError(f"Somethign went wrong with the request to anthropic: {response.json()}")

        answer = json.loads(response.content.decode())
        out_text = answer['content'][0]['text']
        index = out_text.find('[')
        return out_text[index:] if index != -1 else out_text

    def _image_get_description_openAI(self, images=None, extracted_text=None, model="4oMini"):
        """
        Using the openAI API to generate image descriptions.
        
        Args:
            images (list(dict)): second outout of get_sldies_text. By default the self.images is used.
            extracted_text (str, optinal): the extracted thext from get_sldies_text. By default the self.text is used.
            model (str, optional): model to use [haiku, sonnet]. Deafults to haiku.

        Returns:
            dict: image_id, summary
        """
        #import mu2e
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            print("Warning: OPENAI_API_KEY not set, skipping image descriptions with OpenAI.")
            return []
        import requests

        images_ = images if images else self.images
        text_ = extracted_text if extracted_text else self.text
        
        models = {"4oMini":"gpt-4o-mini"}
        if model not in models:
            raise NameError(f"Model '{model}' is not implemented. Model needs to be one of {models.keys()}")
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        imgs_payload = []
        for i, img in enumerate(images_):
            imgs_payload.append({"type": "text","text":f"Image{i+1}"})
            imgs_payload.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img['data']}"}})
            
        prompt = "Can you please generate a summary for each attached image focused on what is shown in the image."
        if text_:
            prompt += "These images are mebeded in the presentation below, see the corresponding tags of the form [ImageXX].\
                  The summaires will be used to replace the [ImageXX], it should add additional inforamtion and avoud repeating the inforamtion already present in the text."
        prompt += "Start each summary with Image...\
                   The summary will be used to genrate document embedings. \
                   Please return only the summary in a json format with the format [{image_id:ImageXX, summary=SUMAMRY},{image_id:ImageYY, summary=SUMAMRY},....]\
                   Avoid any premble text other than this list of json objects."
        if text_:
            prompt += "<presentation>"+extracted_text+"<\presentation>"

        payload = {
            "model": models[model],
            "messages": [{
                    "role": "user",
                    "content": imgs_payload + [{"type": "text", "text": prompt}]
                        }],
            "max_tokens": 4000
        }

        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        if response.status_code != 200:
            raise RuntimeError(f"Somethign went wrong with the request to openAI: {response.content}")

        result = response.json()
        #print(result)
        out_text = result['choices'][0]['message']['content']
        index = out_text.find('[')
        rindex = out_text.rindex(']')
        return out_text[index:rindex+1] if index != -1 else out_text

    def _add_image_descriptions(self, descriptions, text=None):
        """
        Function to remove the image placeholder [Image1] with the summaries generated by images_get_description.

        Args:
            text (str, optinal): the parsed text from get_sldies_text. By default the self.text is used.
            descriptions (list(dict)): image descriptions from images_get_description. List of dicts with image_id:FigureXX, summar
        Returns:
            text(str): modified text
        """
        out_text = text if text else self.text
        for img in descriptions:
            out_text = out_text.replace("["+img['image_id']+"]", "["+img['summary']+"]")
        return out_text

    def add_image_descriptions(self, text=None, images=None, method="claude-haiku"):
        """
        Function to remove the image placeholder [Image1] with the summaries generated by images_get_description.

        Args:
            text (str): the parsed text from get_sldies_text. By default the self.text is used.
            images (list(dic)): images from get_sldies_text. By default the self.images is used.
            methods (str, optional): 
        Returns:
            text(str): one of claude-sonnet, claude-haiku, openAI-4oMini. Deafults to claude-haiku.
        """
        import json
        text_ = text if text else self.text
        images_ = images if images else self.images
        summaries = self.images_get_description(images_, text_, method)
        summaries = fix_json_quotes(summaries)
        try:
           summaries_ = json.loads(summaries)
        except:
           print(summaries)
           raise
        self.text = self._add_image_descriptions(summaries_, text_)
        return self.text

def fix_json_quotes(text):
    # Fix all types of quotes that might appear
    replacements = {
        '"': '"',  # Replace curly double quotes
        '"': '"',
        '"': '"',
        ''': "'",  # Replace curly single quotes
        ''': "'",
        '′': "'",  # Replace prime marks
        '″': '"',
        '‟': '"',  # Replace other Unicode quote variants
        '„': '"',
        '「': '"',
        '」': '"'
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    return text

