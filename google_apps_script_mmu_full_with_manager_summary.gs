
/*******************************************************
 * ММУ — GOOGLE SHEETS API
 * Заявки, статистика, ДОД и маршрутизация по УЗ
 *
 * ВАЖНО:
 * 1. Укажи свой прежний SECRET.
 * 2. SHEET_ID должен указывать на главную таблицу.
 * 3. Файл УчебныеЗаведения.gs оставь отдельно.
 *******************************************************/

const SHEET_ID = '1iRx4N31fSFjg3RE77O4GFdeOHkIjEzWJ6efVvwUqBxs';
const SECRET = '';

const MAIN_SHEET_NAME = 'Заявки';
const UZ_REGISTRY_NAME = 'Реестр УЗ';
const DASHBOARD_NAME = 'Панель ММУ';
const DOD_LIST_NAME = 'ДОД — список';

const LEAD_HEADERS = [
  'Дата обновления',
  'Имя Telegram',
  'Фамилия Telegram',
  'Username',
  'Telegram ID',
  'Телефон Telegram',
  'Согласие',
  'Школа или колледж',
  'Класс',
  'Фамилия',
  'Имя',
  'Отчество',
  'Телефон абитуриента',
  'ЕГЭ',
  'Сфера интересов',
  'Дата ДОД',
  'Время ДОД',
  'Статус ДОД',
  'Статус заявки',
  'Следующий контакт',
  'Комментарий',
  'Источник',
  'Код специальности'
];


/*******************************************************
 * ГЛАВНАЯ ТАБЛИЦА
 *******************************************************/

/**
 * Возвращает главную Google Таблицу.
 */
function getSpreadsheet_() {
  if (!SHEET_ID || SHEET_ID.indexOf('ВСТАВЬТЕ_') === 0) {
    throw new Error('Не указан SHEET_ID главной таблицы.');
  }

  return SpreadsheetApp.openById(SHEET_ID);
}


/**
 * Возвращает лист заявок ММУ.
 * Если листа нет, создаёт его.
 * Существующие данные не очищает.
 */
function getMainSheet_() {
  const ss = getSpreadsheet_();
  let sh = ss.getSheetByName(MAIN_SHEET_NAME);

  if (!sh) {
    sh = ss.insertSheet(MAIN_SHEET_NAME);
  }

  if (sh.getLastRow() === 0) {
    sh.getRange(1, 1, 1, LEAD_HEADERS.length)
      .setValues([LEAD_HEADERS]);
    sh.setFrozenRows(1);
  }

  return sh;
}


/**
 * Ищет заявителя по Telegram ID.
 * Возвращает номер строки либо -1.
 */
function findRowByTelegramId_(sh, telegramId) {
  const lastRow = sh.getLastRow();

  if (lastRow < 2) {
    return -1;
  }

  const target = String(telegramId).trim();

  const ids = sh.getRange(2, 5, lastRow - 1, 1)
    .getDisplayValues();

  for (let i = 0; i < ids.length; i++) {
    if (String(ids[i][0]).trim() === target) {
      return i + 2;
    }
  }

  return -1;
}


/**
 * Обновляет данные заявителя.
 * Соответствует структуре из 23 столбцов.
 */
function updateMainRowFromPayload_(sh, row, body) {
  const values = sh.getRange(row, 1, 1, 23).getValues()[0];

  values[0] = new Date();

  const map = [
    ['first_name', 1],
    ['last_name', 2],
    ['username', 3],
    ['telegram_id', 4],
    ['phone', 5],
    ['consent', 6],
    ['school', 7],
    ['class_number', 8],
    ['surname', 9],
    ['name', 10],
    ['patronymic', 11],
    ['student_phone', 12],
    ['exams', 13],
    ['career', 14],
    ['booking_date', 15],
    ['booking_time', 16],
    ['booking_status', 17],
    ['source', 21],
    ['specialty_code', 22]
  ];

  map.forEach(function(item) {
    const key = item[0];
    const index = item[1];

    if (body[key] !== undefined && body[key] !== null) {
      values[index] =
        key === 'telegram_id'
          ? String(body[key])
          : body[key];
    }
  });

  if (
    body.open_day_date !== undefined &&
    body.booking_date === undefined
  ) {
    values[15] = body.open_day_date;
  }

  if (
    body.open_day_time !== undefined &&
    body.booking_time === undefined
  ) {
    values[16] = body.open_day_time;
  }

  if (body.booking_status === 'Пришел на ДОД') {
    values[18] = 'Пришел на ДОД';

  } else if (
    body.booking_status === 'Записан на ДОД' &&
    ['', 'Новая', 'В работе', 'Связались', 'Не дозвонились']
      .includes(String(values[18] || ''))
  ) {
    values[18] = 'Записан на ДОД';
  }

  if (!values[18] && values[4]) {
    values[18] = 'Новая';
  }

  sh.getRange(row, 1, 1, 23).setValues([values]);

  sh.getRange(row, 1).setNumberFormat('dd.MM.yyyy HH:mm');
  sh.getRange(row, 16).setNumberFormat('dd.MM.yyyy');
  sh.getRange(row, 17).setNumberFormat('HH:mm');
}


