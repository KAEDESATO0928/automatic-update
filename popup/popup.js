/**
 * Popup Script for Carrier Entry Automation
 * ポップアップUIのロジック
 */

// DOM要素の取得
const elements = {
  // 設定
  appId: document.getElementById('app-id'),
  apiToken: document.getElementById('api-token'),
  toggleToken: document.getElementById('toggle-token'),
  saveSettings: document.getElementById('save-settings'),
  settingsStatus: document.getElementById('settings-status'),

  // 実行
  recordId: document.getElementById('record-id'),
  fetchData: document.getElementById('fetch-data'),
  executionStatus: document.getElementById('execution-status'),

  // 進捗表示
  progressSection: document.getElementById('progress-section'),
  progressPage: document.getElementById('progress-page'),
  progressCount: document.getElementById('progress-count'),
  progressFill: document.getElementById('progress-fill'),
  fieldStatusList: document.getElementById('field-status-list'),

  // ステータス
  dataStatus: document.getElementById('data-status'),
  pageStatus: document.getElementById('page-status'),
  processStatus: document.getElementById('process-status'),
  clearData: document.getElementById('clear-data'),

  // ログ
  logList: document.getElementById('log-list'),
  refreshLogs: document.getElementById('refresh-logs'),
  exportLogs: document.getElementById('export-logs'),
  clearLogs: document.getElementById('clear-logs'),

  // モーダル
  logModal: document.getElementById('log-modal'),
  logDetails: document.getElementById('log-details'),
  closeModal: document.getElementById('close-modal'),

  // デバッグ
  debugOutput: document.getElementById('debug-output')
};

// kintone設定
const KINTONE_CONFIG = {
  subdomain: 'because-i.cybozu.com'
};

// 現在の処理状態
let currentProcessing = {
  totalFields: 0,
  processedFields: 0,
  pageName: ''
};

// ログデータのキャッシュ
let logsCache = [];

/**
 * 初期化処理
 */
async function initialize() {
  // 保存済み設定を読み込み
  const settings = await chrome.storage.local.get(['appId', 'apiToken', 'kintoneData']);

  if (settings.appId) {
    elements.appId.value = settings.appId;
  }
  if (settings.apiToken) {
    elements.apiToken.value = settings.apiToken;
  }

  // ステータス更新
  updateStatusDisplay(settings.kintoneData);

  // イベントリスナー設定
  setupEventListeners();

  // メッセージリスナー設定
  setupMessageListener();

  // ログを読み込み
  await loadLogs();

  log('Popup initialized');
}

/**
 * イベントリスナーの設定
 */
function setupEventListeners() {
  // APIトークン表示切替
  elements.toggleToken.addEventListener('click', () => {
    const type = elements.apiToken.type === 'password' ? 'text' : 'password';
    elements.apiToken.type = type;
    elements.toggleToken.textContent = type === 'password' ? 'Show' : 'Hide';
  });

  // 設定保存
  elements.saveSettings.addEventListener('click', saveSettings);

  // データ取得&開始
  elements.fetchData.addEventListener('click', fetchAndStart);

  // データクリア
  elements.clearData.addEventListener('click', clearData);

  // Enterキーでデータ取得
  elements.recordId.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      fetchAndStart();
    }
  });

  // ログ操作
  elements.refreshLogs.addEventListener('click', loadLogs);
  elements.exportLogs.addEventListener('click', exportLogs);
  elements.clearLogs.addEventListener('click', clearAllLogs);

  // モーダル
  elements.closeModal.addEventListener('click', closeModal);
  elements.logModal.addEventListener('click', (e) => {
    if (e.target === elements.logModal) {
      closeModal();
    }
  });
}

/**
 * メッセージリスナーの設定
 */
function setupMessageListener() {
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    switch (message.action) {
      case 'PROCESSING_STARTED':
        handleProcessingStarted(message.data);
        break;

      case 'FIELD_PROCESSED':
        handleFieldProcessed(message.data);
        break;

      case 'FIELD_ERROR':
        handleFieldError(message.data);
        break;

      case 'PROCESSING_COMPLETED':
        handleProcessingCompleted(message.data);
        break;

      case 'PROCESSING_ERROR':
        handleProcessingError(message.data);
        break;
    }
  });
}

/**
 * 処理開始ハンドラ
 */
