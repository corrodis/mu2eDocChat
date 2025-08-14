# Benchmarking and Evaluation

## Command Line Usage
### Generation
Default Prompt
- Use `mu2e-eval generate` to generate default question/answer dataset based on document keypoints. For each question, 4 possible answer selections are generated.
- `mu2e-eval generate --filename FILENAME` specifies filename for json containing qa pairs. Default name is "benchmark_questions.json". The file will be saved to the data directory accessible via `~/.mu2e/data`.
- `mu2e-eval generate --num NUM` determines number of documents to use for dataset generation. By default, `generate` will use the max number of documents contained in the database.

chATLAS Prompt
- Use `mu2e-eval generate-chATLAS` to generate benchmarking dataset based on the chATLAS-benchmark package inspired prompt. This dataset will contain 3 qa pairs for each document with different difficulty levels.
- `mu2e-eval generate --filename FILENAME` will specify filename for json. Default is "chATLAS_questions.json" and will be saved to data directory.


### Testing
- Use `mu2e-eval test-retrieval` to test qa dataset. This tool will produce a score for each question based on how high the key document was returned in the retrieval. A score of 0 indicates the document was not returned as part of the first 100 results. These scores will be saved as "benchmark_scores.json" in the data directory. 
- To test whether the model correctly answers a question with a retrieval score of 0 based on the provided selections use `mu2e-eval test-retrieval --test-zeros`. 
- To specify embedding collection use `mu2e-eval test-retrieval --collection COLLECTION`. 



