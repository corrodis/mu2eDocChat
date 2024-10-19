from abc import ABC, abstractmethod
import re
from mu2e import tools
import mu2e
import anthropic
from openai import OpenAI
from abc import ABC, abstractmethod

# input parser
class InputParser():
    """
    Parses direct user input for the use in the mu2e ML/AI agent.
    This parser allows to encode settings in the user string that we might want to remove from the actual user query that is processed.
    """
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
            docs.append({"type":"mu2e-docdb", "id":match.group(1)})
        pattern = r'\\gm2-docdb-(\d+)'
        match = re.search(pattern, query)
        if match:
            docs.append({"type":"gm2-docdb", "id":match.group(1)})
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
        for key in ["print-settings"]:
            pattern = r'\\'+key+r''
            match = re.search(pattern, query)
            if match:
                settings[key] = True
                query = re.sub(pattern, '', query).strip()
        print("DEBUG settings", settings)
                
        return {"query": query, "docs": docs, "system": system, "settings":settings}

class Retriever():
    #def __init__(self, vectorstore):
    #    self.vectorstore = vectorstore
    #    self.label = "documents"
        
    def __call__(self, input):
        # check if docs are requested
        out = input
        if "docs" in input:
            for doc in input["docs"]:
                if doc['type'] == "mu2e-docdb":
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
        

class LLMopenAI(LLM):
    import mu2e
    def __init__(self, model="4o-mini"):
        self.client = OpenAI(api_key=mu2e.api_keys['openAI'])
        self.models = {"4o-mini":"gpt-4o-mini",
                       "4o":"chatgpt-4o-latest",
                       "1o-mini":"o1-mini",
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
    import mu2e
    def __init__(self, model="haiku"):
        self.client = anthropic.Anthropic(api_key=mu2e.api_keys['antropic'])
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

class chat():
    def __init__(self, api="antropic"):
        self.parser = InputParser()
        self.retriever = Retriever()
        if api == "antropic":
            self.llm = LLMAntropic()
        elif api == "openAI":
            self.llm = LLMopenAI()
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
        out_str = self.data["answer"]
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
                if new_model in ["sonnet","opus","haiku"]: # Antropic
                    if not isinstance(self.llm, LLMAntropic):
                        self.llm = LLMAntropic()
                elif new_model in ["o4-mini","1o-mini","4o","o1-preview"]: # OpenAI
                    if not isinstance(self.llm, LLMopenAI):
                        self.llm = LLMopenAI()
                self.llm.setModel(new_model)
                print("DEBUG model:", self.llm.model)
            if "temperature" in settings:
                self.llm.temperature = float(settings["temperature"])
                print("DEBUG model:", self.llm.temperature)