function handleProcessingStarted(data) {
  currentProcessing = {
    totalFields: data.totalFields || 0,
    processedFields: 0,
    pageName: data.pageName || ''
  };

  // 進捗セクションを表示
  elements.progressSection.classList.remove('hidden');
  elements.progressPage.textContent = data.pageName;
  elements.progressCount.textContent = `0/${data.totalFields}`;
  elements.progressFill.style.width = '0%';
  elements.fieldStatusList.innerHTML = '';

  // ステータス更新
  elements.pageStatus.textContent = data.pageName;
  elements.processStatus.textContent = '処理中...';
  elements.processStatus.classList.add('processing');

  log('Processing started', data);
}

/**
 * フィールド処理完了ハンドラ
 */
function handleFieldProcessed(data) {
  const field = data.field;
  currentProcessing.processedFields++;

  // 進捗更新
  const progress = (currentProcessing.processedFields / currentProcessing.totalFields) * 100;
  elements.progressFill.style.width = `${progress}%`;
  elements.progressCount.textContent = `${currentProcessing.processedFields}/${currentProcessing.totalFields}`;

  // フィールドステータス追加
  const item = document.createElement('div');
  item.className = `field-status-item ${field.status}`;
  item.innerHTML = `
    <span>${field.description || field.kintoneField}</span>
    <span>${field.status === 'success' ? 'OK' : 'NG'}</span>
  `;
  elements.fieldStatusList.appendChild(item);

  // スクロール
  elements.fieldStatusList.scrollTop = elements.fieldStatusList.scrollHeight;
}

/**
 * フィールドエラーハンドラ
 */
function handleFieldError(data) {
  const { field, error } = data;

  showStatus(elements.executionStatus, 'warning',
    `${field.description || field.kintoneField}: ${error.message}`
  );
}

/**
 * 処理完了ハンドラ
 */
function handleProcessingCompleted(data) {
  const { logEntry } = data;

  // 進捗を100%に
  elements.progressFill.style.width = '100%';

  // ステータス更新
  elements.processStatus.textContent = getStatusLabel(logEntry.status);
  elements.processStatus.classList.remove('processing');

  // サマリー表示
  const successCount = logEntry.fields.filter(f => f.status === 'success').length;
  const totalCount = logEntry.fields.length;

  const statusType = logEntry.status === 'success' ? 'success' :
                     logEntry.status === 'partial' ? 'warning' : 'error';

  showStatus(elements.executionStatus, statusType,
    `処理完了: ${successCount}/${totalCount} フィールド成功 (${logEntry.duration}ms)`
  );

  // 少し待ってから進捗セクションを非表示
  setTimeout(() => {
    elements.progressSection.classList.add('hidden');
  }, 3000);

  // ログリストを更新
  loadLogs();

  log('Processing completed', logEntry);
}

/**
 * 処理エラーハンドラ
 */
function handleProcessingError(data) {
  const { error } = data;

  elements.processStatus.textContent = 'エラー';
  elements.processStatus.classList.remove('processing');

  showStatus(elements.executionStatus, 'error', `エラー: ${error.message}`);

  log('Processing error', error);
}

/**
 * 設定を保存
 */
async function saveSettings() {
  const appId = elements.appId.value.trim();
  const apiToken = elements.apiToken.value.trim();

  if (!appId || !apiToken) {
    showStatus(elements.settingsStatus, 'error', 'アプリIDとAPIトークンを入力してください');
    return;
  }

  try {
    await chrome.storage.local.set({ appId, apiToken });
    showStatus(elements.settingsStatus, 'success', '設定を保存しました');
    log('Settings saved', { appId });
  } catch (error) {
    showStatus(elements.settingsStatus, 'error', `保存エラー: ${error.message}`);
    log('Settings save error', error);
  }
}

/**
 * kintoneからデータを取得して処理開始
 */
