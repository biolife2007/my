#!/usr/bin/env python3
"""Convert the adjacent UTF-8, semicolon-delimited id-vnid.csv to XLSX.

Deploy to cli/box and run with Python 3. No third-party packages required.
All IDs remain text. The CSV is never modified.
"""
import csv
import io
import os
import re
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape


NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
DOCREL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
BAD_XML = re.compile('[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]')


def read_rows(source):
    with source.open('rb') as handle:
        before = os.fstat(handle.fileno())
        raw = handle.read()
        after = os.fstat(handle.fileno())
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('CSV changed while being read; retry after upload finishes')
    text = raw.decode('utf-8-sig')
    rows = list(csv.reader(io.StringIO(text, newline=''), delimiter=';', strict=True))
    if not rows or rows[0] != ['id Продукта', 'зовнішній id']:
        raise ValueError('CSV is empty or headers do not match the expected two columns')
    if len(rows) > 1048576:
        raise ValueError('Too many rows for Excel')
    for number, row in enumerate(rows, 1):
        if len(row) > 2:
            raise ValueError('More than two columns at row %d' % number)
        row.extend([''] * (2 - len(row)))
        for value in row:
            if BAD_XML.search(value) or len(value.encode('utf-16-le')) // 2 > 32767:
                raise ValueError('Invalid Excel text at row %d' % number)
    return rows


def write_xlsx(rows, destination):
    sheet = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<worksheet xmlns="%s">' % NS,
             '<dimension ref="A1:B%d"/>' % len(rows),
             '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>',
             '<cols><col min="1" max="2" width="26" customWidth="1"/></cols><sheetData>']
    for number, row in enumerate(rows, 1):
        sheet.append('<row r="%d">' % number)
        for column, value in zip('AB', row):
            # Inline strings prevent Excel from interpreting IDs as dates or formulas.
            value = escape(value).replace('\r', '&#13;')
            sheet.append('<c r="%s%d" t="inlineStr"><is><t xml:space="preserve">%s</t></is></c>' % (column, number, value))
        sheet.append('</row>')
    sheet.append('</sheetData><autoFilter ref="A1:B%d"/></worksheet>' % len(rows))
    files = {
        '[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
        '_rels/.rels': '<Relationships xmlns="%s"><Relationship Id="rId1" Type="%s/officeDocument" Target="xl/workbook.xml"/></Relationships>' % (REL, DOCREL),
        'xl/workbook.xml': '<workbook xmlns="%s" xmlns:r="%s"><sheets><sheet name="id-vnid" sheetId="1" r:id="rId1"/></sheets></workbook>' % (NS, DOCREL),
        'xl/_rels/workbook.xml.rels': '<Relationships xmlns="%s"><Relationship Id="rId1" Type="%s/worksheet" Target="worksheets/sheet1.xml"/></Relationships>' % (REL, DOCREL),
        'xl/worksheets/sheet1.xml': ''.join(sheet),
    }
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=str(destination.parent), prefix='.id-vnid-', suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
        with zipfile.ZipFile(str(temporary), 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, content in files.items():
                archive.writestr(name, content.encode('utf-8'))
        os.chmod(str(temporary), 0o644)
        os.replace(str(temporary), str(destination))
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main():
    import fcntl  # Linux cron host; prevents overlapping runs.
    directory = Path(__file__).resolve().parent
    with (directory / '.id-vnid-convert.lock').open('a') as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('SKIP: another conversion is running', flush=True)
            return
        rows = read_rows(directory / 'id-vnid.csv')
        destination = directory / 'id-vnid.xlsx'
        write_xlsx(rows, destination)
        print('%s OK rows=%d file=%s' % (datetime.now(timezone.utc).isoformat(), len(rows) - 1, destination), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('%s ERROR: %s' % (datetime.now(timezone.utc).isoformat(), error), file=sys.stderr, flush=True)
        sys.exit(1)
