from abc import ABC, abstractmethod
import re
from mu2e import tools, rag
import anthropic
import json
import requests
from openai import OpenAI
from abc import ABC, abstractmethod
import os

# input parser
class InputParser():
    """
    Parses direct user input for the use in the mu2e ML/AI agent.
    This parser allows to encode settings in the user string that we might want to remove from the actual user query that is processed.
    """
    @staticmethod
    def list_commands(print_help: bool = False) -> dict:
        """
        Returns all available command arguments that can be used in queries.
        
        Args:
            print_help (bool): If True, prints a nicely formatted help message.
                             If False, just returns the commands dictionary.        

        Returns:
            dict: Dictionary of commands and their descriptions
        """
        commands = {
            # Model selection
            "\\model=<name>": {
                "description": "Select LLM model to use",
                "examples": ["\\model=sonnet", "\\model=haiku", "\\model=4o-mini"],
                "values": {
                    "Anthropic": ["sonnet", "haiku", "opus"],
                    "OpenAI": ["4o-mini", "4o", "o1-mini", "o1-preview"],
                    "Argo": ["argo-4o", "argo-o1"]
                }
            },
            
            # RAG
            "\\rag": {
                "description": "Enable RAG (Retrieval Augmented Generation)",
                "example": "\\rag What is the latest status of the tracker?"
            },
            
            # Document reference
            "\\mu2e-docdb-<number>": {
                "description": "Reference specific DocDB document",
                "example": "\\mu2e-docdb-51478 What does this document say?"
            },
            
            # Temperature
            "\\temperature=<value>": {
                "description": "Set temperature for LLM response (0.0-1.0)",
                "example": "\\temperature=0.7"
            },
            
            # Settings
            "\\print-settings": {
                "description": "Show current settings in response"
            }
        }

        if print_help:
            print("\nAvailable Commands for Mu2e Chat:")
            print("=" * 40)
            for cmd, info in commands.items():
                print(f"\n{cmd}")
                print(f"  {info['description']}")
                if 'example' in info:
                    print(f"  Example: {info['example']}")
                if 'examples' in info:
                    print(f"  Examples: {', '.join(info['examples'])}")
                if 'values' in info:
                    print("  Available values:")
                    for api, models in info['values'].items():
                        print(f"    {api}: {', '.join(models)}")
            print("\n" + "=" * 40)

        return commands
    def __init__(self):
        pass
    def __call__(self, user_query):
        """
        Parse the user query into a standardized dictionary format.

        Args:
            user_query (str): The raw query string from the user.

        Returns:
            dict: A dictionary containing the query under the key 'query' and additional, optional settings.

        Example:
            >>> parser = InputParser()
            >>> parser("What's the weather like?")
            {'query': "What's the weather like?"}
        """
        query = user_query

        # parse docid-numbers
        docs = []
        system = {}
        pattern = r'\\mu2e-docdb-(\d+)'
        match = re.search(pattern, query)
        if match:
            docs.append({"type":"mu2e-docdb", "id":match.group(1), "mode":"user"})
        pattern = r'\\gm2-docdb-(\d+)'
        match = re.search(pattern, query)
        if match:
            docs.append({"type":"gm2-docdb", "id":match.group(1), "mode":"user"})
            #query = re.sub(pattern, '', query).strip()

        # move a user tag to the system prompts (from slack for example)
        #pattern = r'<user[^>]*>'
        #match = re.search(pattern, query)
        #if match:
        #    system['user'] = match.group(0)
        #    query = re.sub(pattern, '', query).strip()
        #

        settings = {}
        for key in ["model", "temperature"]:
            pattern = r'\\'+key+r'=(.*?)(?:\s|$)'
            match = re.search(pattern, query)
            if match:
                settings[key] = match.group(1)
                query = re.sub(pattern, '', query).strip()
        
        settings["rag"] = False # disable RAG by default and follow up questions except it is enabled by the user
        for key in ["print-settings","rag"]:
            pattern = r'\\'+key+r''
            match = re.search(pattern, query)
            if match:
                settings[key] = True
                query = re.sub(pattern, '', query).strip()
        #print("DEBUG settings", settings)

        # custom system prompt
        pattern = r'\\system="(.*?)"'
        match = re.search(pattern, query)
        if match:
            system["custom"] = match.group(1)
            query = re.sub(pattern, '', query).strip()
                
        return {"query": query, "docs": docs, "system": system, "settings":settings}

