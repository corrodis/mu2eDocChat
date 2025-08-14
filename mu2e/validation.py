import os 
import json
from itertools import islice
import mu2e
from mu2e import tools 
from mu2e import utils
from mu2e import search
from mu2e.chat_mcp import Chat
from pathlib import Path
import pandas as pd
from .collections import get_collection


class BenchmarkGenerator:

    def __init__(self, client=None, model=None, max_documents=100):
        self.client = tools.getOpenAIClient()
        self.model = utils.get_model()
        self.max_documents = max_documents
        self.dataset = []
        self.score_data = []
            

    def extract_key_points(self, document_text):
        prompt = f"Extract the key points from this document. Choose fact-like points a user might be looking for. Return each key point on a separate line starting with '- ':\n\n{document_text}"
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
            )
        
        keypoints_list = [line.strip()[2:] for line in response.choices[0].message.content.split('\n') if line.strip().startswith('- ')]
        return keypoints_list


    def generate_question(self, document_text, keypoint):
        prompt = f"Given this document:\n\n{document_text}\n\nAnd this key fact from the document:'{keypoint}'\n\nWrite a simple, generic question that a user might search for or ask, where this fact would be part of the answer. Make it the kind of broad question someone would actually type into a search box, not overly specific or technical. Focus on the main topic or issue, not all the details."
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()


    def generate_selections(self, document_text, keypoint, question):
        prompt = f"Given this document:\n\n{document_text}\n\nThis question: '{question}'\n\nAnd knowing that the correct answer involves: '{keypoint}'\n\nGenerate 4 multiple choice answers where the first one is correct based on the keypoint and 3 are plausible but incorrect. Make the incorrect answers believable and related to the topic, but clearly wrong. Format: each answer on a new line. No numbering of any form in front."
        response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt }]
            )
        return response.choices[0].message.content.split('\n\n')

    def generate_dataset(self, num=None):
        if num is None:
            num = self.max_documents

        question_id = 0
        
        for doc in islice(tools.iterate_documents(), num):
            doc_id = doc['doc_id']
            print(doc_id)
            doc = tools.load2(doc_id)

            
            for file in doc['files']:
                
                document_text = file['text']
                keypoints_list = self.extract_key_points(document_text)

                if len(keypoints_list) > 1:
                    question_id+=1
                    keypoint = keypoints_list[1]
                    print(keypoint)
                    question = self.generate_question(document_text, keypoint)
                    selections = self.generate_selections(document_text, keypoint, question)
    
                    self.dataset.append( {"doc_id":doc_id, 
                                      "question":question,
                                      "question_id":question_id,
                                      "keypoint":keypoint,
                                      "selections":selections} )    

                else:
                    continue

        return self.dataset

    
    def chATLAS_generate_qa_pair(self):

        
        system_prompt = """
You are an expert at crafting high-quality question-answer pairs tailored to evaluate AI models, focusing on technical relevance and clarity. Based on the provided document, a single entry in a large database of related content, create one QA pair for each of the following personas:

1. **Early Career Physics Student**:
   - Focus on straightforward, fundamental, or procedural questions aimed at someone new to HEP-related work.
   - Questions should prioritize basic understanding and operational details.

2. **Established Worker**:
   - Craft questions exploring intermediate-level technical discussions, practical implications, or connections between related topics.
   - Questions should reflect a practical, problem-solving perspective.

3. **Experienced Professional**:
   - Focus on complex, nuanced, or historical questions that require deeper knowledge of the domain or long-term thinking.
   - Questions should push the boundaries of understanding, exploring broader implications or sophisticated analyses.

**General Requirements**:
- Base the questions strictly on the provided page content. Avoid speculative or unsupported queries.
- Questions and answers must not explicitly mention or reference "this document."
- Ensure answers are concise (1-3 sentences) and directly address the question.
- Do not include generic questions or those focusing on significance or implications without supporting content.

**Techniques to Improve QA Quality**:
- Extract specific, explicit, and meaningful details.
- Differentiate question focus based on persona style and expertise level.
- If the page content lacks sufficient meaningful information, return an empty array.

Format the response as a JSON object with this structure:
{
    "qa_pairs": [
        {
            "type": "early_career|established_worker|experienced_professional",
            "question": "...",
            "answer": "..."
        },
        ...
    ]
"""
        question_id = 0
        for doc in islice(tools.iterate_documents(), self.max_documents):
            
            doc_id = doc['doc_id']
            print(doc_id)
            doc = tools.load2(doc_id)

            for file in doc['files']:
                document_text = file['text']
            
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": f"{system_prompt}. \n\nProvided is the document: {document_text}"}]
                )

                content = response.choices[0].message.content.strip()

                # Format the response and convert to JSON
                
                first_brace_index = content.find('{')
                if first_brace_index == -1:
                    print(f"No JSON object found in response:\n{content}")
                    continue

                question_id+=1

    
                if content[0] != '{':
                    clean_json_str = content[first_brace_index:-3]
                else:
                    clean_json_str = content[first_brace_index:]



                try:
                    parsed = json.loads(clean_json_str)
                    qa_pairs = parsed.get("qa_pairs", [])
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON for doc {doc_id}, question {question_id}: {e}")
                    qa_pairs = []
        
                self.dataset.append({
                    "doc_id": doc_id,
                    "question_id": question_id,
                    "qa_pairs": qa_pairs
                })
            
        return self.dataset
        


    def save(self, filename):
        base = utils.get_data_dir()
        output_path = base / f'{filename}.json'
        
        with open(output_path, 'w') as file:
            print(f"dumping dataset with {len(self.dataset)} items")
            print("Saving to:", output_path.resolve())

            json.dump(self.dataset, file, indent=4)


    
    async def model_eval_mc(self, question, selections):
        c = Chat(recreate_mcp_per_message=True)
        answer = await c.chat(f"{question} \n Select the correct answer from the following options: {selections}")
        await c.cleanup()
        return answer
        


    async def check_retrieval(self, collection, filename='benchmark_questions', num_results=7000, test_zeros=False):
        
        base = utils.get_data_dir()
        output_path = base / f'{filename}.json'

        data = []
        index = []
        distance = 0
        position = 0
        missing_ids=[]

        with open(output_path, 'r') as file:
            d = json.load(file)
            for entry in d:
                question = entry['question']
                doc_id = entry['doc_id']
                question_id = entry['question_id']
        
                print("Question:", question)
                print("ID:", question_id)

                col = get_collection(collection)
                
                results = search.search(query=question, collection=col, n_results=num_results)


                distances = results['distances']
        
                print("Target doc_id:", doc_id)
        
                found = False


                ids = results['ids']

                for idx, retrieved_id in enumerate(ids):
                    if retrieved_id.startswith(doc_id + '_'):
                        distance = distances[idx]
                        position = idx
                        data.append([distance, position])
                        found = True
                        break
        
                if not found:
                    data.append(["Not Found", -1])  # or any placeholder for missing doc
                    missing_ids.append(doc_id)
        
                index.append(question_id)
                score = (1 - position * (1 / 100)) if (found and position < 100) else 0
                print("Score:", score)

                
                if (test_zeros == True and score == 0):
                    #print("Top chunk for above score:\n", results['documents'][0])
                    
                    response = await self.model_eval_mc(question, entry['selections'])
                    print("Response:", response)
                    
        
                self.score_data.append({"question": question, "score": score})

            print("Missing IDs:", missing_ids)
            existing_ids = col.get()['ids']
            base_ids = set(i.split('_')[0] for i in existing_ids)
            
            for missing in set(missing_ids):
                if missing not in base_ids:
                    print(f"Not in collection: {missing}")
                else:
                    print(f"In collection but not retrieved: {missing}")
        
        return pd.DataFrame(data, index=index, columns=['distance', 'position'])

    

    def check_chATLAS(self, collection, filename='chATLAS_questions', question_num=1, num_results=7000):

        base = utils.get_data_dir()
        output_path = base / f'{filename}.json'

        data = []
        index = []
        distance = 0
        position = 0
        missing_ids = []


        with open(output_path, 'r') as file:
            d = json.load(file)
            for entry in d:
                qa_pairs = entry.get("qa_pairs", [])
        
                try:
                    question = entry['qa_pairs'][question_num]['question']
                except (IndexError, KeyError, TypeError):
                    continue
                    
                doc_id = entry['doc_id']
                question_id = entry['question_id']

                print("Question:", question)
                print("ID:", question_id)

                col = get_collection(collection)
                results = search.search(query=question, collection=col, n_results=num_results)
                distances = results['distances']


                print("Target doc_id:", doc_id)

                found = False
                ids = results['ids']

                for idx, retrieved_id in enumerate(ids):
                    if retrieved_id.startswith(doc_id + '_'):
                        distance = distances[idx]
                        position = idx
                        data.append([distance, position])
                        found = True
                        break
        
                if not found:
                    data.append(["Not Found", -1])
                    missing_ids.append(doc_id)
        
                index.append(question_id)
                score = (1 - position * (1 / 100)) if (found and position < 100) else 0
                print("Score:", score)

                
                self.score_data.append({"question": question, "score": score})
        
        
        return pd.DataFrame(data, index=index, columns=['distance', 'position'])


    
    
 
    def save_retrieval(self, collection, filename='benchmark_scores'):

        base = utils.get_data_dir()
        output_path = base / f'{filename}_{collection}.json'
        

        with open(output_path, 'w') as file:
            print(f"dumping dataset with {len(self.score_data)} items")
            print("Saving to:", output_path.resolve())


            json.dump(self.score_data, file, indent=4)
        


    
    
