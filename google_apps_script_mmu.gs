/**
 * ММУ — единый Google Apps Script для Telegram-бота.
 *
 * Перед публикацией:
 * 1. Укажи новый SECRET и то же значение в Deployka -> GOOGLE_SHEET_SECRET.
 * 2. SHEET_ID оставь ID главной таблицы ММУ.
 * 3. Файл «УчебныеЗаведения.gs» оставь отдельно.
 *
 * Безопасность:
 * - не очищает лист «Заявки»;
 * - не удаляет и не переставляет существующие строки;
 * - не создаёт тестовых заявок;
 * - функции настройки менеджеров добавляют только отсутствующие заголовки.
 */

const SHEET_ID = '1iRx4N31fSFjg3RE77O4GFdeOHkIjEzWJ6efVvwUqBxs';
const SECRET = 'ВСТАВЬТЕ_НОВЫЙ_СЛУЧАЙНЫЙ_СЕКРЕТ';

const MAIN_SHEET_NAME = 'Заявки';
const UZ_REGISTRY_NAME = 'Реестр УЗ';
const DASHBOARD_NAME = 'Панель ММУ';
const DOD_LIST_NAME = 'ДОД — список';
const MANAGERS_SHEET_NAME = 'Менеджеры';
const UZ_ASSIGNMENTS_SHEET_NAME = 'Распределение УЗ';

const LEAD_HEADERS = [
  'Дата обновления', 'Имя Telegram', 'Фамилия Telegram', 'Username',
  'Telegram ID', 'Телефон Telegram', 'Согласие', 'Школа или колледж',
  'Класс', 'Фамилия', 'Имя', 'Отчество', 'Телефон абитуриента',
  'ЕГЭ', 'Сфера интересов', 'Дата ДОД', 'Время ДОД', 'Статус ДОД',
  'Статус заявки', 'Следующий контакт', 'Комментарий', 'Источник',
  'Код специальности', 'Код УЗ', 'Код менеджера'
];

const LEAD_STATUSES = [
  'Новая', 'В работе', 'Связались', 'Не дозвонились',
  'Записан на ДОД', 'Пришел на ДОД', 'Поступление',
  'Не заинтересован', 'Закрыта'
];

const MANAGER_HEADERS = [
  'Имя менеджера', 'Telegram ID', 'Статус', 'Всего анкет',
  'Дата добавления', 'Контакт', 'Всего заявок', 'Ссылка', 'Код менеджера'
];

const ASSIGNMENT_HEADERS = [
  'Имя менеджера', 'Telegram ID менеджера', 'Название УЗ', 'Код УЗ',
  'Ссылка на анкету', 'Анкет по ссылке', 'Статус',
  'Telegram ID', 'Персональная ссылка', 'Количество заявок', 'Код менеджера'
];

function getSpreadsheet_() {
  if (!SHEET_ID) throw new Error('Не указан SHEET_ID главной таблицы.');
  return SpreadsheetApp.openById(SHEET_ID);
}

function getMainSheet_() {
  const ss = getSpreadsheet_();
  let sh = ss.getSheetByName(MAIN_SHEET_NAME);
  if (!sh) sh = ss.insertSheet(MAIN_SHEET_NAME);

  if (sh.getLastRow() === 0) {
    sh.getRange(1, 1, 1, LEAD_HEADERS.length).setValues([LEAD_HEADERS]);
    sh.setFrozenRows(1);
  } else {
    // Сохраняем существующие заголовки и данные. Добавляем только пустые заголовки X/Y.
    if (!String(sh.getRange(1, 24).getDisplayValue()).trim()) {
      sh.getRange(1, 24).setValue('Код УЗ');
    }
    if (!String(sh.getRange(1, 25).getDisplayValue()).trim()) {
      sh.getRange(1, 25).setValue('Код менеджера');
    }
  }
  return sh;
}

