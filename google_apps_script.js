/**
 * AI Coach Google Apps Script Webhook (升級版 v2.0)
 * 支援功能：
 * 1. 賽事實績智慧插入 (半馬/全馬分區)
 * 2. 訓練課表多列多欄批次寫入 (set_range)
 * 3. 單一特定儲存格精準修改 (update_cell)
 * 4. 指定資料列刪除 (delete_row)
 * 5. 指定範圍內容清除 (clear_range)
 */

function doGet(e) {
  return ContentService.createTextOutput(JSON.stringify({
    status: "ok",
    version: "2.0",
    message: "AI Coach 跑步賽事與課表智能同步端點正常運作中！"
  })).setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  var lock = LockService.getScriptLock();
  // 最多等待 10 秒取得鎖定，防止並發寫入衝突
  lock.tryLock(10000);
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return ContentService.createTextOutput(JSON.stringify({
        status: "error",
        message: "缺少 POST 內容 (Empty payload)"
      })).setMimeType(ContentService.MimeType.JSON);
    }

    var data = JSON.parse(e.postData.contents);
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheetName = data.sheet_name || "成績";
    var sheet = ss.getSheetByName(sheetName);
    
    if (!sheet) {
      return ContentService.createTextOutput(JSON.stringify({
        status: "error",
        message: "找不到工作表: " + sheetName
      })).setMimeType(ContentService.MimeType.JSON);
    }

    var action = data.action || "";

    // ----------------------------------------------------
    // 功能 1：指定列刪除 (例如刪除測試列)
    // ----------------------------------------------------
    if (action === "delete_row") {
      var rowIdx = data.row_index || data.row;
      if (rowIdx && rowIdx > 0 && rowIdx <= sheet.getLastRow()) {
        sheet.deleteRow(rowIdx);
        return ContentService.createTextOutput(JSON.stringify({
          status: "success",
          message: "✅ 成功刪除第 " + rowIdx + " 列！"
        })).setMimeType(ContentService.MimeType.JSON);
      } else {
        return ContentService.createTextOutput(JSON.stringify({
          status: "error",
          message: "無效的列號: " + rowIdx
        })).setMimeType(ContentService.MimeType.JSON);
      }
    }

    // ----------------------------------------------------
    // 功能 2：單一儲存格更新 (update_cell)
    // 支援 A1 標記 (cell: "C20") 或 (row: 20, col: 3)
    // ----------------------------------------------------
    if (action === "update_cell") {
      var targetRange;
      if (data.cell) {
        targetRange = sheet.getRange(data.cell);
      } else if (data.row && data.col) {
        targetRange = sheet.getRange(data.row, data.col);
      } else {
        return ContentService.createTextOutput(JSON.stringify({
          status: "error",
          message: "缺少儲存格位置參數 (cell 或 row/col)"
        })).setMimeType(ContentService.MimeType.JSON);
      }
      targetRange.setValue(data.value);
      return ContentService.createTextOutput(JSON.stringify({
        status: "success",
        cell: targetRange.getA1Notation(),
        value: data.value,
        message: "✅ 成功更新儲存格 " + targetRange.getA1Notation() + "！"
      })).setMimeType(ContentService.MimeType.JSON);
    }

    // ----------------------------------------------------
    // 功能 3：多列多欄批次寫入 (set_range)
    // 傳入 values 2D 陣列: [[col1, col2, ...], [col1, col2, ...]]
    // ----------------------------------------------------
    if (action === "set_range" || action === "update_range") {
      var values = data.values;
      if (!values || !values.length || !values[0].length) {
        return ContentService.createTextOutput(JSON.stringify({
          status: "error",
          message: "缺少寫入資料 values 2D 陣列"
        })).setMimeType(ContentService.MimeType.JSON);
      }
      var startRow = data.start_row || 1;
      var startCol = data.start_col || 1;
      var numRows = values.length;
      var numCols = values[0].length;
      
      var range = sheet.getRange(startRow, startCol, numRows, numCols);
      range.setValues(values);
      return ContentService.createTextOutput(JSON.stringify({
        status: "success",
        start_row: startRow,
        start_col: startCol,
        rows_count: numRows,
        cols_count: numCols,
        message: "✅ 成功批次寫入 " + numRows + " 列資料至 " + sheetName + "！"
      })).setMimeType(ContentService.MimeType.JSON);
    }

    // ----------------------------------------------------
    // 功能 4：清除特定範圍內容 (clear_range)
    // ----------------------------------------------------
    if (action === "clear_range") {
      if (data.range) {
        sheet.getRange(data.range).clearContent();
        return ContentService.createTextOutput(JSON.stringify({
          status: "success",
          message: "✅ 成功清除範圍 " + data.range + " 內容！"
        })).setMimeType(ContentService.MimeType.JSON);
      }
    }

    // ----------------------------------------------------
    // 預設功能：賽事實績寫入 (向下相容原本的 sync_activity_to_gsheet)
    // ----------------------------------------------------
    var rowData = data.row;
    if (!rowData || !rowData.length) {
      return ContentService.createTextOutput(JSON.stringify({
        status: "error",
        message: "未指定 action 且缺少 row 資料"
      })).setMimeType(ContentService.MimeType.JSON);
    }

    var section = data.section || "half"; // "half" (半馬) 或 "full" (全馬)
    var colValues = sheet.getRange("A1:A50").getValues();
    var targetRow = -1;

    // 半馬智慧定位：尋找「全馬賽事」標題列，插在其上方最後一列
    if (section === "half") {
      for (var i = 0; i < colValues.length; i++) {
        if (colValues[i][0] && colValues[i][0].toString().indexOf("全馬賽事") !== -1) {
          targetRow = i + 1;
          break;
        }
      }
      if (targetRow > 1) {
        var insertAt = targetRow - 1;
        while (insertAt > 1 && (!colValues[insertAt - 1][0] || colValues[insertAt - 1][0].toString().trim() === "")) {
          insertAt--;
        }
        insertAt = insertAt + 1;
        sheet.insertRowBefore(insertAt);
        sheet.getRange(insertAt, 1, 1, rowData.length).setValues([rowData]);
        return ContentService.createTextOutput(JSON.stringify({
          status: "success",
          inserted_row: insertAt,
          message: "✅ 成功插入半馬賽事紀錄！"
        })).setMimeType(ContentService.MimeType.JSON);
      }
    }

    // 預設尾端追加
    sheet.appendRow(rowData);
    return ContentService.createTextOutput(JSON.stringify({
      status: "success",
      inserted_row: sheet.getLastRow(),
      message: "✅ 成功追加資料！"
    })).setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({
      status: "error",
      message: err.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  } finally {
    lock.releaseLock();
  }
}
