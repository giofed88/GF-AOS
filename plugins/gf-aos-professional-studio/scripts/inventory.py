#!/usr/bin/env python3
"""Read-only inventory of a client folder; writes reports only to a separate workspace."""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

CATEGORIES = {
    'verbali': ('verbale', 'verbali'),
    'bilanci': ('bilancio', 'bilanci', 'situazione_contabile'),
    'fiscale': ('iva', 'dichiarazione', 'f24', 'ires', 'irpef'),
    'lavoro': ('cedolino', 'inps', 'inail', 'uniemens'),
    'contratti': ('contratto', 'lettera_incarico'),
    'magazzino': ('rimanenze', 'inventario', 'magazzino'),
}

def classify(name):
    lowered = name.lower().replace(' ', '_').replace('-', '_')
    return next((category for category, terms in CATEGORIES.items() if any(term in lowered for term in terms)), 'da_verificare')

def inventory(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_dir():
        raise ValueError('La cartella sorgente non esiste')
    if output == source or source in output.parents:
        raise ValueError('Il report deve essere fuori dalla cartella sorgente')
    if output.exists() and output.is_symlink():
        raise ValueError('Output simbolico non consentito')
    rows, problems = [], []
    for root, dirs, files in os.walk(source, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not (Path(root)/d).is_symlink())
        for name in sorted(files):
            path = Path(root)/name
            try:
                if path.is_symlink():
                    problems.append({'path': str(path.relative_to(source)), 'issue': 'link simbolico ignorato'})
                    continue
                stat = path.stat()
                rows.append({'path': str(path.relative_to(source)), 'bytes': stat.st_size,
                             'modified_utc': datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                             'category_proposed': classify(name)})
            except OSError as exc:
                problems.append({'path': str(path.relative_to(source)), 'issue': str(exc)})
    result = {'source': str(source), 'created_utc': datetime.now(timezone.utc).isoformat(),
              'count': len(rows), 'files': rows, 'problems': problems,
              'note': 'Categorie proposte; nessun contenuto letto o file sorgente modificato.'}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    markdown = output.with_suffix('.md')
    markdown.write_text('# Inventario fascicolo 006A\n\n' + f'File: {len(rows)}. Problemi: {len(problems)}.\n\n' +
                        '| Percorso | Categoria proposta | Byte |\n| --- | --- | ---: |\n' +
                        ''.join(f"| {r['path'].replace('|', '¦')} | {r['category_proposed']} | {r['bytes']} |\n" for r in rows) +
                        '\nLe categorie richiedono conferma professionale.\n', encoding='utf-8')
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(f"Inventariati {inventory(args.source, args.output)['count']} file")