function ensureSheetHeadersSafely_(sheet, headers) {
  if (sheet.getLastRow() === 0) {
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    sheet.setFrozenRows(1);
    return;
  }
  // Не переписываем существующие заголовки и не сдвигаем столбцы.
  const width = Math.max(sheet.getLastColumn(), headers.length);
  const current = sheet.getRange(1, 1, 1, width).getDisplayValues()[0];
  headers.forEach((header, i) => {
    if (!String(current[i] || '').trim()) sheet.getRange(1, i + 1).setValue(header);
  });
}

function findRowByTelegramId_(sheet, telegramId) {
  if (telegramId === undefined || telegramId === null || String(telegramId).trim() === '') return -1;
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return -1;
  const wanted = String(telegramId).trim();
  const ids = sheet.getRange(2, 5, lastRow - 1, 1).getDisplayValues();
  for (let i = 0; i < ids.length; i++) {
    if (String(ids[i][0]).trim() === wanted) return i + 2;
  }
  return -1;
}

/**
 * Обновляет запись в первых 23 колонках и сохраняет коды в X/Y.
 * Не перезаписывает поля, отсутствующие в payload.
 */
function updateMainRowFromPayload_(sh, row, body) {
  if (sh.getMaxColumns() < 25) sh.insertColumnsAfter(sh.getMaxColumns(), 25 - sh.getMaxColumns());

  const headers = sh.getRange(1, 1, 1, Math.max(sh.getLastColumn(), 25)).getDisplayValues()[0];
  if (!String(headers[23] || '').trim()) sh.getRange(1, 24).setValue('Код УЗ');
  if (!String(headers[24] || '').trim()) sh.getRange(1, 25).setValue('Код менеджера');

  const values = sh.getRange(row, 1, 1, 23).getValues()[0];
  values[0] = new Date();

  const map = [
    ['first_name', 1], ['last_name', 2], ['username', 3],
    ['telegram_id', 4], ['phone', 5], ['consent', 6],
    ['school', 7], ['class_number', 8], ['surname', 9],
    ['name', 10], ['patronymic', 11], ['student_phone', 12],
    ['exams', 13], ['career', 14], ['booking_date', 15],
    ['booking_time', 16], ['booking_status', 17], ['source', 21],
    ['specialty_code', 22]
  ];

  map.forEach(([key, index]) => {
    if (body[key] !== undefined && body[key] !== null) {
      values[index] = key === 'telegram_id' ? String(body[key]) : body[key];
    }
  });

  if (body.open_day_date !== undefined && body.booking_date === undefined) values[15] = body.open_day_date;
  if (body.open_day_time !== undefined && body.booking_time === undefined) values[16] = body.open_day_time;

  if (body.booking_status === 'Пришел на ДОД') {
    values[18] = 'Пришел на ДОД';
  } else if (
    body.booking_status === 'Записан на ДОД' &&
    ['', 'Новая', 'В работе', 'Связались', 'Не дозвонились'].includes(String(values[18] || ''))
  ) {
    values[18] = 'Записан на ДОД';
  }
  if (!values[18] && values[4]) values[18] = 'Новая';

  sh.getRange(row, 1, 1, 23).setValues([values]);
  if (body.uz_code !== undefined && body.uz_code !== null && String(body.uz_code).trim()) {
    sh.getRange(row, 24).setValue(String(body.uz_code).trim().toUpperCase());
  }
  if (body.manager_code !== undefined && body.manager_code !== null && String(body.manager_code).trim()) {
    sh.getRange(row, 25).setValue(String(body.manager_code).trim().toUpperCase());
  }

  sh.getRange(row, 1).setNumberFormat('dd.MM.yyyy HH:mm');
  sh.getRange(row, 16).setNumberFormat('dd.MM.yyyy');
  sh.getRange(row, 17).setNumberFormat('HH:mm');
}

/**
 * Маршрутизация: при наличии uz_code выбирает отдельную таблицу из реестра.
 * Без uz_code заявка сохраняется в главной таблице ММУ.
 */