/*******************************************************
 * ВЫБОР ТАБЛИЦЫ УЧЕБНОГО ЗАВЕДЕНИЯ
 *******************************************************/

/**
 * Если пришёл uz_code, ищет УЗ в реестре
 * и направляет заявку в его отдельную таблицу.
 *
 * Если uz_code отсутствует, использует прежнюю
 * главную таблицу ММУ.
 */
function getUzDestination_(body) {
  const uzCode = String(body.uz_code || '')
    .trim()
    .toUpperCase();

  if (!uzCode) {
    return {
      sheet: getMainSheet_(),
      uzCode: '',
      uzName: 'ММУ'
    };
  }

  const master = getSpreadsheet_();
  const registry = master.getSheetByName(UZ_REGISTRY_NAME);

  if (!registry || registry.getLastRow() < 2) {
    throw new Error('Реестр УЗ не найден или не содержит записей.');
  }

  const rows = registry
    .getRange(2, 1, registry.getLastRow() - 1, 7)
    .getValues();

  const match = rows.find(function(item) {
    return String(item[1] || '').trim().toUpperCase() === uzCode;
  });

  if (!match) {
    throw new Error('Не найден код учебного заведения: ' + uzCode);
  }

  const spreadsheetId = String(match[2] || '').trim();

  if (!spreadsheetId) {
    throw new Error(
      'Для УЗ "' + match[0] + '" не указан ID отдельной таблицы.'
    );
  }

  const uzSpreadsheet = SpreadsheetApp.openById(spreadsheetId);
  const sheet = uzSpreadsheet.getSheetByName(MAIN_SHEET_NAME);

  if (!sheet) {
    throw new Error(
      'В таблице "' + match[0] + '" отсутствует лист "Заявки".'
    );
  }

  return {
    sheet: sheet,
    uzCode: uzCode,
    uzName: String(match[0] || '')
  };
}


/*******************************************************
 * WEB APP
 *******************************************************/

/**
 * Проверка работоспособности веб-приложения.
 */
function doGet() {
  return ContentService
    .createTextOutput('MMU Google Sheets endpoint is working')
    .setMimeType(ContentService.MimeType.TEXT);
}


/**
 * Получает данные от Telegram-бота.
 */
function doPost(e) {
  const lock = LockService.getScriptLock();

  try {
    lock.waitLock(10000);

    const raw = e && e.postData && e.postData.contents
      ? e.postData.contents
      : '{}';

    const body = JSON.parse(raw);

    if (
      !SECRET ||
      SECRET.indexOf('ЗАМЕНИТЕ_') === 0 ||
      SECRET.indexOf('ВСТАВЬТЕ_') === 0 ||
      body.secret !== SECRET
    ) {
      return jsonResponse_({
        ok: false,
        error: 'unauthorized'
      });
    }

    // Сводка для руководителя. Только чтение, строки не изменяются.
    if (body.action === 'leadership_summary') {
      return jsonResponse_({
        ok: true,
        action: 'leadership_summary',
        summary: getLeadershipSummary_()
      });
    }

    if (!body.telegram_id) {
      return jsonResponse_({
        ok: false,
        error: 'missing_telegram_id'
      });
    }

    // Выбираем таблицу по коду УЗ.
    const destination = getUzDestination_(body);
    const sh = destination.sheet;

    // Обновляем существующую заявку или добавляем новую.
    let row = findRowByTelegramId_(sh, body.telegram_id);

    if (row === -1) {
      sh.appendRow(new Array(23).fill(''));
      row = sh.getLastRow();
      sh.getRange(row, 19).setValue('Новая');
    }

    updateMainRowFromPayload_(sh, row, body);

    SpreadsheetApp.flush();

    return jsonResponse_({
      ok: true,
      action: body.action || '',
      row: row,
      uz_code: destination.uzCode,
      uz_name: destination.uzName
    });

  } catch (err) {
    console.error(err);

    return jsonResponse_({
      ok: false,
      error: String(err)
    });

  } finally {
    try {
      lock.releaseLock();
    } catch (ignored) {}
  }
}


