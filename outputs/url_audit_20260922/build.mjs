import fs from 'node:fs/promises';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const dir='outputs/url_audit_20260922';
const d=JSON.parse(await fs.readFile(`${dir}/data.json`,'utf8'));
const w=await SpreadsheetFile.importXlsx(await FileBlob.load(d.source));
const s=w.worksheets.getItemAt(0);
const headers=['URL','SKU','Назва товару в Пролітех','Результат перевірки','HTTP','Кінцевий URL','Перевірено (UTC)','Назва на сайті постачальника'];
const rows=d.rows.map(([url,sku])=>{const c=d.checks[url];return [url,sku,d.names[String(sku).trim()]?.[0][1]||'SKU не знайдено в Пролітех',c.status,c.http,c.final_url,c.checked.slice(0,19).replace('T',' '),c.h1];});
s.getRange(`A1:H${rows.length+1}`).values=[headers,...rows];
const report=w.worksheets.add('Зниклі сторінки');
report.getRange('A2').values=[['Неіснуючі URL — 22.09.2026']];
report.getRange('A3').values=[['59 сторінок: HTTP 404 підтверджено двома запитами для кожного URL.']];
report.getRange('A4').values=[['22 SKU зі зниклими URL відсутні в базі Пролітех. Назви не підставлялися за припущенням.']];
const gone=rows.filter(r=>r[4]===404);
const out=gone.map(r=>[r[1],r[2],r[0],r[4],r[5],r[6]]);
report.getRange(`A6:F${6+out.length}`).values=[['SKU','Назва товару в Пролітех','URL, що зник','HTTP','Кінцевий URL','Перевірено (UTC)'],...out];
for(const [sheet,head,last,widths] of [[s,1,325,[66,23,65,24,9,66,23,65]],[report,6,65,[23,65,66,9,66,23]]]){
 const end=String.fromCharCode(64+widths.length);
 sheet.showGridLines=false;
 sheet.getRange(`A${head}:${end}${last}`).format.font={name:'Arial',size:10};
 sheet.getRange(`A${head}:${end}${last}`).format.verticalAlignment='center';
 sheet.getRange(`A${head}:${end}${last}`).format.wrapText=true;
 sheet.getRange(`A${head}:${end}${last}`).format.rowHeight=44;
 sheet.getRange(`A${head}:${end}${head}`).format={fill:'#253E54',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:32};
 widths.forEach((width,i)=>sheet.getRange(`${String.fromCharCode(65+i)}1:${String.fromCharCode(65+i)}${last}`).format.columnWidth=width);
 sheet.freezePanes.freezeRows(head);
 sheet.tables.add(`A${head}:${end}${last}`,true, sheet===s?'AllUrls':'MissingUrls');
}
report.getRange('A2').format.font={name:'Arial',size:14,bold:true};
report.getRange('A2:A4').format.wrapText=false;
report.getRange('A2:A4').format.rowHeight=24;
s.getRange('B2:B325').setNumberFormat('@');
report.getRange('A7:A65').setNumberFormat('@');
w.recalculate();
console.log((await w.inspect({kind:'table',range:'\'Зниклі сторінки\'!A6:D9',include:'values',tableMaxRows:4,tableMaxCols:4,maxChars:2500})).ndjson);
const file=await SpreadsheetFile.exportXlsx(w);await file.save(`${dir}/19_звіт_URL.xlsx`);
for(const [sheet,range,name] of [[s,'A1:E7','all'],[report,'A2:D11','missing']]){
 const p=await w.render({sheetName:sheet.name,range,scale:1});await fs.writeFile(`${dir}/${name}.png`,new Uint8Array(await p.arrayBuffer()));
}
