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

Show recent notes:

```text
/notes
```

Laptop wake flow:

```text
джарвис
...pause...
сделай заметку Иван предпочитает созвоны после 14:00
```
