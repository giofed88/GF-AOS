# Eval — Integrita fonti

- Lo snapshot conserva hash di percorsi e contenuti, non nomi o testo.
- La verifica invariata restituisce `PASS`.
- Aggiunte, rimozioni o modifiche restituiscono `BLOCKED` senza esporre il nome file.
- Symlink e radice coincidente con il workspace vengono rifiutati.