/**
 * Формирует ответ веб-приложения в JSON.
 */
function jsonResponse_(data) {
  return ContentService
    .createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}


/*******************************************************
 * СВОДКА РУКОВОДИТЕЛЮ
 *******************************************************/

/**
 * Считает заявки из главной таблицы и всех отдельных таблиц УЗ.
 * Не изменяет данные. Повторные Telegram ID считаются один раз.
 */
function getLeadershipSummary_() {
  const master = getSpreadsheet_();
  const registry = master.getSheetByName(UZ_REGISTRY_NAME);
  const spreadsheetIds = [];

  if (registry && registry.getLastRow() > 1) {
    registry.getRange(2, 3, registry.getLastRow() - 1, 1)
      .getDisplayValues()
      .forEach(function(row) {
        const id = String(row[0] || '').trim();
        if (id && id !== master.getId() && spreadsheetIds.indexOf(id) === -1) {
          spreadsheetIds.push(id);
        }
      });
  }

  const sheets = [getMainSheet_()];
  spreadsheetIds.forEach(function(id) {
    try {
      const ss = SpreadsheetApp.openById(id);
      const sh = ss.getSheetByName(MAIN_SHEET_NAME);
      if (sh) sheets.push(sh);
    } catch (err) {
      console.warn('Не удалось прочитать таблицу УЗ ' + id + ': ' + err);
    }
  });

  const seen = {};
  const counts = {
    total: 0,
    new: 0,
    in_work: 0,
    contacted: 0,
    dod_booked: 0,
    dod_attended: 0,
    admission: 0,
    not_interested: 0
  };

  sheets.forEach(function(sh) {
    if (sh.getLastRow() < 2) return;
    const rows = sh.getRange(2, 1, sh.getLastRow() - 1, 23).getDisplayValues();
    rows.forEach(function(row) {
      const telegramId = String(row[4] || '').trim();
      if (!telegramId || seen[telegramId]) return;
      seen[telegramId] = true;
      counts.total++;

      const dodStatus = String(row[17] || '').trim();
      const leadStatus = String(row[18] || '').trim();

      if (leadStatus === 'Новая') counts.new++;
      if (leadStatus === 'В работе') counts.in_work++;
      if (leadStatus === 'Связались') counts.contacted++;
      if (leadStatus === 'Поступление') counts.admission++;
      if (leadStatus === 'Не заинтересован' || leadStatus === 'Не заинтересованы') {
        counts.not_interested++;
      }
      if (dodStatus === 'Записан на ДОД') counts.dod_booked++;
      if (dodStatus === 'Пришел на ДОД' || dodStatus === 'Пришёл на ДОД') {
        counts.dod_attended++;
      }
    });
  });

  return counts;
}


/*******************************************************
 * ПАНЕЛЬ СТАТИСТИКИ ММУ
 *******************************************************/

/**
 * Создаёт панель статистики.
 * Очищает только вкладку «Панель ММУ».
 */
