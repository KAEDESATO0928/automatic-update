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
  
  // ステータス
  dataStatus: document.getElementById('data-status'),
  pageStatus: document.getElementById('page-status'),
  processStatus: document.getElementById('process-status'),
  clearData: document.getElementById('clear-data'),
  
  // デバッグ
  debugOutput: document.getElementById('debug-output')
};

// kintone設定
const KINTONE_CONFIG = {
  subdomain: 'because-i.cybozu.com'
};

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
    elements.toggleToken.textContent = type === 'password' ? '👁️' : '🙈';
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
    
    // レコードデータを整形（kintoneのフィールド値形式から単純な値へ）
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
    
    // content_scriptに通知（既にページが開いている場合）
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
 * { "field_code": { "type": "...", "value": "..." } } → { "field_code": "..." }
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
    // content scriptがまだロードされていない場合は無視
    log('Content script not ready', error.message);
  }
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
