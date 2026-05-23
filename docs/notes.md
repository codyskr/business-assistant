# Encrypted Notes

Notes are stored locally in:

```text
data/notes.jsonl
```

Each line contains one encrypted Fernet payload. The same local key from
`MEMORY_KEY_PATH` is used, so losing `data/memory.key` makes existing notes
unreadable.

Create a note:

```text
сделай заметку Иван предпочитает созвоны после 14:00
```

Find a note:

```text
найди заметку про Ивана
что я записывал про документы
/notes Иван
```

Search uses two layers:

```text
1. local lexical/fuzzy search with a few synonym expansions
2. optional local Ollama reranking for semantic relevance
```

The model is local through `OLLAMA_URL`; notes are not sent to external APIs by
this feature.

```env
NOTES_LLM_SEARCH_ENABLED=true
NOTES_LLM_SEARCH_LIMIT=30
```

Show recent notes:

```text
/notes
```