function getUzDestination_(body) {
  const uzCode = String(body.uz_code || '').trim().toUpperCase();
  if (!uzCode) return { sheet: getMainSheet_(), uzCode: '', uzName: 'ММУ' };

  const master = getSpreadsheet_();
  const registry = master.getSheetByName(UZ_REGISTRY_NAME);
  if (!registry || registry.getLastRow() < 2) {
    throw new Error('Реестр УЗ не найден или не содержит записей.');
  }

  const rows = registry.getRange(2, 1, registry.getLastRow() - 1, 7).getValues();
  const match = rows.find(r => String(r[1] || '').trim().toUpperCase() === uzCode);
  if (!match) throw new Error('Не найден код учебного заведения: ' + uzCode);

  const spreadsheetId = String(match[2] || '').trim();
  if (!spreadsheetId) throw new Error('Для УЗ «' + match[0] + '» не указан ID отдельной таблицы.');

  const uzSpreadsheet = SpreadsheetApp.openById(spreadsheetId);
  let sheet = uzSpreadsheet.getSheetByName(MAIN_SHEET_NAME);
  if (!sheet) throw new Error('В таблице «' + match[0] + '» отсутствует лист «Заявки».');

  // Для отдельных таблиц также добавляем только недостающие поля X/Y.
  if (sheet.getMaxColumns() < 25) sheet.insertColumnsAfter(sheet.getMaxColumns(), 25 - sheet.getMaxColumns());
  if (!String(sheet.getRange(1, 24).getDisplayValue()).trim()) sheet.getRange(1, 24).setValue('Код УЗ');
  if (!String(sheet.getRange(1, 25).getDisplayValue()).trim()) sheet.getRange(1, 25).setValue('Код менеджера');

  return { sheet: sheet, uzCode: uzCode, uzName: String(match[0] || '') };
}

function doGet() {
  return ContentService.createTextOutput('MMU Google Sheets endpoint is working')
    .setMimeType(ContentService.MimeType.TEXT);
}

function doPost(e) {
  const lock = LockService.getScriptLock();
  try {
    lock.waitLock(10000);
    const raw = e && e.postData && e.postData.contents ? e.postData.contents : '{}';
    const body = JSON.parse(raw);

    if (!SECRET || SECRET.indexOf('ВСТАВЬТЕ_') === 0 || body.secret !== SECRET) {
      return jsonResponse_({ ok: false, error: 'unauthorized' });
    }
    if (!body.telegram_id) return jsonResponse_({ ok: false, error: 'missing_telegram_id' });

    const destination = getUzDestination_(body);
    const sh = destination.sheet;
    let row = findRowByTelegramId_(sh, body.telegram_id);

    if (row === -1) {
      sh.appendRow(new Array(25).fill(''));
      row = sh.getLastRow();
      sh.getRange(row, 19).setValue('Новая');
    }

    updateMainRowFromPayload_(sh, row, body);
    SpreadsheetApp.flush();

    // Уведомление менеджеру отправляется только после подтверждённой записи анкеты.
    let managerNotified = false;
    if (String(body.action || '') === 'questionnaire' && String(body.manager_code || '').trim()) {
      managerNotified = notifyAssignedManagerSafely_(body, destination, row);
    }

    return jsonResponse_({
      ok: true,
      action: body.action || '',
      row: row,
      uz_code: destination.uzCode,
      uz_name: destination.uzName,
      manager_code: String(body.manager_code || ''),
      manager_notified: managerNotified
    });
  } catch (err) {
    console.error(err);
    return jsonResponse_({ ok: false, error: String(err) });
  } finally {
    try { lock.releaseLock(); } catch (ignored) {}
  }
}

function jsonResponse_(data) {
  return ContentService.createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}

/**
 * Безопасно создаёт вкладки менеджеров и добавляет отсутствующие заголовки.
 * Не очищает вкладки и не изменяет существующие строки.
 */
