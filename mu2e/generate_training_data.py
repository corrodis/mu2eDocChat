import random
from itertools import islice
from datasets import Dataset
from mu2e import tools, chunking

def generate_chunked_triplets(num_docs=100):
    """
    Build a triplet dataset:
      - anchor, positive: adjacent chunks from the same document
      - negative: random chunk from a different document
    """
    #for random negatives
    seed = 42
    random.seed(seed)

    #chunk all docs
    all_docs = {}  # {doc_id: [chunk1, chunk2, ...]}
    
    for doc in islice(tools.iterate_documents(), num_docs):
        doc_id = doc.get("doc_id")
        if not doc_id:
            continue
        
        print(doc_id)

        doc_chunks = []
        for file in doc.get("files", []):
            text = (file.get("text") or "").strip()
            if not text:
                continue
                
            chunks = chunking.chunk_text_simple(text, chunk_overlap=200)
            if chunks:
                doc_chunks.extend(chunks)

        if len(doc_chunks) >= 2:
            all_docs[doc_id] = doc_chunks

    if len(all_docs) < 2:
        raise ValueError("Need at least two documents (each with >=2 chunks) to form valid triplets.")

    #Flat pool of all chunks
    flat_pool = [(current_id, c) for current_id, chunks in all_docs.items() for c in chunks]

    #Building triplets
    anchors, positives, negatives = [], [], []
    anchor_doc_ids, positive_doc_ids, negative_doc_ids = [], [], []

    for current_id, chunks in all_docs.items():
        other_doc_pool = [(other_id, c) for (other_id, c) in flat_pool if other_id != current_id]
        if not other_doc_pool:
            continue  # safety

        for i in range(len(chunks) - 1):
            anchor = chunks[i]
            positive = chunks[i + 1]
            negative_id, negative = random.choice(other_doc_pool)

            anchors.append(anchor)
            positives.append(positive)
            negatives.append(negative)
            anchor_doc_ids.append(current_id)
            positive_doc_ids.append(current_id)
            negative_doc_ids.append(negative_id)

    dataset = Dataset.from_dict({
        "anchor": anchors,
        "positive": positives,
        "negative": negatives,
        "anchor_doc_id": anchor_doc_ids,
        "positive_doc_id": positive_doc_ids,
        "negative_doc_id": negative_doc_ids,
    })
    
    dataset.save_to_disk('~/.mu2e/data/training_dataset.json')

if __name__ == "__main__":
    generate_chunked_triplets()
