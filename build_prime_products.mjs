import fs from 'node:fs/promises';
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const root = 'C:/Users/2ID (Alena)/Documents/GitHub/my';
const outputDir = `${root}/outputs/019ffa63-a94e-7573-9e8b-1d1d7892272c`;
const raw = JSON.parse(await fs.readFile(`${root}/prime_products_scraped.json`, 'utf8'));

function variant(sku) {
  const m = sku.match(/PRIME(\d+)-(\d+)/);
  return { volume: m?.[1] || '', clamp: m?.[2] || '' };
}

function descriptionUk(volume, clamp) {
  const lidVolume = { '25': '3,5', '40': '6', '60': '9' }[volume];
  const clamps = volume === '25' ? '4' : '6';
  const height = { '25-2': '510', '40-2': '600', '40-3': '580', '40-4': '560', '60-2': '690', '60-3': '670', '60-4': '650' }[`${volume}-${clamp}`];
  const diameter = { '25': '300', '40': '350', '60': '400' }[volume];
  const pack = { '25': '36 × 36 × 44 см, 6,1 кг', '40': '40 × 40 × 49 см, 8,2 кг', '60': '45 × 45 × 57 см, 10,8 кг' }[volume];
  return `<h2>Перегінний куб Magnum Prime ${volume} л/${clamp}&quot;</h2>
<p>Перегінний куб Magnum Prime з об’ємною кришкою аламбічної форми та тришаровим дном призначений для дистиляції фруктово-ягідної, цукрової та зернової сировини, а також може використовуватися у пивоварінні.</p>
<ol>
<li><strong>Унікальна об’ємна кришка аламбічної форми.</strong> Плавно спрямовує потік пари, створює додатковий простір для захисту від піноутворення, забезпечує природну повітряну дефлегмацію та має підвищену конструктивну жорсткість.</li>
<li><strong>Шкала літражу.</strong> На внутрішній стінці куба нанесена шкала, що дозволяє швидко контролювати кількість рідини під час наповнення та роботи без додаткової мірної тари.</li>
<li><strong>Цифровий термометр.</strong> Кришка оснащена електронним цифровим термометром, установленим через вварену нержавіючу ніпель-гільзу. Отвір гільзи 6 мм дозволяє за потреби встановити температурний щуп автоматики.</li>
<li><strong>Посилені затискачі.</strong> Забезпечують герметичність, зручність та безпеку. Прогумовані контактні поверхні захищають кришку від подряпин. Конструкція розрахована на допустимий робочий тиск.</li>
<li><strong>Кламповий патрубок під ТЕН.</strong> Нагрівач установлюється швидко та просто, без різьбових з’єднань. Клампове з’єднання забезпечує герметичність, зручний монтаж і мінімізує ризик підтікання.</li>
<li><strong>Тришарове дно.</strong> Алюмінієвий теплорозподільний шар забезпечує швидке та рівномірне нагрівання по всій площі куба, зменшує локальні перегріви й ризик пригорання, підвищує міцність і стійкість дна до деформації.</li>
<li><strong>Зливний кран.</strong> Кран із харчової нержавіючої сталі AISI 304 забезпечує зручний та швидкий злив, стійкий до корозії й легко миється.</li>
<li><strong>Прогумовані ручки.</strong> Забезпечують надійний хват, менше нагріваються та роблять перенесення куба комфортнішим і безпечнішим.</li>
<li><strong>Ребро жорсткості.</strong> Підсилює корпус і слугує опорою для фальшдна, що дає змогу працювати з густою фруктово-ягідною та зерновою сировиною, зерновими заторами й пивним суслом.</li>
</ol>
<p><strong>Додатковий бонус:</strong> подвійна різьба дозволяє встановити зливний кран із зовнішньої сторони куба та фільтр «базука» з внутрішньої сторони, переобладнавши куб у повноцінну пивоварню.</p>
<h3>Базова комплектація</h3>
<ul><li>перегінний куб об’ємом ${volume} л із клампом під ТЕН;</li><li>аламбічна кришка під кламп ${clamp}&quot;;</li><li>електронний цифровий термометр;</li><li>зливний кран із внутрішньою різьбою 1/2&quot;.</li></ul>
<h3>Додаткові опції</h3>
<ul><li>зміна об’єму ємності;</li><li>зміна розміру клампа на кришці;</li><li>ТЕН різної потужності з хомутом і прокладкою;</li><li>регулятор потужності з ПЗВ;</li><li>заглушка, хомут і прокладка для отвору під ТЕН;</li><li>система циркуляції та охолодження сусла;</li><li>фільтр «базука»;</li><li>фальшдно або сито для густої сировини;</li><li>неопреновий утеплювач;</li><li>оглядове вікно (діоптр) із підсвіткою.</li></ul>
<h3>Характеристики</h3>
<ul><li><strong>Об’єм:</strong> ${volume} л.</li><li><strong>Кламп на кришці:</strong> ${clamp}&quot;.</li><li><strong>Матеріал стінок і кришки:</strong> харчова нержавіюча сталь AISI 304.</li><li><strong>Тришарове дно:</strong> AISI 304 / алюмінієвий теплорозподільний шар / феромагнітна харчова нержавіюча сталь для роботи на індукційній плиті.</li><li><strong>Товщина:</strong> дно приблизно 5 мм, кришка приблизно 1,2 мм, стінка приблизно 1 мм.</li><li><strong>Об’єм кришки:</strong> приблизно ${lidVolume} л.</li><li><strong>Кількість затискачів:</strong> ${clamps} шт.</li>${height ? `<li><strong>Висота у зборі:</strong> приблизно ${height} мм.</li>` : ''}<li><strong>Діаметр дна:</strong> приблизно ${diameter} мм.</li><li><strong>Розмір і вага з упаковкою:</strong> ${pack}.</li></ul>`;
}