function setupManagerSystem() {
  const ss = getSpreadsheet_();
  let managers = ss.getSheetByName(MANAGERS_SHEET_NAME);
  if (!managers) managers = ss.insertSheet(MANAGERS_SHEET_NAME);
  let assignments = ss.getSheetByName(UZ_ASSIGNMENTS_SHEET_NAME);
  if (!assignments) assignments = ss.insertSheet(UZ_ASSIGNMENTS_SHEET_NAME);

  ensureSheetHeadersSafely_(managers, MANAGER_HEADERS);
  ensureSheetHeadersSafely_(assignments, ASSIGNMENT_HEADERS);

  managers.setFrozenRows(1);
  assignments.setFrozenRows(1);
  managers.getRange(1, 1, 1, MANAGER_HEADERS.length)
    .setBackground('#17365D').setFontColor('#FFFFFF').setFontWeight('bold').setWrap(true);
  assignments.getRange(1, 1, 1, ASSIGNMENT_HEADERS.length)
    .setBackground('#17365D').setFontColor('#FFFFFF').setFontWeight('bold').setWrap(true);

  [180, 140, 100, 110, 150, 180, 110, 280, 140].forEach((w, i) => managers.setColumnWidth(i + 1, w));
  [180, 160, 220, 130, 350, 130, 100, 140, 380, 140, 140].forEach((w, i) => assignments.setColumnWidth(i + 1, w));
  return 'Вкладки менеджеров проверены. Существующие данные сохранены.';
}

/**
 * Пересчитывает статистику менеджеров только там, где строки можно
 * однозначно сопоставить по заголовку «Код менеджера».
 * Не исправляет автоматически неоднозначные/перепутанные строки распределения.
 */
function refreshManagerCountsSafely() {
  const ss = getSpreadsheet_();
  const main = getMainSheet_();
  const managers = ss.getSheetByName(MANAGERS_SHEET_NAME);
  if (!managers) throw new Error('Сначала запусти setupManagerSystem().');

  const leadLast = main.getLastRow();
  const counts = {};
  if (leadLast >= 2) {
    const leadData = main.getRange(2, 1, leadLast - 1, 25).getValues();
    leadData.forEach(r => {
      const managerCode = String(r[24] || '').trim().toUpperCase();
      if (managerCode) counts[managerCode] = (counts[managerCode] || 0) + 1;
    });
  }

  const last = managers.getLastRow();
  if (last < 2) return 'Вкладка «Менеджеры» пока не содержит менеджеров.';
  const headers = managers.getRange(1, 1, 1, managers.getLastColumn()).getDisplayValues()[0];
  const codeCol = headers.indexOf('Код менеджера') + 1;
  const totalCol = headers.indexOf('Всего заявок') + 1;
  const formsCol = headers.indexOf('Всего анкет') + 1;
  if (!codeCol) throw new Error('В «Менеджеры» отсутствует столбец «Код менеджера».');

  const rows = managers.getRange(2, 1, last - 1, managers.getLastColumn()).getValues();
  rows.forEach((r, i) => {
    const code = String(r[codeCol - 1] || '').trim().toUpperCase();
    if (!code) return;
    const n = counts[code] || 0;
    if (totalCol) managers.getRange(i + 2, totalCol).setValue(n);
    if (formsCol) managers.getRange(i + 2, formsCol).setValue(n);
  });
  return 'Статистика менеджеров обновлена по кодам из заявок.';
}

/**
 * Обновляет обычные ссылки в реестре, не меняя другие поля и строки.
 * Не генерирует персональные ссылки менеджеров.
 */
function refreshUzBotLinksSafely() {
  const ss = getSpreadsheet_();
  const registry = ss.getSheetByName(UZ_REGISTRY_NAME);
  if (!registry) throw new Error('Не найдена вкладка «Реестр УЗ».');
  const last = registry.getLastRow();
  if (last < 2) return 'Реестр пока пуст.';
  for (let row = 2; row <= last; row++) {
    const code = String(registry.getRange(row, 2).getDisplayValue() || '').trim().toUpperCase();
    if (!code) continue;
    const url = 'https://t.me/UniversityQuestionnaireMMUbot?start=uz_' + encodeURIComponent(code);
    registry.getRange(row, 5).setRichTextValue(
      SpreadsheetApp.newRichTextValue().setText(url).setLinkUrl(url).build()
    );
  }
  return 'Ссылки бота в реестре обновлены.';
}

/**
 * Настраивает только панель статистики. Очищает исключительно «Панель ММУ».
 * Запускай только если согласен пересоздать содержимое этой вкладки.
 */
