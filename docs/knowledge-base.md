# Encrypted Knowledge Base

Send a file to the Telegram bot to add it to the local knowledge base.

Supported formats:

```text
txt, md, csv, json, yaml, log, html, xml, pdf, docx
```

Storage:

```text
data/knowledge.jsonl
```

Each chunk is encrypted with the local Fernet key from `MEMORY_KEY_PATH`.

Search:

```text
/kb договор с Иваном
/knowledge регламент оплаты
найди в базе знаний про условия договора
покажи в документах про отчет
```

Settings:

```env
KNOWLEDGE_LLM_SEARCH_ENABLED=true
KNOWLEDGE_LLM_SEARCH_LIMIT=40
KNOWLEDGE_MAX_FILE_MB=20
KNOWLEDGE_CHUNK_CHARS=1400
KNOWLEDGE_CHUNK_OVERLAP=180
```

Search uses local lexical/fuzzy matching plus optional local Ollama reranking.
Knowledge chunks are not sent to external APIs by this feature.
