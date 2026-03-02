# Sample Documents

Place your PDF documents in this directory for ingestion into the demo.

## Guidelines

- **Supported formats**: PDF files (`.pdf`)
- **Recommended size**: Documents under 200 MB each
- **Content types**: Company policies, manuals, reports, technical documentation, etc.
- **Quantity**: Start with 5-10 documents for a quick demo; the pipeline handles hundreds

## What happens during ingestion

1. **Upload** (`02_upload_documents.py`): PDFs are uploaded to Azure Blob Storage
2. **Knowledge Source** (`03_create_knowledge.py`): The Blob Knowledge Source triggers automatic processing:
   - **Layout Analysis**: OCR + structure detection (paragraphs, headers, tables, figures)
   - **Markdown Conversion**: Structural elements → Markdown (tables as MD tables, headers preserved)
   - **Semantic Chunking**: Intelligent splitting with cross-page support; tables stay intact
   - **Vectorization**: Chunks are embedded using `text-embedding-3-large`
3. **Indexing**: Enriched chunks are stored in Azure AI Search with vector + text fields

## Sample documents

If you don't have documents ready, you can use publicly available PDFs such as:
- [NASA Earth at Night e-book](https://github.com/Azure-Samples/azure-search-sample-data/blob/main/nasa-e-book/earth_at_night_508.pdf)
- Any publicly available technical documentation or white papers
