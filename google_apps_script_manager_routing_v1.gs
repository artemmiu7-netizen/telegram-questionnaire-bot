/**
 * MMU — безопасная маршрутизация заявок в индивидуальные таблицы менеджеров.
 *
 * ДОБАВЛЯЕТСЯ отдельным .gs-файлом к действующему расширенному Apps Script.
 * Не заменяет doPost, реестр УЗ, ДОД, статистику и существующие функции.
 *
 * Ожидаемые листы главной таблицы:
 *   Заявки, Менеджеры, Реестр УЗ
 *
 * В листе «Менеджеры» используются заголовки:
 *   Код менеджера, Статус, Google email,
 *   ID таблицы менеджера, Ссылка на таблицу менеджера
 *
 * В «Заявки» — 25 колонок в порядке MMU_LEAD_HEADERS ниже.
 * Если заголовки отличаются, функция копирует фактическую строку целиком,
 * не переставляя и не очищая столбцы.
 */

const MMU_MGR_SHEET_NAME_V1 = 'Менеджеры';
const MMU_UZ_REGISTRY_SHEET_NAME_V1 = 'Реестр УЗ';
const MMU_MAIN_LEADS_SHEET_NAME_V1 = 'Заявки';
const MMU_MANAGER_BOOK_ID_HEADER_V1 = 'ID таблицы менеджера';
const MMU_MANAGER_BOOK_URL_HEADER_V1 = 'Ссылка на таблицу менеджера';
const MMU_MANAGER_CODE_HEADER_V1 = 'Код менеджера';
const MMU_MANAGER_EMAIL_HEADER_V1 = 'Google email';
const MMU_MANAGER_STATUS_HEADER_V1 = 'Статус';
const MMU_TELEGRAM_ID_HEADER_V1 = 'Telegram ID';
const MMU_UZ_CODE_HEADER_V1 = 'Код УЗ';
const MMU_UZ_NAME_HEADER_V1 = 'Название УЗ';

/**
 * Вызывать из doPost после обновления главной строки и SpreadsheetApp.flush().
 * Возвращает {ok:true,...} либо {ok:false,error:...}.
 */
function mmuSyncLeadToManagerBookV1_(masterSs, mainSheet, mainRow, body) {
  const managerCode = String(body.manager_code || '').trim().toUpperCase();
  if (!managerCode) {
    return { ok: true, skipped: true, reason: 'manager_code_empty' };
  }

  const managerSheet = masterSs.getSheetByName(MMU_MGR_SHEET_NAME_V1);
  if (!managerSheet) throw new Error('Не найден лист «Менеджеры».');

  const managerHeaders = mmuGetHeaderMapV1_(managerSheet);
  const codeCol = managerHeaders[MMU_MANAGER_CODE_HEADER_V1];
  if (!codeCol) throw new Error('В листе «Менеджеры» нет столбца «Код менеджера».');

  const managerRow = mmuFindRowByValueV1_(managerSheet, codeCol, managerCode);
  if (managerRow < 2) throw new Error('Не найден активный менеджер: ' + managerCode);

  const statusCol = managerHeaders[MMU_MANAGER_STATUS_HEADER_V1];
  if (statusCol) {
    const status = String(managerSheet.getRange(managerRow, statusCol).getDisplayValue() || '')
      .trim().toLowerCase();
    if (status && !['активен', 'активна', 'active', 'да', 'работает'].includes(status)) {
      throw new Error('Менеджер ' + managerCode + ' не активен.');
    }
  }

  const emailCol = managerHeaders[MMU_MANAGER_EMAIL_HEADER_V1];
  const email = emailCol
    ? String(managerSheet.getRange(managerRow, emailCol).getDisplayValue() || '').trim()
    : '';

  const bookIdCol = mmuEnsureHeaderV1_(managerSheet, MMU_MANAGER_BOOK_ID_HEADER_V1);
  const bookUrlCol = mmuEnsureHeaderV1_(managerSheet, MMU_MANAGER_BOOK_URL_HEADER_V1);

  let managerBookId = String(managerSheet.getRange(managerRow, bookIdCol).getDisplayValue() || '').trim();
  let managerBook;

  if (managerBookId) {
    managerBook = SpreadsheetApp.openById(managerBookId);
  } else {
    const managerNameCol = managerHeaders['Имя менеджера'];
    const managerName = managerNameCol
      ? String(managerSheet.getRange(managerRow, managerNameCol).getDisplayValue() || '').trim()
      : managerCode;
    managerBook = SpreadsheetApp.create('ММУ — заявки менеджера ' + (managerName || managerCode));
    managerBookId = managerBook.getId();

    managerSheet.getRange(managerRow, bookIdCol).setValue(managerBookId);
    managerSheet.getRange(managerRow, bookUrlCol).setValue(managerBook.getUrl());

  }

  // Повторно проверяем доступ: это также покрывает случай, когда email
  // менеджера добавили уже после создания его таблицы.
  if (email) {
    try {
      managerBook.addEditor(email);
    } catch (shareError) {
      console.error('MMU_MANAGER_SHARE_WARNING ' + managerCode + ': ' + shareError);
    }
  }

  const mainLastColumn = mainSheet.getLastColumn();
  if (mainLastColumn < 1 || mainRow < 2) {
    throw new Error('Некорректная строка заявки для копирования менеджеру.');
  }

  const leadValues = mainSheet.getRange(mainRow, 1, 1, mainLastColumn).getValues()[0];
  const mainHeaders = mainSheet.getRange(1, 1, 1, mainLastColumn).getDisplayValues()[0];
  const uzCodeCol = mmuFindHeaderIndexV1_(mainHeaders, MMU_UZ_CODE_HEADER_V1);
  const uzName = mmuResolveUzNameV1_(masterSs, uzCodeCol > -1 ? leadValues[uzCodeCol] : body.uz_code);
  const rawUzCode = uzCodeCol > -1 ? leadValues[uzCodeCol] : body.uz_code;
  const tabName = mmuBuildUzTabNameV1_(rawUzCode, uzName);

  let targetSheet = managerBook.getSheetByName(tabName);
  if (!targetSheet) {
    const defaultSheets = managerBook.getSheets();
    if (defaultSheets.length === 1 &&
        defaultSheets[0].getLastRow() === 0 &&
        defaultSheets[0].getLastColumn() === 0) {
      defaultSheets[0].setName(tabName);
      targetSheet = defaultSheets[0];
    } else {
      targetSheet = managerBook.insertSheet(tabName);
    }
    targetSheet.getRange(1, 1, 1, mainLastColumn).setValues([mainHeaders]);
    targetSheet.setFrozenRows(1);
    targetSheet.getRange(1, 1, 1, mainLastColumn)
      .setFontWeight('bold')
      .setWrap(true);
  } else {
    mmuEnsureManagerTabHeadersV1_(targetSheet, mainHeaders);
  }

  const telegramIdIndex = mmuFindHeaderIndexV1_(mainHeaders, MMU_TELEGRAM_ID_HEADER_V1);
  if (telegramIdIndex < 0) throw new Error('В главном листе нет столбца «Telegram ID».');
  const telegramId = String(leadValues[telegramIdIndex] || body.telegram_id || '').trim();
  if (!telegramId) throw new Error('У заявки отсутствует Telegram ID.');

  const targetTelegramCol = telegramIdIndex + 1;
  let targetRow = mmuFindRowByValueV1_(targetSheet, targetTelegramCol, telegramId);
  if (targetRow < 2) targetRow = Math.max(targetSheet.getLastRow() + 1, 2);

  targetSheet.getRange(targetRow, 1, 1, mainLastColumn).setValues([leadValues]);
  targetSheet.getRange(targetRow, 1, 1, mainLastColumn)
    .setVerticalAlignment('top')
    .setWrap(true);

  return {
    ok: true,
    manager_code: managerCode,
    manager_book_id: managerBookId,
    manager_book_url: managerBook.getUrl(),
    uz_code: String(rawUzCode || ''),
    uz_tab: tabName,
    manager_row: targetRow
  };
}