function descriptionRu(volume, clamp) {
  const lidVolume = { '25': '3,5', '40': '6', '60': '9' }[volume];
  const clamps = volume === '25' ? '4' : '6';
  const height = { '25-2': '510', '40-2': '600', '40-3': '580', '40-4': '560', '60-2': '690', '60-3': '670', '60-4': '650' }[`${volume}-${clamp}`];
  const diameter = { '25': '300', '40': '350', '60': '400' }[volume];
  const pack = { '25': '36 × 36 × 44 см, 6,1 кг', '40': '40 × 40 × 49 см, 8,2 кг', '60': '45 × 45 × 57 см, 10,8 кг' }[volume];
  return `<h2>Перегонный куб Magnum Prime ${volume} л/${clamp}&quot;</h2>
<p>Перегонный куб Magnum Prime с объемной крышкой аламбической формы и трехслойным дном предназначен для дистилляции фруктово-ягодного, сахарного и зернового сырья, а также может использоваться в пивоварении.</p>
<ol>
<li><strong>Уникальная объемная крышка аламбической формы.</strong> Плавно направляет поток пара, создает дополнительное пространство для защиты от пенообразования, обеспечивает естественную воздушную дефлегмацию и обладает повышенной конструктивной жесткостью.</li>
<li><strong>Шкала литража.</strong> На внутренней стенке куба нанесена шкала, позволяющая быстро контролировать количество жидкости при наполнении и работе без дополнительной мерной тары.</li>
<li><strong>Цифровой термометр.</strong> Крышка оснащена электронным цифровым термометром, установленным через вваренную нержавеющую ниппель-гильзу. Отверстие гильзы 6 мм позволяет при необходимости установить температурный щуп автоматики.</li>
<li><strong>Усиленные зажимы.</strong> Обеспечивают герметичность, удобство и безопасность. Прорезиненные контактные поверхности защищают крышку от царапин. Конструкция рассчитана на допустимое рабочее давление.</li>
<li><strong>Кламповый патрубок под ТЭН.</strong> Нагреватель устанавливается быстро и просто, без резьбовых соединений. Кламповое соединение обеспечивает герметичность, удобный монтаж и минимизирует риск протекания.</li>
<li><strong>Трехслойное дно.</strong> Алюминиевый теплораспределительный слой обеспечивает быстрый и равномерный нагрев по всей площади куба, уменьшает локальные перегревы и риск пригорания, повышает прочность и устойчивость дна к деформации.</li>
<li><strong>Сливной кран.</strong> Кран из пищевой нержавеющей стали AISI 304 обеспечивает удобный и быстрый слив, устойчив к коррозии и легко моется.</li>
<li><strong>Прорезиненные ручки.</strong> Обеспечивают надежный хват, меньше нагреваются и делают переноску куба более комфортной и безопасной.</li>
<li><strong>Ребро жесткости.</strong> Усиливает корпус и служит опорой для фальшдна, позволяя работать с густым фруктово-ягодным и зерновым сырьем, зерновыми заторами и пивным суслом.</li>
</ol>
<p><strong>Дополнительный бонус:</strong> двойная резьба позволяет установить сливной кран с внешней стороны куба и фильтр «базука» с внутренней стороны, переоборудовав куб в полноценную пивоварню.</p>
<h3>Базовая комплектация</h3>
<ul><li>перегонный куб объемом ${volume} л с клампом под ТЭН;</li><li>аламбическая крышка под кламп ${clamp}&quot;;</li><li>электронный цифровой термометр;</li><li>сливной кран с внутренней резьбой 1/2&quot;.</li></ul>
<h3>Дополнительные опции</h3>
<ul><li>изменение объема емкости;</li><li>изменение размера клампа на крышке;</li><li>ТЭН различной мощности с хомутом и прокладкой;</li><li>регулятор мощности с УЗО;</li><li>заглушка, хомут и прокладка для отверстия под ТЭН;</li><li>система циркуляции и охлаждения сусла;</li><li>фильтр «базука»;</li><li>фальшдно или сито для густого сырья;</li><li>неопреновый утеплитель;</li><li>смотровое окно (диоптр) с подсветкой.</li></ul>
<h3>Характеристики</h3>
<ul><li><strong>Объем:</strong> ${volume} л.</li><li><strong>Кламп на крышке:</strong> ${clamp}&quot;.</li><li><strong>Материал стенок и крышки:</strong> пищевая нержавеющая сталь AISI 304.</li><li><strong>Трехслойное дно:</strong> AISI 304 / алюминиевый теплораспределительный слой / ферромагнитная пищевая нержавеющая сталь для работы на индукционной плите.</li><li><strong>Толщина:</strong> дно около 5 мм, крышка около 1,2 мм, стенка около 1 мм.</li><li><strong>Объем крышки:</strong> около ${lidVolume} л.</li><li><strong>Количество зажимов:</strong> ${clamps} шт.</li>${height ? `<li><strong>Высота в сборе:</strong> около ${height} мм.</li>` : ''}<li><strong>Диаметр дна:</strong> около ${diameter} мм.</li><li><strong>Размер и вес с упаковкой:</strong> ${pack}.</li></ul>`;
}