function setupMmuDashboard() {
  const ss = getSpreadsheet_();
  getMainSheet_();
  let sh = ss.getSheetByName(DASHBOARD_NAME);
  if (!sh) sh = ss.insertSheet(DASHBOARD_NAME);
  sh.clear();
  sh.clearFormats();

  sh.getRange('A1:F1').merge();
  sh.getRange('A1').setValue('ММУ | ПАНЕЛЬ АБИТУРИЕНТОВ');
  sh.getRange('A1:F1').setBackground('#12304A').setFontColor('#FFFFFF')
    .setFontWeight('bold').setFontSize(16).setHorizontalAlignment('center');
  sh.setRowHeight(1, 42);
  sh.getRange('A2').setValue('Обновлено:');
  sh.getRange('B2').setFormula('=NOW()').setNumberFormat('dd.MM.yyyy HH:mm');

  sh.getRange('A4:B4').setValues([['ОСНОВНЫЕ ПОКАЗАТЕЛИ', 'КОЛИЧЕСТВО']]);
  sh.getRange('A5:A14').setValues([
    ['Уникальные заявители'], ['Дали согласие'], ['Анкета заполнена'],
    ['Записаны на ДОД'], ['Пришли на ДОД'], ['Новые лиды'],
    ['В работе'], ['Связались'], ['Поступление'], ['Не заинтересованы']
  ]);
  const formulas = [
    '=COUNTIF(Заявки!E2:E,"<>")',
    '=COUNTIF(Заявки!G2:G,"Да")',
    '=COUNTIFS(Заявки!J2:J,"<>",Заявки!K2:K,"<>",Заявки!M2:M,"<>")',
    '=COUNTIF(Заявки!R2:R,"Записан на ДОД")',
    '=COUNTIF(Заявки!R2:R,"Пришел на ДОД")',
    '=COUNTIF(Заявки!S2:S,"Новая")',
    '=COUNTIF(Заявки!S2:S,"В работе")',
    '=COUNTIF(Заявки!S2:S,"Связались")',
    '=COUNTIF(Заявки!S2:S,"Поступление")',
    '=COUNTIF(Заявки!S2:S,"Не заинтересован")'
  ];
  sh.getRange('B5:B14').setFormulas(formulas.map(f => [f]));
  sh.getRange('A4:B4').setBackground('#D9EAF7').setFontWeight('bold').setHorizontalAlignment('center');
  sh.getRange('A5:A14').setFontWeight('bold');
  sh.getRange('B5:B14').setHorizontalAlignment('center').setNumberFormat('0');
  sh.getRange('A4:B14').setBorder(true, true, true, true, true, true);
  sh.setColumnWidth(1, 250);
  sh.setColumnWidth(2, 150);
  sh.setFrozenRows(4);
  return 'Панель ММУ обновлена.';
}

/**
 * Пересоздаёт содержимое только «ДОД — список». Не очищает «Заявки».
 * Запускай только если согласен обновить этот список.
 */
function setupMmuDodList() {
  const ss = getSpreadsheet_();
  getMainSheet_();
  let sh = ss.getSheetByName(DOD_LIST_NAME);
  if (!sh) sh = ss.insertSheet(DOD_LIST_NAME);
  sh.clear();
  sh.clearFormats();
  sh.getRange('A1:I1').setValues([[
    'Дата ДОД', 'Время', 'Имя', 'Фамилия', 'Телефон',
    'Telegram', 'Источник', 'Статус ДОД', 'Комментарий'
  ]]);
  sh.getRange('A1:I1').setBackground('#12304A').setFontColor('#FFFFFF').setFontWeight('bold').setWrap(true);
  sh.getRange('A2').setFormula(
    '=IFERROR(QUERY(Заявки!A:W,"select P,Q,K,J,F,D,V,R,U where R matches \'Записан на ДОД|Пришел на ДОД\' order by P,Q",1),"Пока нет записей на ДОД")'
  );
  [110, 85, 130, 130, 150, 140, 180, 150, 260].forEach((w, i) => sh.setColumnWidth(i + 1, w));
  sh.setFrozenRows(1);
  SpreadsheetApp.flush();
  return 'Список ДОД обновлён.';
}

