/**
 * ДОПОЛНЕНИЕ к уже существующему Apps Script ММУ.
 *
 * ВАЖНО: этот файл сам по себе только добавляет функцию сводки.
 * Чтобы бот мог вызвать её, в существующую doPost(e) добавь
 * обработчик ниже ПОСЛЕ проверки SECRET, но ДО проверки telegram_id:
 *
 * if (body.action === 'leadership_summary') {
 *   return jsonResponse_({
 *     ok: true,
 *     action: 'leadership_summary',
 *     summary: getLeadershipSummary_()
 *   });
 * }
 *
 * Не заменяй весь действующий Apps Script этим файлом.
 * Не меняй SECRET, SHEET_ID и текущий URL развёртывания.
 */

function getLeadershipSummary_() {
  const master = SpreadsheetApp.openById(SHEET_ID);
  const registry = master.getSheetByName('Реестр УЗ');
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

  const main = master.getSheetByName('Заявки');
  const sheets = main ? [main] : [];
  spreadsheetIds.forEach(function(id) {
    try {
      const ss = SpreadsheetApp.openById(id);
      const sh = ss.getSheetByName('Заявки');
      if (sh) sheets.push(sh);
    } catch (err) {
      console.warn('Не удалось прочитать таблицу УЗ ' + id + ': ' + err);
    }
  });

  const seen = {};
  const counts = {
    total: 0, new: 0, in_work: 0, contacted: 0,
    dod_booked: 0, dod_attended: 0, admission: 0, not_interested: 0
  };

  sheets.forEach(function(sh) {
    if (sh.getLastRow() < 2) return;
    sh.getRange(2, 1, sh.getLastRow() - 1, 23).getDisplayValues()
      .forEach(function(row) {
        const id = String(row[4] || '').trim();
        if (!id || seen[id]) return;
        seen[id] = true;
        counts.total++;

        const dod = String(row[17] || '').trim();
        const status = String(row[18] || '').trim();
        if (status === 'Новая') counts.new++;
        if (status === 'В работе') counts.in_work++;
        if (status === 'Связались') counts.contacted++;
        if (status === 'Поступление') counts.admission++;
        if (status === 'Не заинтересован' || status === 'Не заинтересованы') counts.not_interested++;
        if (dod === 'Записан на ДОД') counts.dod_booked++;
        if (dod === 'Пришел на ДОД' || dod === 'Пришёл на ДОД') counts.dod_attended++;
      });
  });

  return counts;
}
