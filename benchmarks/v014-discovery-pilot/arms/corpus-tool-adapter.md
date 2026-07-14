# Frozen-corpus tool adapter

Treat `corpus_search(query, limit)` and `corpus_read(doc_id)` as the only research tools. Query in
the likely language of the source documents; use multiple causal, bottleneck, substitute, customer,
supplier, regulation, financing, valuation, and falsifier queries instead of one company-name query.

- Search returns metadata and short snippets, not evidence-complete bodies.
- Read a document before citing it or using it as decisive evidence.
- A document can be read only after search returned its ID.
- Respect the dispatch query/read budgets. Stop cleanly when a budget is exhausted.
- Do not infer that search rank, document frequency, or corpus inclusion proves importance.
- Do not use direct filesystem, live web, memory, or post-as-of knowledge.
- Keep retrieval and investment judgment separate: finding a document is not finding an edge.
