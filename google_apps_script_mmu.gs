const SHEET_ID = '1iRx4N31fSFjg3RE77O4GFdeOHkIjEzWJ6efVvwUqBxs';
const SECRET = 'PASTE_YOUR_SECRET_HERE';

const HEADERS = [
  'Дата обновления',
  'Имя Telegram',
  'Фамилия Telegram',
  'Username',
  'Telegram ID',
  'Телефон Telegram',
  'Согласие',
  'Школа',
  'Класс',
  'Фамилия анкеты',
  'Имя анкеты',
  'Отчество',
  'Телефон ученика',
  'ЕГЭ',
  'Карьерная сфера',
  'Дата ДОД',
  'Время ДОД',
  'Статус ДОД',
  'Статус лида',
  'Следующий контакт',
  'Комментарий',
  'Источник'
];

const LEAD_STATUSES = [
  'Новая',
  'В работе',
  'Связались',
  'Не дозвонились',
  'Записан на ДОД',
  'Пришел на ДОД',
  'Поступление',
  'Не заинтересован',
  'Закрыта'
];

function getMainSheet_() {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  const sheet = ss.getSheets()[0];

  if (sheet.getName() !== 'Заявки') {
    sheet.setName('Заявки');
  }

  ensureHeaders_(sheet);
  return sheet;
}

function ensureHeaders_(sheet) {
  const current = sheet.getRange(1, 1, 1, HEADERS.length).getValues()[0];
  const needsHeaders = current.every(v => String(v || '') === '');

  if (needsHeaders) {
    sheet.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]);
  } else {
    // Добавляем недостающие новые столбцы, не удаляя существующие данные.
    sheet.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]);
  }
}

function findRowByTelegramId_(sheet, telegramId) {
  if (!telegramId || sheet.getLastRow() < 2) return -1;

  const values = sheet.getRange(2, 5, sheet.getLastRow() - 1, 1).getValues();
  const wanted = String(telegramId);

  for (let i = 0; i < values.length; i++) {
    if (String(values[i][0]) === wanted) return i + 2;
  }

  return -1;
}

function formatSheet_() {
  const sheet = getMainSheet_();

  const maxRows = Math.max(sheet.getMaxRows(), 2);
  const maxCols = HEADERS.length;

  // Шапка.
  const header = sheet.getRange(1, 1, 1, maxCols);
  header
    .setFontWeight('bold')
    .setFontColor('#FFFFFF')
    .setBackground('#0F766E')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle')
    .setWrap(true);
  header.setRowHeight(42);

  // Тело таблицы.
  const body = sheet.getRange(2, 1, maxRows - 1, maxCols);
  body
    .setVerticalAlignment('top')
    .setWrap(true)
    .setFontSize(10);

  // Удобные ширины.
  const widths = [
    150, 125, 125, 125, 110, 150, 90,
    180, 75, 135, 125, 135, 150, 200, 190,
    105, 85, 135, 145, 125, 280, 180
  ];

  widths.forEach((width, index) => {
    sheet.setColumnWidth(index + 1, width);
  });

  // Форматы дат и времени.
  sheet.getRange('A2:A').setNumberFormat('dd.MM.yyyy HH:mm');
  sheet.getRange('P2:P').setNumberFormat('dd.MM.yyyy');
  sheet.getRange('Q2:Q').setNumberFormat('HH:mm');
  sheet.getRange('T2:T').setNumberFormat('dd.MM.yyyy');

  // Фильтр.
  const filter = sheet.getFilter();
  if (filter) filter.remove();

  sheet.getRange(
    1,
    1,
    Math.max(sheet.getLastRow(), 2),
    maxCols
  ).createFilter();

  // Закрепление.
  sheet.setFrozenRows(1);
  sheet.setFrozenColumns(2);

  // Статусы — выпадающий список.
  const statusRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(LEAD_STATUSES, true)
    .setAllowInvalid(false)
    .build();

  sheet.getRange('S2:S').setDataValidation(statusRule);

  // Проставляем "Новая" только в пустых строках с Telegram ID.
  const lastRow = sheet.getLastRow();
  if (lastRow >= 2) {
    const ids = sheet.getRange(2, 5, lastRow - 1, 1).getValues();
    const statuses = sheet.getRange(2, 19, lastRow - 1, 1).getValues();

    let changed = false;

    for (let i = 0; i < ids.length; i++) {
      if (ids[i][0] && !statuses[i][0]) {
        statuses[i][0] = 'Новая';
        changed = true;
      }
    }

    if (changed) {
      sheet.getRange(2, 19, lastRow - 1, 1).setValues(statuses);
    }
  }

  // Цветовая индикация статусов лида.
  const rules = [
    SpreadsheetApp.newConditionalFormatRule()
      .whenTextEqualTo('Новая')
      .setBackground('#E0F2FE')
      .setRanges([sheet.getRange('S2:S')])
      .build(),

    SpreadsheetApp.newConditionalFormatRule()
      .whenTextEqualTo('В работе')
      .setBackground('#FEF3C7')
      .setRanges([sheet.getRange('S2:S')])
      .build(),

    SpreadsheetApp.newConditionalFormatRule()
      .whenTextEqualTo('Связались')
      .setBackground('#DCFCE7')
      .setRanges([sheet.getRange('S2:S')])
      .build(),

    SpreadsheetApp.newConditionalFormatRule()
      .whenTextEqualTo('Не дозвонились')
      .setBackground('#FDE68A')
      .setRanges([sheet.getRange('S2:S')])
      .build(),

    SpreadsheetApp.newConditionalFormatRule()
      .whenTextEqualTo('Записан на ДОД')
      .setBackground('#BBF7D0')
      .setRanges([sheet.getRange('S2:S')])
      .build(),

    SpreadsheetApp.newConditionalFormatRule()
      .whenTextEqualTo('Пришел на ДОД')
      .setBackground('#86EFAC')
      .setRanges([sheet.getRange('S2:S')])
      .build(),

    SpreadsheetApp.newConditionalFormatRule()
      .whenTextEqualTo('Не заинтересован')
      .setBackground('#F1F5F9')
      .setRanges([sheet.getRange('S2:S')])
      .build(),

    SpreadsheetApp.newConditionalFormatRule()
      .whenTextEqualTo('Закрыта')
      .setBackground('#E2E8F0')
      .setRanges([sheet.getRange('S2:S')])
      .build()
  ];

  sheet.setConditionalFormatRules(rules);

  // Комментарии и длинные поля читаются без ручного изменения ширины.
  sheet.getRange('N2:O').setWrap(true);
  sheet.getRange('U2:V').setWrap(true);

  // Подгоняем высоту уже существующих строк под содержимое.
  if (lastRow >= 2) {
    sheet.autoResizeRows(2, lastRow - 1);
  }

  sheet.setActiveSelection('A2');
}