function setupMmuDashboard() {
  const ss = getSpreadsheet_();
  getMainSheet_();

  let sh = ss.getSheetByName(DASHBOARD_NAME);

  if (!sh) {
    sh = ss.insertSheet(DASHBOARD_NAME);
  }

  sh.clear();
  sh.clearFormats();

  sh.getRange('A1:F1').merge();
  sh.getRange('A1')
    .setValue('ММУ | ПАНЕЛЬ АБИТУРИЕНТОВ');

  sh.getRange('A1:F1')
    .setBackground('#12304A')
    .setFontColor('#FFFFFF')
    .setFontWeight('bold')
    .setFontSize(16)
    .setHorizontalAlignment('center');

  sh.setRowHeight(1, 42);

  sh.getRange('A2').setValue('Обновлено:');
  sh.getRange('B2')
    .setFormula('=NOW()')
    .setNumberFormat('dd.MM.yyyy HH:mm');

  sh.getRange('A4:B4').setValues([
    ['ОСНОВНЫЕ ПОКАЗАТЕЛИ', 'КОЛИЧЕСТВО']
  ]);

  sh.getRange('A5:A14').setValues([
    ['Уникальные заявители'],
    ['Дали согласие'],
    ['Анкета заполнена'],
    ['Записаны на ДОД'],
    ['Пришли на ДОД'],
    ['Новые лиды'],
    ['В работе'],
    ['Связались'],
    ['Поступление'],
    ['Не заинтересованы']
  ]);

  // Разделитель аргументов — точка с запятой.
  sh.getRange('B5:B14').setFormulas([
    ['=IFERROR(COUNTUNIQUE(FILTER(\'Заявки\'!E2:E;\'Заявки\'!E2:E<>""));0)'],
    ['=COUNTIF(\'Заявки\'!G2:G;"<>")'],
    ['=COUNTIFS(\'Заявки\'!J2:J;"<>";\'Заявки\'!K2:K;"<>")'],
    ['=COUNTIF(\'Заявки\'!R2:R;"Записан на ДОД")'],
    ['=COUNTIF(\'Заявки\'!R2:R;"Пришел на ДОД")'],
    ['=COUNTIF(\'Заявки\'!S2:S;"Новая")'],
    ['=COUNTIF(\'Заявки\'!S2:S;"В работе")'],
    ['=COUNTIF(\'Заявки\'!S2:S;"Связались")'],
    ['=COUNTIF(\'Заявки\'!S2:S;"Поступление")'],
    ['=COUNTIF(\'Заявки\'!S2:S;"Не заинтересованы")']
  ]);

  sh.getRange('A4:B4')
    .setBackground('#D9EAF7')
    .setFontWeight('bold')
    .setHorizontalAlignment('center');

  sh.getRange('A5:A14').setFontWeight('bold');
  sh.getRange('B5:B14')
    .setHorizontalAlignment('center')
    .setNumberFormat('0');

  sh.getRange('A4:B14')
    .setBorder(true, true, true, true, true, true);

  sh.setColumnWidth(1, 250);
  sh.setColumnWidth(2, 150);
  sh.setColumnWidths(3, 4, 130);

  sh.setFrozenRows(4);

  return 'Панель ММУ обновлена.';
}


/*******************************************************
 * СПИСОК ДОД
 *******************************************************/

/**
 * Создаёт список заявителей с заполненной датой ДОД.
 * Изменяется только вкладка «ДОД — список».
 */
function setupMmuDodList() {
  const ss = getSpreadsheet_();
  getMainSheet_();

  let sh = ss.getSheetByName(DOD_LIST_NAME);

  if (!sh) {
    sh = ss.insertSheet(DOD_LIST_NAME);
  }

  sh.clear();

  sh.getRange('A1').setFormula(
    '=IFERROR(FILTER(\'Заявки\'!A1:W;\'Заявки\'!P1:P<>"");"Нет записей")'
  );

  sh.setFrozenRows(1);
  sh.setRowHeight(1, 36);

  sh.getRange('A1:W1')
    .setBackground('#12304A')
    .setFontColor('#FFFFFF')
    .setFontWeight('bold')
    .setWrapStrategy(SpreadsheetApp.WrapStrategy.WRAP);

  sh.setColumnWidth(1, 155);
  sh.setColumnWidth(2, 140);
  sh.setColumnWidth(3, 140);
  sh.setColumnWidth(4, 150);
  sh.setColumnWidth(5, 140);
  sh.setColumnWidth(6, 165);
  sh.setColumnWidth(7, 120);
  sh.setColumnWidth(8, 190);
  sh.setColumnWidth(9, 80);
  sh.setColumnWidth(10, 140);
  sh.setColumnWidth(11, 120);
  sh.setColumnWidth(12, 140);
  sh.setColumnWidth(13, 170);
  sh.setColumnWidth(14, 160);
  sh.setColumnWidth(15, 180);
  sh.setColumnWidth(16, 120);
  sh.setColumnWidth(17, 100);
  sh.setColumnWidth(18, 150);
  sh.setColumnWidth(19, 150);
  sh.setColumnWidth(20, 150);
  sh.setColumnWidth(21, 250);
  sh.setColumnWidth(22, 160);
  sh.setColumnWidth(23, 150);

  return 'Список ДОД настроен.';
}


