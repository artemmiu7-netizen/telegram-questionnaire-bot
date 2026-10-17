/**
 * ММУ — менеджеры, распределение УЗ и персональные ссылки.
 *
 * Безопасно: существующие заявки не удаляет и не очищает.
 * Вставить отдельным файлом в проект Apps Script главной таблицы.
 *
 * Структура:
 * Менеджеры: A Имя, B Telegram ID, C Статус, D Всего анкет,
 *            E Дата добавления, F Код менеджера
 * Распределение УЗ: A Имя, B Telegram ID, C Название УЗ, D Код УЗ,
 *                   E Ссылка, F Анкет по ссылке, G Статус, H Код менеджера
 */

const MANAGERS_SHEET_NAME = 'Менеджеры';
const UZ_ASSIGNMENTS_SHEET_NAME = 'Распределение УЗ';
const MMU_BOT_USERNAME = 'UniversityQuestionnaireMMUbot';

function setupManagerSystem() {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  const managers = getOrCreateSheet_(ss, MANAGERS_SHEET_NAME);
  const assignments = getOrCreateSheet_(ss, UZ_ASSIGNMENTS_SHEET_NAME);

  ensureManagerHeaders_(managers, [
    'Имя менеджера', 'Telegram ID', 'Статус',
    'Всего анкет', 'Дата добавления', 'Код менеджера'
  ]);
  ensureManagerHeaders_(assignments, [
    'Имя менеджера', 'Telegram ID менеджера', 'Название УЗ',
    'Код УЗ', 'Ссылка на анкету', 'Анкет по ссылке',
    'Статус', 'Код менеджера'
  ]);

  [managers, assignments].forEach(function(sh) {
    sh.setFrozenRows(1);
    sh.getRange(1, 1, 1, sh.getLastColumn())
      .setFontWeight('bold')
      .setWrap(true)
      .setBackground('#12304A')
      .setFontColor('#FFFFFF');
    sh.autoResizeColumns(1, sh.getLastColumn());
  });

  return 'Вкладки менеджеров проверены. Существующие строки сохранены.';
}

function refreshManagerLinks() {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  const managers = ss.getSheetByName(MANAGERS_SHEET_NAME);
  const assignments = ss.getSheetByName(UZ_ASSIGNMENTS_SHEET_NAME);
  const registry = ss.getSheetByName(UZ_REGISTRY_NAME || 'Реестр УЗ');

  if (!managers || !assignments || !registry) {
    throw new Error('Сначала запусти setupManagerSystem() и проверь вкладку «Реестр УЗ».');
  }

  ensureManagerHeaders_(managers, [
    'Имя менеджера', 'Telegram ID', 'Статус',
    'Всего анкет', 'Дата добавления', 'Код менеджера'
  ]);
  ensureManagerHeaders_(assignments, [
    'Имя менеджера', 'Telegram ID менеджера', 'Название УЗ',
    'Код УЗ', 'Ссылка на анкету', 'Анкет по ссылке',
    'Статус', 'Код менеджера'
  ]);

  const managerRows = managers.getLastRow() > 1
    ? managers.getRange(2, 1, managers.getLastRow() - 1, 6).getValues()
    : [];
  const managerByName = {};
  const managerJson = {};

  managerRows.forEach(function(row, i) {
    const name = String(row[0] || '').trim();
    const telegramId = String(row[1] || '').trim();
    const status = String(row[2] || 'Активен').trim();
    let code = String(row[5] || '').trim().toUpperCase();

    if (!name || !telegramId) return;
    if (!code) {
      code = 'MGR' + String(i + 1).padStart(3, '0');
      managers.getRange(i + 2, 6).setValue(code);
    }
    managerByName[name.toLowerCase()] = {
      name: name, telegramId: telegramId, status: status, code: code
    };
    if (status.toLowerCase() !== 'неактивен') {
      managerJson[code] = telegramId;
    }
  });

  const uzRows = registry.getLastRow() > 1
    ? registry.getRange(2, 1, registry.getLastRow() - 1, 7).getValues()
    : [];
  const uzByName = {};
  uzRows.forEach(function(row) {
    uzByName[String(row[0] || '').trim().toLowerCase()] = {
      name: String(row[0] || '').trim(),
      code: String(row[1] || '').trim().toUpperCase(),
      spreadsheetId: String(row[2] || '').trim(),
      status: String(row[6] || 'Создана').trim()
    };
  });

  const last = assignments.getLastRow();
  const rows = last > 1
    ? assignments.getRange(2, 1, last - 1, 8).getValues()
    : [];
  rows.forEach(function(row, i) {
    const sheetRow = i + 2;
    const managerName = String(row[0] || '').trim();
    const manager = managerByName[managerName.toLowerCase()];
    const uzName = String(row[2] || '').trim();
    const uzCodeCell = String(row[3] || '').trim().toUpperCase();
    const uz = uzRows.find(function(item) {
      return String(item[1] || '').trim().toUpperCase() === uzCodeCell ||
        String(item[0] || '').trim().toLowerCase() === uzName.toLowerCase();
    });

    if (!manager || !uz) {
      assignments.getRange(sheetRow, 7).setValue('Проверить менеджера/УЗ');
      return;
    }

    const uzCode = String(uz[1] || '').trim().toUpperCase();
    if (!uzCode) {
      assignments.getRange(sheetRow, 7).setValue('Нет кода УЗ');
      return;
    }

    const link = 'https://t.me/' + MMU_BOT_USERNAME +
      '?start=uz_' + encodeURIComponent(uzCode) +
      '_mgr_' + encodeURIComponent(manager.code);

    assignments.getRange(sheetRow, 2).setValue(manager.telegramId);
    assignments.getRange(sheetRow, 3).setValue(String(uz[0] || '').trim());
    assignments.getRange(sheetRow, 4).setValue(uzCode);
    assignments.getRange(sheetRow, 5).setValue(link);
    assignments.getRange(sheetRow, 7).setValue(
      manager.status.toLowerCase() === 'неактивен' ? 'Неактивно' : 'Активно'
    );
    assignments.getRange(sheetRow, 8).setValue(manager.code);
    assignments.getRange(sheetRow, 5).setShowHyperlink(true);
  });

  managers.getRange(1, 6).setNote('Код используется в персональных ссылках бота. Не меняй вручную без необходимости.');
  assignments.getRange(1, 5).setNote('Персональная ссылка: код УЗ + код менеджера.');
  assignments.getRange(1, 8).setNote('Автоматически присваиваемый код менеджера.');

  return 'Ссылки обновлены. JSON для Deployka: ' + JSON.stringify(managerJson);
}

function getOrCreateSheet_(ss, name) {
  return ss.getSheetByName(name) || ss.insertSheet(name);
}

function ensureManagerHeaders_(sh, headers) {
  const current = sh.getLastColumn() > 0
    ? sh.getRange(1, 1, 1, Math.max(sh.getLastColumn(), headers.length)).getValues()[0]
    : [];
  headers.forEach(function(header, i) {
    if (!current[i]) sh.getRange(1, i + 1).setValue(header);
  });
}