function mmuGetHeaderMapV1_(sheet) {
  const lastCol = Math.max(sheet.getLastColumn(), 1);
  const headers = sheet.getRange(1, 1, 1, lastCol).getDisplayValues()[0];
  const map = {};
  headers.forEach((value, index) => {
    const key = String(value || '').trim();
    if (key) map[key] = index + 1;
  });
  return map;
}

function mmuEnsureHeaderV1_(sheet, header) {
  const map = mmuGetHeaderMapV1_(sheet);
  if (map[header]) return map[header];
  const nextCol = Math.max(sheet.getLastColumn(), 0) + 1;
  sheet.getRange(1, nextCol).setValue(header);
  return nextCol;
}

function mmuFindHeaderIndexV1_(headers, wanted) {
  const target = String(wanted || '').trim().toLowerCase();
  return headers.findIndex(value => String(value || '').trim().toLowerCase() === target);
}

function mmuFindRowByValueV1_(sheet, column, value) {
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return -1;
  const wanted = String(value || '').trim().toLowerCase();
  const values = sheet.getRange(2, column, lastRow - 1, 1).getDisplayValues();
  for (let i = 0; i < values.length; i++) {
    if (String(values[i][0] || '').trim().toLowerCase() === wanted) return i + 2;
  }
  return -1;
}

function mmuResolveUzNameV1_(masterSs, uzCode) {
  const code = String(uzCode || '').trim().toUpperCase();
  if (!code) return 'Без УЗ';
  const registry = masterSs.getSheetByName(MMU_UZ_REGISTRY_SHEET_NAME_V1);
  if (!registry || registry.getLastRow() < 2) return code;

  const headers = mmuGetHeaderMapV1_(registry);
  const codeCol = headers[MMU_UZ_CODE_HEADER_V1];
  const nameCol = headers[MMU_UZ_NAME_HEADER_V1];
  if (!codeCol || !nameCol) return code;

  const row = mmuFindRowByValueV1_(registry, codeCol, code);
  return row > 1
    ? String(registry.getRange(row, nameCol).getDisplayValue() || code).trim()
    : code;
}

function mmuBuildUzTabNameV1_(uzCode, uzName) {
  const code = String(uzCode || '').trim() || 'NO_UZ';
  const name = String(uzName || '').trim();
  let tab = (code + ' — ' + name).replace(/[\\/?*\[\]:]/g, ' ').replace(/\s+/g, ' ').trim();
  if (tab.length > 95) tab = tab.slice(0, 95).trim();
  return tab || 'Без УЗ';
}

function mmuEnsureManagerTabHeadersV1_(sheet, sourceHeaders) {
  if (sheet.getLastRow() === 0 || sheet.getLastColumn() === 0) {
    sheet.getRange(1, 1, 1, sourceHeaders.length).setValues([sourceHeaders]);
    sheet.setFrozenRows(1);
    return;
  }
  const currentWidth = Math.max(sheet.getLastColumn(), sourceHeaders.length);
  const currentHeaders = sheet.getRange(1, 1, 1, currentWidth).getDisplayValues()[0];
  const hasHeader = currentHeaders.some(value => String(value || '').trim());
  if (!hasHeader) {
    sheet.getRange(1, 1, 1, sourceHeaders.length).setValues([sourceHeaders]);
    sheet.setFrozenRows(1);
  }
}
