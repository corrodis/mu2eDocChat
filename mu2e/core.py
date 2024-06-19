import mu2e
import json

## get the API key(s)
with open('config.json') as config_file:
   config = json.load(config_file)
api_key=config['antropic']


def getSystemPrompt(q):

        website_content_string = ""
        for doc in mu2e.findAndGet(q):
            website_content_string += "<page url=\""+doc['url']+"\" title=\""+doc['heading']+"\">\n"+doc['text']+"</page>\n"

        SYSTEM_PROMPT = f"""You are a mu2e DocBot, a helpful assistant that is an expert at helping users with the mu2e related questions.

        Here is some realted Mu2e documentation
	<documentation>
	{website_content_string}
	</documentation>

        When a user asks a question, peform the following tasks:
        1. Find sections in the documentation that are the most relevant to answering the question. You may need to use multiple pages.
        2. Keep track of the url of the pages.
        3. Based on the document, answer the question. Directly quote the documentation when possible, including examples.
        4.  When answering the question provide references to the corresponding urls in square brackets from step 2.
        Format the answer as plain text, formatted as Markdown[1]
	"""
        return SYSTEM_PROMPT


def ask(q):
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    message = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=1000,
        temperature=0.7,
        system=getSystemPrompt(q),
        #stream=True,
        messages=[
            {"role": "user", "content": q},
        ])
    
    return(message)