const rows = raw.map((item) => {
  const { volume, clamp } = variant(item.sku);
  return [
    item.sku,
    `Перегінний куб Magnum Prime ${volume}л/${clamp}\" (аламбічна кришка, тришарове дно)`,
    `Перегонный куб Magnum Prime ${volume}л/${clamp}\" (аламбическая крышка, трехслойное дно)`,
    item.price,
    descriptionUk(volume, clamp),
    descriptionRu(volume, clamp),
    item.photos,
    item.availabilityUk,
  ];
});

const workbook = Workbook.create();
const sheet = workbook.worksheets.add('Товари');
sheet.showGridLines = false;
sheet.getRange('A1:H10').values = [[
  'SKU', 'Назва укр', 'Назва рос', 'Ціна', 'Опис укр', 'Опис рос',
  'Посилання на всі фото товару через кому', 'наявність'
], ...rows];

sheet.getRange('A1:H1').format = {
  fill: '#1F4E78',
  font: { bold: true, color: '#FFFFFF', size: 11 },
  horizontalAlignment: 'center',
  verticalAlignment: 'center',
  wrapText: true,
  borders: { preset: 'outside', style: 'medium', color: '#17365D' },
};
sheet.getRange('A2:H10').format = {
  font: { color: '#1F2937', size: 10 },
  verticalAlignment: 'top',
  wrapText: true,
  borders: { preset: 'inside', style: 'thin', color: '#D9E2F3' },
};
sheet.getRange('A2:A10').format.font = { bold: true, color: '#1F4E78' };
sheet.getRange('D2:D10').format = { numberFormat: '#,##0', horizontalAlignment: 'right', verticalAlignment: 'top' };
sheet.getRange('H2:H10').format = { fill: '#E2F0D9', font: { bold: true, color: '#375623' }, horizontalAlignment: 'center', verticalAlignment: 'top', wrapText: true };

sheet.getRange('A:A').format.columnWidth = 24;
sheet.getRange('B:C').format.columnWidth = 48;
sheet.getRange('D:D').format.columnWidth = 12;
sheet.getRange('E:F').format.columnWidth = 78;
sheet.getRange('G:G').format.columnWidth = 90;
sheet.getRange('H:H').format.columnWidth = 21;
sheet.getRange('1:1').format.rowHeight = 34;
sheet.getRange('2:10').format.rowHeight = 180;
sheet.freezePanes.freezeRows(1);

const table = sheet.tables.add('A1:H10', true, 'PrimeProducts');
table.style = 'TableStyleMedium2';
table.showFilterButton = true;

await fs.mkdir(outputDir, { recursive: true });
const preview = await workbook.render({ sheetName: 'Товари', range: 'A1:H4', scale: 1, format: 'png' });
await fs.writeFile(`${outputDir}/prime_products_preview.png`, new Uint8Array(await preview.arrayBuffer()));
const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(`${outputDir}/magnum_prime_products_html_names_fixed.xlsx`);

const check = await workbook.inspect({ kind: 'table', range: 'Товари!A1:H10', include: 'values,formulas', tableMaxRows: 10, tableMaxCols: 8, maxChars: 5000 });
const errors = await workbook.inspect({ kind: 'match', searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A', options: { useRegex: true, maxResults: 100 }, summary: 'final formula error scan' });
console.log(check.ndjson);
console.log(errors.ndjson);