function setupOpenDay_() {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  let sheet = ss.getSheetByName('ДОД');

  if (!sheet) {
    sheet = ss.insertSheet('ДОД');
  } else {
    sheet.clear();
    sheet.clearFormats();
  }

  sheet.getRange('A1:I1').setValues([[
    'Дата ДОД',
    'День',
    'Время',
    'Имя',
    'Фамилия',
    'Телефон',
    'Telegram',
    'Статус',
    'Комментарий'
  ]]);

  sheet.getRange('A1:I1')
    .setFontWeight('bold')
    .setFontColor('#FFFFFF')
    .setBackground('#0F766E')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle')
    .setWrap(true);
  sheet.setRowHeight(1, 42);

  // Автоматически показывает только людей, записанных на ДОД.
  sheet.getRange('A2').setFormula(
    '=IFERROR(QUERY(Заявки!A:U,"select P,Q,B,C,D,F,G,R,U where R matches \'Записан на ДОД|Пришел на ДОД\' order by P,Q",1),"")'
  );

  const widths = [110, 100, 80, 120, 120, 145, 120, 145, 240];
  widths.forEach((width, index) => sheet.setColumnWidth(index + 1, width));

  sheet.getRange('A2:I1000')
    .setVerticalAlignment('top')
    .setWrap(true)
    .setFontSize(10);

  sheet.getRange('A2:A').setNumberFormat('dd.MM.yyyy');
  sheet.getRange('C2:C').setNumberFormat('HH:mm');

  const filter = sheet.getFilter();
  if (filter) filter.remove();
  sheet.getRange('A1:I1000').createFilter();

  sheet.setFrozenRows(1);
  sheet.autoResizeRows(2, Math.max(sheet.getLastRow() - 1, 1));
  sheet.setActiveSelection('A2');
}