async function fetchAndStart() {
  const recordId = elements.recordId.value.trim();

  if (!recordId) {
    showStatus(elements.executionStatus, 'error', 'レコード番号を入力してください');
    return;
  }

  const settings = await chrome.storage.local.get(['appId', 'apiToken']);

  if (!settings.appId || !settings.apiToken) {
    showStatus(elements.executionStatus, 'error', '先にAPI設定を保存してください');
    return;
  }

  elements.fetchData.disabled = true;
  elements.fetchData.textContent = '取得中...';
  showStatus(elements.executionStatus, 'info', 'kintoneからデータを取得中...');

  try {
    // kintone REST API呼び出し
    const url = `https://${KINTONE_CONFIG.subdomain}/k/v1/record.json?app=${settings.appId}&id=${recordId}`;

    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'X-Cybozu-API-Token': settings.apiToken
      }
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.message || `HTTP ${response.status}`);
    }

    const data = await response.json();

    // レコードデータを整形
    const kintoneData = flattenKintoneRecord(data.record);
    kintoneData._recordId = recordId;
    kintoneData._fetchedAt = new Date().toISOString();

    // chrome.storage.localに保存
    await chrome.storage.local.set({
      kintoneData,
      automationActive: true
    });

    // ステータス更新
    updateStatusDisplay(kintoneData);
    showStatus(elements.executionStatus, 'success', 'データ取得完了！対象サイトを開いてください');

    log('Data fetched successfully', kintoneData);

    // content_scriptに通知
    notifyContentScript('DATA_READY', kintoneData);

  } catch (error) {
    showStatus(elements.executionStatus, 'error', `取得エラー: ${error.message}`);
    log('Fetch error', error);
  } finally {
    elements.fetchData.disabled = false;
    elements.fetchData.textContent = 'データ取得 & 開始';
  }
}

/**
 * kintoneレコードをフラット化
 */
function flattenKintoneRecord(record) {
  const result = {};

  for (const [key, field] of Object.entries(record)) {
    if (field && typeof field === 'object' && 'value' in field) {
      result[key] = field.value;
    } else {
      result[key] = field;
    }
  }

  return result;
}

/**
 * データをクリア
 */
async function clearData() {
  if (!confirm('保存されているkintoneデータをクリアしますか？')) {
    return;
  }

  try {
    await chrome.storage.local.remove(['kintoneData', 'automationActive']);
    updateStatusDisplay(null);
    showStatus(elements.executionStatus, 'info', 'データをクリアしました');
    log('Data cleared');

    // content_scriptに通知
    notifyContentScript('DATA_CLEARED', null);
  } catch (error) {
    showStatus(elements.executionStatus, 'error', `クリアエラー: ${error.message}`);
  }
}

/**
 * ログを読み込み
 */
async function loadLogs() {
  try {
    const response = await chrome.runtime.sendMessage({
      action: 'GET_LOGS',
      limit: 20
    });

    if (response.success) {
      logsCache = response.logs;
      renderLogList(response.logs);
    }
  } catch (error) {
    log('Failed to load logs', error);
  }
}

/**
 * ログリストを描画
 */
function renderLogList(logs) {
  if (!logs || logs.length === 0) {
    elements.logList.innerHTML = '<p class="no-logs">ログがありません</p>';
    return;
  }

  elements.logList.innerHTML = logs.map(entry => `
    <div class="log-entry ${entry.status}" data-id="${entry.id}">
      <div class="log-entry-header">
        <span class="log-entry-page">${entry.pageName || 'Unknown'}</span>
        <span class="log-entry-status ${entry.status}">${getStatusLabel(entry.status)}</span>
      </div>
      <div class="log-entry-footer">
        <span>${formatTimestamp(entry.timestamp)}</span>
        <span>ID: ${entry.recordId || '-'}</span>
      </div>
    </div>
  `).join('');

  // クリックイベントを追加
  elements.logList.querySelectorAll('.log-entry').forEach(el => {
    el.addEventListener('click', () => {
      const logEntry = logsCache.find(l => l.id === el.dataset.id);
      if (logEntry) {
        showLogDetail(logEntry);
      }
    });
  });
}

/**
 * ログ詳細を表示
 */