function formatMmuLeadsSafely() {
  const sh = getMainSheet_();
  sh.setFrozenRows(1);
  sh.setFrozenColumns(2);
  sh.getRange(1, 1, 1, 25).setBackground('#12304A').setFontColor('#FFFFFF')
    .setFontWeight('bold').setWrap(true).setVerticalAlignment('middle');
  sh.setRowHeight(1, 42);
  const last = Math.max(sh.getLastRow(), 2);
  if (!sh.getFilter()) sh.getRange(1, 1, last, 25).createFilter();
  const widths = [150,125,125,125,115,150,90,180,85,140,125,135,150,200,190,110,85,145,150,130,280,180,150,130,140];
  widths.forEach((w, i) => sh.setColumnWidth(i + 1, w));
  sh.getRange('A2:A').setNumberFormat('dd.MM.yyyy HH:mm');
  sh.getRange('P2:P').setNumberFormat('dd.MM.yyyy');
  sh.getRange('Q2:Q').setNumberFormat('HH:mm');
  sh.getRange('T2:T').setNumberFormat('dd.MM.yyyy');
  const statusRule = SpreadsheetApp.newDataValidation().requireValueInList(LEAD_STATUSES, true).setAllowInvalid(true).build();
  sh.getRange('S2:S').setDataValidation(statusRule);
  return 'Оформление «Заявки» завершено без очистки данных.';
}

/**
 * Отправляет уведомление менеджеру, если код менеджера найден в таблице «Менеджеры».
 * В Script Properties нужно задать TELEGRAM_BOT_TOKEN.
 * Отсутствие токена/менеджера не отменяет сохранение анкеты.
 */
function notifyAssignedManagerSafely_(body, destination, row) {
  try {
    const token = PropertiesService.getScriptProperties().getProperty('TELEGRAM_BOT_TOKEN');
    if (!token) {
      console.warn('TELEGRAM_BOT_TOKEN не задан в Script Properties; уведомление менеджеру пропущено.');
      return false;
    }

    const ss = getSpreadsheet_();
    const managers = ss.getSheetByName(MANAGERS_SHEET_NAME);
    if (!managers || managers.getLastRow() < 2) return false;

    const headers = managers.getRange(1, 1, 1, managers.getLastColumn()).getDisplayValues()[0];
    const codeCol = headers.indexOf('Код менеджера');
    const idCol = headers.indexOf('Telegram ID');
    const statusCol = headers.indexOf('Статус');
    const nameCol = headers.indexOf('Имя менеджера');
    if (codeCol < 0 || idCol < 0) {
      console.warn('В «Менеджеры» нужны столбцы «Код менеджера» и «Telegram ID».');
      return false;
    }

    const wanted = String(body.manager_code || '').trim().toUpperCase();
    const values = managers.getRange(2, 1, managers.getLastRow() - 1, managers.getLastColumn()).getDisplayValues();
    const manager = values.find(r =>
      String(r[codeCol] || '').trim().toUpperCase() === wanted &&
      (!statusCol || String(r[statusCol] || '').trim().toLowerCase() === 'активен')
    );
    if (!manager) {
      console.warn('Не найден активный менеджер с кодом ' + wanted);
      return false;
    }

    const chatId = String(manager[idCol] || '').trim();
    if (!/^\d+$/.test(chatId)) {
      console.warn('Некорректный Telegram ID менеджера для кода ' + wanted);
      return false;
    }

    const lead = destination.sheet.getRange(row, 1, 1, 25).getDisplayValues()[0];
    const managerName = nameCol >= 0 ? String(manager[nameCol] || 'Менеджер') : 'Менеджер';
    const fullName = [lead[9], lead[10], lead[11]].filter(Boolean).join(' ') || 'Не указано';
    const message = [
      '🆕 <b>Новая анкета ММУ</b>',
      '',
      '👤 <b>Абитуриент:</b> ' + escapeTelegramHtml_(fullName),
      '📱 <b>Телефон:</b> ' + escapeTelegramHtml_(lead[12] || lead[5] || 'не указан'),
      '🏫 <b>Учебное заведение:</b> ' + escapeTelegramHtml_(destination.uzName || 'ММУ'),
      '🔖 <b>Код УЗ:</b> ' + escapeTelegramHtml_(destination.uzCode || 'не указан'),
      '👥 <b>Менеджер:</b> ' + escapeTelegramHtml_(managerName),
      '📌 <b>Статус:</b> ' + escapeTelegramHtml_(lead[18] || 'Новая')
    ].join('\n');

    const response = UrlFetchApp.fetch('https://api.telegram.org/bot' + token + '/sendMessage', {
      method: 'post',
      contentType: 'application/json',
      payload: JSON.stringify({ chat_id: chatId, text: message, parse_mode: 'HTML' }),
      muteHttpExceptions: true
    });
    const result = JSON.parse(response.getContentText() || '{}');
    if (!result.ok) {
      console.warn('Telegram API не подтвердил отправку уведомления менеджеру: ' + response.getResponseCode());
      return false;
    }
    return true;
  } catch (err) {
    console.error('Ошибка уведомления менеджера: ' + String(err));
    return false;
  }
}

