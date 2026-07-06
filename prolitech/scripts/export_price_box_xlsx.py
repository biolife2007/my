import ftplib
import os
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from export_open_prices_csv import load_env, query_mysql


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "exports" / "price-box.xlsx"
ID_VNID = ROOT / "tmp" / "id-vnid.xlsx"
REMOTE_PATH = "/cli/box/price-box.xlsx"
REMOTE_ID_VNID = "/cli/box/id-vnid.xlsx"

SQL = """
SELECT
  p.price,
  TRIM(p.sku) AS sku
FROM {prefix}product p
WHERE p.status = 1
  AND (p.date_available = '0000-00-00' OR p.date_available <= CURDATE())
  AND EXISTS (
    SELECT 1
    FROM {prefix}product_to_store p2s
    WHERE p2s.product_id = p.product_id
  )
ORDER BY p.product_id
"""


def column_name(index):
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def cell_xml(row_number, column_index, value, numeric=False):
    ref = f"{column_name(column_index)}{row_number}"
    if numeric:
        return f'<c r="{ref}"><v>{escape(str(value))}</v></c>'
    return f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'


def sheet_xml(rows):
    out = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
        '<dimension ref="A1:C{}"/>'.format(max(1, len(rows) + 1)),
        '<sheetViews><sheetView workbookViewId="0"/></sheetViews>',
        '<sheetFormatPr defaultRowHeight="15"/>',
        '<cols><col min="1" max="1" width="14" customWidth="1"/>'
        '<col min="2" max="2" width="12" customWidth="1"/>'
        '<col min="3" max="3" width="24" customWidth="1"/></cols>',
        '<sheetData>',
    ]
    headers = ["Ціна", "id-box", "sku"]
    out.append('<row r="1">' + "".join(cell_xml(1, i, h) for i, h in enumerate(headers, 1)) + "</row>")
    for row_number, row in enumerate(rows, 2):
        price, product_id, sku = row
        cells = [
            cell_xml(row_number, 1, price, numeric=True),
            cell_xml(row_number, 2, product_id, numeric=True),
            cell_xml(row_number, 3, sku or ""),
        ]
        out.append(f'<row r="{row_number}">' + "".join(cells) + "</row>")
    out.extend(["</sheetData>", "</worksheet>"])
    return "".join(out)


def write_xlsx(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as xlsx:
        xlsx.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>""")
        xlsx.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""")
        xlsx.writestr("xl/workbook.xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="price-box" sheetId="1" r:id="rId1"/></sheets>
</workbook>""")
        xlsx.writestr("xl/_rels/workbook.xml.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>""")
        xlsx.writestr("xl/styles.xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>
<fills count="1"><fill><patternFill patternType="none"/></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>
</styleSheet>""")
        xlsx.writestr("xl/worksheets/sheet1.xml", sheet_xml(rows))


def text_value(cell, shared_strings):
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(cell.itertext())
    value = cell.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
    if value is None:
        return ""
    text = value.text or ""
    if cell_type == "s":
        return shared_strings[int(text)]
    return text


def read_xlsx_rows(path):
    with zipfile.ZipFile(path) as xlsx:
        shared_strings = []
        if "xl/sharedStrings.xml" in xlsx.namelist():
            root = ET.fromstring(xlsx.read("xl/sharedStrings.xml"))
            for item in root.findall("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si"):
                shared_strings.append("".join(item.itertext()))

        sheet = ET.fromstring(xlsx.read("xl/worksheets/sheet1.xml"))
        rows = []
        for row in sheet.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row"):
            values = []
            for cell in row.findall("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"):
                values.append(text_value(cell, shared_strings))
            rows.append(values)
        return rows


def normalize_key(value):
    text = str(value or "").strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text


def read_id_map(path):
    rows = read_xlsx_rows(path)
    if not rows:
        return {}
    headers = [str(value or "").strip() for value in rows[0]]
    try:
        product_id_index = headers.index("id Продукта")
        external_id_index = headers.index("зовнішній id")
    except ValueError as exc:
        raise RuntimeError(f"Missing expected column in {path}: {exc}") from exc

    id_map = {}
    for row in rows[1:]:
        external_id = normalize_key(row[external_id_index] if external_id_index < len(row) else "")
        product_id = normalize_key(row[product_id_index] if product_id_index < len(row) else "")
        if external_id and product_id:
            id_map[external_id] = product_id
    return id_map


def ensure_dir(ftp, path):
    current = ftp.pwd()
    try:
        ftp.cwd("/")
        for part in path.strip("/").split("/"):
            if not part:
                continue
            try:
                ftp.cwd(part)
            except ftplib.error_perm:
                ftp.mkd(part)
                ftp.cwd(part)
    finally:
        ftp.cwd(current)


def connect_ftp(env):
    ftp = ftplib.FTP()
    ftp.connect(env["FTP_HOST"], int(env.get("FTP_PORT", "21")), timeout=30)
    ftp.login(env["FTP_USERNAME"], env["FTP_PASSWORD"])
    ftp.set_pasv(True)
    return ftp


def download(ftp, remote_path, local_path):
    local_path.parent.mkdir(parents=True, exist_ok=True)
    remote_dir = os.path.dirname(remote_path)
    remote_name = os.path.basename(remote_path)
    current = ftp.pwd()
    try:
        ftp.cwd(remote_dir)
        with local_path.open("wb") as f:
            ftp.retrbinary(f"RETR {remote_name}", f.write)
    finally:
        ftp.cwd(current)


def upload(path, env):
    ftp = connect_ftp(env)
    try:
        remote_dir = os.path.dirname(REMOTE_PATH)
        ensure_dir(ftp, remote_dir)
        ftp.cwd(remote_dir)
        with path.open("rb") as f:
            ftp.storbinary(f"STOR {os.path.basename(REMOTE_PATH)}", f)
    finally:
        ftp.quit()


def main():
    env = load_env(ROOT / ".env_open")
    ftp = connect_ftp(env)
    try:
        download(ftp, REMOTE_ID_VNID, ID_VNID)
    finally:
        ftp.quit()

    id_map = read_id_map(ID_VNID)
    db_rows = query_mysql(env, SQL)
    rows = []
    missing = 0
    for price, sku in db_rows:
        box_id = id_map.get(normalize_key(sku), "")
        if not box_id:
            missing += 1
        rows.append([price, box_id, sku])

    write_xlsx(OUTPUT, rows)
    upload(OUTPUT, env)
    print(f"ok file={OUTPUT} uploaded={REMOTE_PATH} count={len(rows)} matched={len(rows) - missing} missing={missing}")


if __name__ == "__main__":
    main()