/*******************************************************
 * БЕЗОПАСНОЕ ОФОРМЛЕНИЕ ЗАЯВОК
 *******************************************************/

/**
 * Оформляет вкладку «Заявки».
 * Не очищает и не удаляет строки.
 */
function formatMmuLeadsSafely() {
  const sh = getMainSheet_();

  sh.setFrozenRows(1);

  sh.getRange(1, 1, 1, LEAD_HEADERS.length)
    .setBackground('#12304A')
    .setFontColor('#FFFFFF')
    .setFontWeight('bold')
    .setWrapStrategy(SpreadsheetApp.WrapStrategy.WRAP)
    .setVerticalAlignment('middle');

  sh.setRowHeight(1, 42);

  sh.setColumnWidth(1, 155);
  sh.setColumnWidth(2, 140);
  sh.setColumnWidth(3, 140);
  sh.setColumnWidth(4, 150);
  sh.setColumnWidth(5, 140);
  sh.setColumnWidth(6, 165);
  sh.setColumnWidth(7, 120);
  sh.setColumnWidth(8, 190);
  sh.setColumnWidth(9, 80);
  sh.setColumnWidth(10, 140);
  sh.setColumnWidth(11, 120);
  sh.setColumnWidth(12, 140);
  sh.setColumnWidth(13, 170);
  sh.setColumnWidth(14, 160);
  sh.setColumnWidth(15, 180);
  sh.setColumnWidth(16, 120);
  sh.setColumnWidth(17, 100);
  sh.setColumnWidth(18, 150);
  sh.setColumnWidth(19, 150);
  sh.setColumnWidth(20, 150);
  sh.setColumnWidth(21, 250);
  sh.setColumnWidth(22, 160);
  sh.setColumnWidth(23, 150);

  const lastRow = sh.getLastRow();

  if (lastRow >= 2) {
    sh.getRange(2, 1, lastRow - 1, 23)
      .setVerticalAlignment('middle');

    sh.getRange(2, 1, lastRow - 1, 1)
      .setNumberFormat('dd.MM.yyyy HH:mm');

    sh.getRange(2, 16, lastRow - 1, 1)
      .setNumberFormat('dd.MM.yyyy');

    sh.getRange(2, 17, lastRow - 1, 1)
      .setNumberFormat('HH:mm');
  }

  return 'Оформление заявок завершено.';
}


/*******************************************************
 * ОБЩАЯ НАСТРОЙКА ММУ
 *******************************************************/

/**
 * Запускай вручную только при необходимости
 * обновить панель, список ДОД и оформление.
 *
 * Главная вкладка «Заявки» не очищается.
 */
function setupMmuSafely() {
  setupMmuDashboard();
  setupMmuDodList();
  formatMmuLeadsSafely();

  return 'Настройка ММУ завершена.';
}function testUzTableWrite() {
  const master = getSpreadsheet_();
  const registry = master.getSheetByName('Реестр УЗ');

  if (!registry) {
    throw new Error('Не найдена вкладка «Реестр УЗ».');
  }

  const rows = registry.getDataRange().getValues();
  const testUz = rows.find(row =>
    String(row[0]).trim() === 'ТЕСТ — Школа № 999'
  );

  if (!testUz) {
    throw new Error('Тестовая школа не найдена в реестре.');
  }

  const body = {
    uz_code: String(testUz[1]).trim().toUpperCase()
  };

  const destination = getUzDestination_(body);
  const sh = destination.sheet;
  const testId = 'TEST-' + Date.now();

  sh.appendRow(new Array(23).fill(''));
  const row = sh.getLastRow();

  updateMainRowFromPayload_(sh, row, {
    telegram_id: testId,
    first_name: 'ТЕСТ',
    last_name: 'Проверка записи',
    consent: 'ТЕСТ',
    source: 'ДИАГНОСТИКА',
    uz_code: body.uz_code
  });

  SpreadsheetApp.flush();

  return 'Тестовая строка добавлена. Проверь таблицу: ' +
    destination.uzName;
}