function setupStats_() {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  let sheet = ss.getSheetByName('Статистика');

  if (!sheet) {
    sheet = ss.insertSheet('Статистика');
  } else {
    sheet.clear();
    sheet.clearFormats();
  }

  sheet.getRange('A1:D1').merge();
  sheet.getRange('A1').setValue('📊 СТАТИСТИКА ЗАЯВОК');
  sheet.getRange('A1')
    .setFontSize(16)
    .setFontWeight('bold')
    .setFontColor('#FFFFFF')
    .setBackground('#0F766E')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');
  sheet.setRowHeight(1, 36);

  sheet.getRange('A3:B10').setValues([
    ['Показатель', 'Количество'],
    ['Всего заявок', ''],
    ['Дали согласие', ''],
    ['Заполнили анкету', ''],
    ['Записались на ДОД', ''],
    ['Пришли на ДОД', ''],
    ['В работе', ''],
    ['Связались', '']
  ]);

  sheet.getRange('B4').setFormula('=COUNTIF(Заявки!E2:E,"<>")');
  sheet.getRange('B5').setFormula('=COUNTIF(Заявки!G2:G,"Да")');
  sheet.getRange('B6').setFormula('=COUNTIF(Заявки!A2:A,"<>")');
  sheet.getRange('B7').setFormula('=COUNTIF(Заявки!R2:R,"Записан на ДОД")');
  sheet.getRange('B8').setFormula('=COUNTIF(Заявки!R2:R,"Пришел на ДОД")');
  sheet.getRange('B9').setFormula('=COUNTIF(Заявки!S2:S,"В работе")');
  sheet.getRange('B10').setFormula('=COUNTIF(Заявки!S2:S,"Связались")');

  sheet.getRange('A3:B3')
    .setFontWeight('bold')
    .setFontColor('#FFFFFF')
    .setBackground('#334155')
    .setHorizontalAlignment('center');

  sheet.getRange('A4:B10')
    .setBackground('#F8FAFC')
    .setVerticalAlignment('middle');

  sheet.getRange('B4:B10')
    .setFontSize(14)
    .setFontWeight('bold')
    .setHorizontalAlignment('center');

  sheet.getRange('A13:B13').merge();
  sheet.getRange('A13').setValue('Заявки по источникам');
  sheet.getRange('A13:B13')
    .setFontWeight('bold')
    .setFontColor('#FFFFFF')
    .setBackground('#0F766E')
    .setHorizontalAlignment('center');
  sheet.getRange('A14').setFormula(
    '=IFERROR(QUERY(Заявки!V1:V,"select V,count(V) where V is not null and V <> \'Источник\' group by V label V \'Источник\', count(V) \'Количество\'",1),"Нет данных по источникам")'
  );

  sheet.setColumnWidth(1, 250);
  sheet.setColumnWidth(2, 120);
  sheet.setFrozenRows(3);
}

function setupAll() {
  formatSheet_();
  setupOpenDay_();
  setupStats_();
  SpreadsheetApp.flush();
}

function formatNewRow_(sheet, row) {
  sheet.getRange(row, 1, 1, HEADERS.length)
    .setVerticalAlignment('top')
    .setWrap(true)
    .setFontSize(10);

  sheet.setRowHeight(row, 54);

  // После записи даём Google подогнать высоту под длинные поля.
  try {
    sheet.autoResizeRows(row, 1);
  } catch (err) {
    // Если автоизменение высоты недоступно, оставляем 54 px.
  }
}

function updateMainRowFromPayload_(sheet, row, body) {
  let values = sheet.getRange(row, 1, 1, HEADERS.length).getValues()[0];

  values[0] = new Date();

  if (body.first_name !== undefined) values[1] = body.first_name;
  if (body.last_name !== undefined) values[2] = body.last_name;
  if (body.username !== undefined) values[3] = body.username;
  if (body.telegram_id !== undefined) values[4] = String(body.telegram_id);
  if (body.phone !== undefined) values[5] = body.phone;
  if (body.consent !== undefined) values[6] = body.consent;

  if (body.school !== undefined) values[7] = body.school;
  if (body.class_number !== undefined) values[8] = body.class_number;
  if (body.surname !== undefined) values[9] = body.surname;
  if (body.name !== undefined) values[10] = body.name;
  if (body.patronymic !== undefined) values[11] = body.patronymic;
  if (body.student_phone !== undefined) values[12] = body.student_phone;
  if (body.exams !== undefined) values[13] = body.exams;
  if (body.career !== undefined) values[14] = body.career;

  if (body.booking_date !== undefined) values[15] = body.booking_date;
  if (body.booking_time !== undefined) values[16] = body.booking_time;
  if (body.booking_status !== undefined) {
    values[17] = body.booking_status;
    if (!values[18] && body.booking_status) {
      values[18] = 'Записан на ДОД';
    }
  }
  if (body.source !== undefined) values[21] = body.source;

  sheet.getRange(row, 1, 1, HEADERS.length).setValues([values]);
  formatNewRow_(sheet, row);
}

function doGet() {
  return ContentService
    .createTextOutput('MMU bot Google Sheets endpoint is working')
    .setMimeType(ContentService.MimeType.TEXT);
}

function doPost(e) {
  try {
    const body = JSON.parse((e.postData && e.postData.contents) || '{}');

    if (body.secret !== SECRET) {
      return ContentService
        .createTextOutput(JSON.stringify({
          ok: false,
          error: 'unauthorized'
        }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    const sheet = getMainSheet_();
    const telegramId = body.telegram_id;
    let row = findRowByTelegramId_(sheet, telegramId);

    if (row === -1) {
      const newRow = new Array(HEADERS.length).fill('');
      sheet.appendRow(newRow);
      row = sheet.getLastRow();

      sheet.getRange(row, 19).setValue('Новая');
    }

    updateMainRowFromPayload_(sheet, row, body);

    return ContentService
      .createTextOutput(JSON.stringify({
        ok: true,
        action: body.action || '',
        row: row
      }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    console.error(err);

    return ContentService
      .createTextOutput(JSON.stringify({
        ok: false,
        error: String(err)
      }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('ММУ')
    .addItem('Настроить таблицу', 'setupAll')
    .addToUi();
}