function showLogDetail(logEntry) {
  const successCount = logEntry.fields ? logEntry.fields.filter(f => f.status === 'success').length : 0;
  const failedCount = logEntry.fields ? logEntry.fields.filter(f => f.status === 'failed').length : 0;

  let html = `
    <p><strong>ページ:</strong> ${logEntry.pageName || '-'}</p>
    <p><strong>レコードID:</strong> ${logEntry.recordId || '-'}</p>
    <p><strong>日時:</strong> ${formatTimestamp(logEntry.timestamp)}</p>
    <p><strong>処理時間:</strong> ${logEntry.duration}ms</p>
    <p><strong>結果:</strong> ${getStatusLabel(logEntry.status)} (成功: ${successCount}, 失敗: ${failedCount})</p>
  `;

  if (logEntry.fields && logEntry.fields.length > 0) {
    html += '<h4>フィールド結果</h4><ul>';
    html += logEntry.fields.map(f => `
      <li class="${f.status}">
        ${f.description || f.kintoneField}: ${f.status === 'success' ? 'OK' : 'NG'}
        ${f.error ? `<small>${f.error.message}</small>` : ''}
      </li>
    `).join('');
    html += '</ul>';
  }

  if (logEntry.errors && logEntry.errors.length > 0) {
    html += '<h4>エラー詳細</h4><ul>';
    html += logEntry.errors.map(e => `
      <li class="failed">
        <strong>${e.type || 'ERROR'}</strong>: ${e.message}
        ${e.selector ? `<small>セレクタ: ${e.selector}</small>` : ''}
      </li>
    `).join('');
    html += '</ul>';
  }

  elements.logDetails.innerHTML = html;
  elements.logModal.classList.remove('hidden');
}

/**
 * モーダルを閉じる
 */
function closeModal() {
  elements.logModal.classList.add('hidden');
}

/**
 * ログをエクスポート
 */
async function exportLogs() {
  try {
    const response = await chrome.runtime.sendMessage({
      action: 'EXPORT_LOGS',
      format: 'json'
    });

    if (response.success) {
      // ダウンロード
      const blob = new Blob([response.data], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `carrier-entry-logs-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);

      showStatus(elements.executionStatus, 'success', 'ログをエクスポートしました');
    }
  } catch (error) {
    showStatus(elements.executionStatus, 'error', `エクスポート失敗: ${error.message}`);
  }
}

/**
 * 全ログをクリア
 */
async function clearAllLogs() {
  if (!confirm('すべてのログを削除しますか？')) {
    return;
  }

  try {
    await chrome.runtime.sendMessage({ action: 'CLEAR_LOGS' });
    logsCache = [];
    renderLogList([]);
    showStatus(elements.executionStatus, 'info', 'ログをクリアしました');
  } catch (error) {
    showStatus(elements.executionStatus, 'error', `クリア失敗: ${error.message}`);
  }
}

/**
 * ステータス表示を更新
 */
function updateStatusDisplay(kintoneData) {
  if (kintoneData) {
    elements.dataStatus.textContent = `取得済み (ID: ${kintoneData._recordId || '-'})`;
    elements.dataStatus.style.color = '#27ae60';
    elements.processStatus.textContent = '準備完了';
  } else {
    elements.dataStatus.textContent = '未取得';
    elements.dataStatus.style.color = '#e74c3c';
    elements.processStatus.textContent = '待機中';
  }
}

/**
 * ステータスメッセージを表示
 */
function showStatus(element, type, message) {
  element.className = `status ${type}`;
  element.textContent = message;

  // 成功メッセージは3秒後に消す
  if (type === 'success') {
    setTimeout(() => {
      element.className = 'status';
    }, 3000);
  }
}

/**
 * Content Scriptに通知
 */
async function notifyContentScript(action, data) {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (tab && tab.url && tab.url.includes('so-net.ne.jp')) {
      await chrome.tabs.sendMessage(tab.id, { action, data });
      log('Message sent to content script', { action });
    }
  } catch (error) {
    log('Content script not ready', error.message);
  }
}

/**
 * ステータスラベルを取得
 */
function getStatusLabel(status) {
  switch (status) {
    case 'success': return '成功';
    case 'partial': return '一部失敗';
    case 'failed': return '失敗';
    default: return status;
  }
}

/**
 * タイムスタンプをフォーマット
 */
function formatTimestamp(timestamp) {
  if (!timestamp) return '-';
  const date = new Date(timestamp);
  return date.toLocaleString('ja-JP', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
}

/**
 * デバッグログ
 */
function log(message, data = null) {
  const timestamp = new Date().toLocaleTimeString();
  const logEntry = `[${timestamp}] ${message}`;

  console.log(logEntry, data);

  if (elements.debugOutput) {
    const dataStr = data ? `\n${JSON.stringify(data, null, 2)}` : '';
    elements.debugOutput.textContent = logEntry + dataStr + '\n' + elements.debugOutput.textContent;
  }
}

// 初期化実行
document.addEventListener('DOMContentLoaded', initialize);