class Retriever():
    #def __init__(self, vectorstore):
    #    self.vectorstore = vectorstore
    #    self.label = "documents"
    def __init__(self):
        self.rag_max = 3
        self.rag_score = 0.35
        
    def __call__(self, input):
        # check if docs are requested
        out = input
        if "docs" in input:
            for doc in input["docs"]:
                if (doc["type"] == "mu2e-docdb") & (doc["mode"] == "user"):
                    doc_ = tools.load(f"mu2e-docdb-{doc['id']}")
                    prompt_string = f"<document date='{doc_['revised_content']}'\
                                               title='{doc_['title']}'>"
                    for d in doc_['files']:
                        prompt_string += f"<file filename='{d['filename']}' name='{d['filename']}'>\
                                          {d['text']}</file>"
                    prompt_string += "</document>"
                    out["query"]  = out["query"].replace(f"\mu2e-docdb-{doc['id']}", prompt_string)
            #if "prompt" not in out:
            #    out["prompt"] = ""
            #out["prompt"] = out["prompt"] + prompt_string

        # RAG
        if "settings" in out:
            if "rag" in out["settings"]:
                if out["settings"]["rag"]:
                    rag_string = "Use the inforamtion from the following documents in your answer if it fits the topic. Plase cite the used inforamtion with the provided 'docid' (format: mu2e-docdb-XXXXX) and page numbers whenever possible inline."
                    rag_string += "<documents>"
                    rag_sim, rag_docs = rag.find(out["query"])
                    print("DEBUG found ", len(rag_docs), " documents. The largest score is ", rag_sim[0])
                    for j, docid in enumerate(rag_docs):
                        if (j >= self.rag_max) or (rag_sim[j] < self.rag_score):
                            break
                        doc_ = tools.load(docid)
                        doc_type, doc_id = docid.rsplit('-', 1)
                        out["docs"].append({"type":doc_type, "id":doc_id, "mode":"rag"})
                        rag_string += f"<document date='{doc_['revised_content']}'\
                                                  title='{doc_['title']}'\
                                                  docid='{docid}'>"
                        for d in doc_['files']:
                            rag_string += f"<file filename='{d['filename']}' name='{d['filename']}'>\
                                              {d['text']}</file>"
                        rag_string += "</document>"
                    rag_string += "</documents>"
                    out["system"]["rag"] = rag_string
        return out


class LLM(ABC): # virtual LLM base class
    def __init__(self, model):
        self.system_pre = ""
        self.system_post = ""
        self.setModel(model)
        self.temperature = 0.7

    def setModel(self,model):
        self.model = self.models[model]

    def __call__(self, input):
        output = input
        if "messages" not in input:
            output["messages"] = []
        output["messages"].append({"role": "user", "content": output["query"]}) # append the latest question
 
        if "llm" not in output:
            output["llm"] = []
        output["llm"].append(self.send(output))
        return(self.process(output))
    
    @abstractmethod
    def process(self, output):
        pass

    @abstractmethod
    def send(self, input):
        pass

    def system(self, input):
        system = self.system_pre
        #TODO, add document specific
        if "system" in input:
            for key in input["system"]:
                system += input["system"][key]+"\n"
        system += self.system_post
        return system
        
class LLMArgo(LLM):
    def __init__(self, model="argo-4o"):
        self.url = "https://apps-dev.inside.anl.gov/argoapi/api/v1/resource/chat/"
        self.headers = {"Content-Type": "application/json"}
        self.user = "scorrodi"
        self.models = {"argo-4o":"gpt4o",
                       "argo-o1":"gpto1preview"}
        self.temperature = 0.1 
        self.top_p = 0.9
        self.max_tokens = 1000
        super().__init__(model)
    

    def send(self, output):
        data = {
            "user": self.user,
            "model": self.model,
            "system": output["system"] ,
            "messages":output["messages"],
            "stop": [],
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
            "max_completion_tokens": self.max_tokens
        }
        response = requests.post(self.url, 
                                 data=json.dumps(data), 
                                 headers=self.headers)
        return response.json()['response']   
 
    def process(self, output):
        last_message = output['llm'][ -1]
        output["answer"] = last_message
        output["messages"].append({"role": "assistant", "content": last_message})
        return output

class LLMopenAI(LLM):
    def __init__(self, model="4o-mini"):
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OpenAI API key not found. Please set OPENAI_API_KEY environment variable")
        self.client = OpenAI(api_key=api_key)
        self.models = {"4o-mini":"gpt-4o-mini",
                       "4o":"chatgpt-4o-latest",
                       "o1-mini":"o1-mini",
                       "o1-preview":"o1-preview"}
        super().__init__(model)
        
    def send(self, output):
        return self.client.chat.completions.create(
            model=self.model,
            #system=self.system(output),
            messages=[{"role":"system", "content":self.system(output)}] 
                     + output["messages"],
            stream=False,
            temperature=self.temperature)

    def process(self, output):
        last_message = output['llm'][ -1].choices
        if isinstance(last_message, list):
            last_message = last_message[0]  # Take the first message if it's a list
        else:
            last_message = last_message

        output["answer"] = last_message.message.content
        output["messages"].append({"role": "assistant", "content": last_message.message.content})
        return output
        