function escapeTelegramHtml_(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/**
 * Пересчитывает статистику менеджеров по главной и отдельным таблицам УЗ.
 * Сопоставление идёт по заголовку «Код менеджера» в колонке Y.
 * Данные и существующие строки не изменяются.
 */
function refreshManagerCountsAcrossUzSafely() {
  const master = getSpreadsheet_();
  const registry = master.getSheetByName(UZ_REGISTRY_NAME);
  const counts = {};
  const seenIds = {};

  function countSheet(sheet) {
    if (!sheet || sheet.getLastRow() < 2) return;
    const headers = sheet.getRange(1, 1, 1, Math.max(sheet.getLastColumn(), 25)).getDisplayValues()[0];
    let managerCol = headers.indexOf('Код менеджера') + 1;
    if (managerCol < 1) managerCol = 25;
    const vals = sheet.getRange(2, managerCol, sheet.getLastRow() - 1, 1).getDisplayValues();
    vals.forEach(r => {
      const code = String(r[0] || '').trim().toUpperCase();
      if (code) counts[code] = (counts[code] || 0) + 1;
    });
  }

  countSheet(master.getSheetByName(MAIN_SHEET_NAME));
  if (registry && registry.getLastRow() >= 2) {
    const rows = registry.getRange(2, 1, registry.getLastRow() - 1, 7).getDisplayValues();
    rows.forEach(r => {
      const id = String(r[2] || '').trim();
      if (!id || seenIds[id]) return;
      seenIds[id] = true;
      try {
        const book = SpreadsheetApp.openById(id);
        countSheet(book.getSheetByName(MAIN_SHEET_NAME));
      } catch (err) {
        console.warn('Не удалось прочитать таблицу УЗ ' + String(r[0] || '') + ': ' + String(err));
      }
    });
  }

  const managers = master.getSheetByName(MANAGERS_SHEET_NAME);
  if (!managers || managers.getLastRow() < 2) return 'Нет строк менеджеров для подсчёта.';
  const headers = managers.getRange(1, 1, 1, managers.getLastColumn()).getDisplayValues()[0];
  const codeCol = headers.indexOf('Код менеджера');
  const totalCol = headers.indexOf('Всего заявок');
  const formsCol = headers.indexOf('Всего анкет');
  if (codeCol < 0) throw new Error('В «Менеджеры» отсутствует столбец «Код менеджера».');
  const data = managers.getRange(2, 1, managers.getLastRow() - 1, managers.getLastColumn()).getValues();
  data.forEach((r, i) => {
    const code = String(r[codeCol] || '').trim().toUpperCase();
    if (!code) return;
    const n = counts[code] || 0;
    if (totalCol >= 0) managers.getRange(i + 2, totalCol + 1).setValue(n);
    if (formsCol >= 0) managers.getRange(i + 2, formsCol + 1).setValue(n);
  });
  SpreadsheetApp.flush();
  return 'Статистика менеджеров обновлена по всем таблицам УЗ.';
}
