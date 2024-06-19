Work in progress for a LLM driven chat bot accessing the public mu2e wiki.

Work in progress list of required python packages

Before the example can be used, an embeding for the wiki data needs to be generated. That is done with
```
python getWiki.py
```
This will generate a "database" with the wikidata and the corresponding embeddings in "data/" folder.

Ones that file is present, questions about the mu2e wiki can be asked by
```
import mu2e;
mu2e.ask("What is mu2e?").content
```