class LLMAntropic(LLM): #anthropic
    def __init__(self, model="sonnet"):
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("Anthropic API key not found. Please set ANTHROPIC_API_KEY environment variable")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.models = {"haiku":"claude-3-haiku-20240307",
                       "sonnet":"claude-3-5-sonnet-20240620",
                       "opus":"claude-3-opus-20240229"}
        super().__init__(model)
        self.max_tokens = 1000
        self.temperature = 0.7
        self.tools = None


    def send(self, output):
        if self.tools:
            return (
            self.client.beta.tools.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                tools=self.tools,
                temperature=self.temperature,
                system=self.system(output),
                stream=False,
                messages=output["messages"])
            )
        else:
            print("DEBUG", self.system(output))
            return (
            self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=self.system(output),
                stream=False,
                messages=output["messages"])
            )
            
    def process(self, output):
        #print(output)
        last_message = output['llm'][-1]
        if isinstance(last_message, list):
            last_message = last_message[0]  # Take the first message if it's a list
        else:
            last_message = last_message

        #print(last_message)
        #print("NUMBER OF CONTENT:", len(last_message.content))
        if last_message.content[0].type == "text":
            answer = ""
            for k in last_message.content:
                answer += k.text
            output["answer"] = answer
            output["messages"].append({"role": "assistant", "content": answer})
            #print(output)
            #print("ANSWER")
            #print(answer)
            return output

        elif last_message.content[0].type == "tool_use":
            tool_name  = last_message.content[0].name
            tool_input = last_message.content[0].input
            tool_id    = last_message.content[0].id
            print(tool_name, tool_input)
            #TODO, actual tool use!
            tool_result = "42"

            output["messages"].append({"role": "assistant", "content": last_message.content})
            output["messages"].append({"role": "user", "content": [
                                       {
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": str(tool_result),
                }]
                                      })
            #print("TOOL USE RESPONSE")
            #print(output["messages"])
            output["llm"].append(self.send(output))
            #self.send(output)
            return self.process(output)
        else:
            raise NotImplementedError

class OutputParser():
    def __init__(self):
        self.usedDocuments = True

    def __call__(self, out):
        out_str = out["answer"]
        if self.usedDocuments:
            if "docs" in out:
                if len(out["docs"]) > 0:
                    out_str += "\n *Related Documents*:"
            for doc in out["docs"]:
                print(doc)
                out_str += f"\n* {doc['type']}-{str(doc['id'])}"
                if doc["type"] == "mu2e-docdb":
                    out_str += ": https://mu2e-docdb.fnal.gov/cgi-bin/sso/ShowDocument?docid="+str(doc['id'])+""
        return out_str
        
        

class chat():
    def __init__(self, api="antropic"):
        self.parser = InputParser()
        self.retriever = Retriever()
        if api == "antropic":
            self.llm = LLMAntropic()
        elif api == "openAI":
            self.llm = LLMopenAI()
        self.outparser = OutputParser()
        self.data = None

    def __call__(self, user_query):
        print("TEST", user_query)
        if not self.data:
            self.data = self.parser(user_query)
        else:
            self.data = self.data | self.parser(user_query)
        self.updateSettings()
        self.data = self.retriever(self.data)
        self.data = self.llm(self.data)
        print(self.data["answer"])
        out_str = self.outparser(self.data)
        if "settings" in self.data:
            if "print-settings" in self.data["settings"]:
                out_str += "<settings "
                out_str += "model=\""+self.llm.model+"\" "
                out_str += "temperature=%.1f" % self.llm.temperature
                out_str += ">"
        return out_str

    def updateSettings(self):
        if "settings" in self.data:
            settings = self.data["settings"]
            if "model" in settings:
                new_model = settings["model"]
                print(new_model)
                if new_model in ["sonnet","opus","haiku"]: # Antropic
                    if not isinstance(self.llm, LLMAntropic):
                        self.llm = LLMAntropic()
                elif new_model in ["4o-mini","1o-mini","4o","o1-preview"]: # OpenAI
                    print("DEBUG")
                    if not isinstance(self.llm, LLMopenAI):
                        self.llm = LLMopenAI()
                elif new_model in ["argo-4o","argo-o1"]: # Argo
                    if not isinstance(self.llm, LLMArgo):
                        self.llm = LLMArgo()
                self.llm.setModel(new_model)
                print("DEBUG model:", self.llm.model)
            if "temperature" in settings:
                self.llm.temperature = float(settings["temperature"])
                print("DEBUG model:", self.llm.temperature)
