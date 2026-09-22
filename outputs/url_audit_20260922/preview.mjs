import fs from 'node:fs/promises';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const w=await SpreadsheetFile.importXlsx(await FileBlob.load('C:/Work/ПОСТАЧАЛЬНИКИ/Магнум Стіл/18-09-2026/19.xlsx'));
console.log((await w.inspect({kind:'sheet',include:'id,name'})).ndjson);
const p=await w.render({sheetName:w.worksheets.getItemAt(0).name,range:'A1:B6',scale:1});
await fs.writeFile('outputs/url_audit_20260922/before.png',new Uint8Array(await p.arrayBuffer()));
