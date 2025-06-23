# Search Module

The `search.py` module provides a simplified interface for ChromaDB collection queries with filtering capabilities.

## Basic Usage

```python
import mu2e.search as search

# Semantic search (default collection)
results = search.search("muon conversion", n_results=10)

# Use custom collection
c = anl.get_collection()
results = search.search("detector design", collection=c, n_results=5)
```

## Date Filtering

```python
# Semantic search last 30 days
results = search.search_by_date("calibration", days_back=30)

# Custom date range
from datetime import datetime, timedelta
results = search.search(
    "beam studies",
    date_range={
        'start': datetime(2024, 1, 1),
        'end': datetime.now()
    }
)
```

## Full-Text Search

```python
# ChromaDB native keyword search
results = search.search_fulltext("stopping target", n_results=5)
```

## Raw ChromaDB Filters

```python
# Direct ChromaDB where clauses
results = search.search(
    "cosmic rays",
    filters={"docid": {"$gte": 50000}}
)
```

This module is a wrapper around ChromaDB's query interface, providing convenient search patterns while maintaining full ChromaDB functionality.