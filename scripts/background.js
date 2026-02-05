/**
 * Background Service Worker for Carrier Entry Automation
 * ページ遷移の監視とメッセージング、ログ管理
 */

// LogManagerをインポート
importScripts('log-manager.js');

// 拡張機能インストール時
chrome.runtime.onInstalled.addListener((details) => {
  console.log('[CarrierEntry] Extension installed', details.reason);

  // 初期設定
  chrome.storage.local.set({
    automationActive: false,
    kintoneData: null
  });
});

// タブ更新時（ページ遷移検知）
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (changeInfo.status !== 'complete') return;
  if (!tab.url || !tab.url.includes('so-net.ne.jp')) return;

  console.log('[CarrierEntry] Target page loaded', tab.url);

  const { automationActive, kintoneData } = await chrome.storage.local.get([
    'automationActive',
    'kintoneData'
  ]);

  if (automationActive && kintoneData) {
    try {
      await chrome.tabs.sendMessage(tabId, {
        action: 'PAGE_LOADED',
        url: tab.url
      });
      console.log('[CarrierEntry] Notified content script');
    } catch (error) {
      console.log('[CarrierEntry] Content script not ready, will retry');
    }
  }
});

// メッセージハンドラ
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log('[CarrierEntry] Message received in background', message.action);

  // 非同期処理が必要なメッセージ
  const asyncActions = [
    'PROCESSING_COMPLETED',
    'GET_LOGS',
    'EXPORT_LOGS',
    'CLEAR_LOGS',
    'GET_LOG_STATS'
  ];

  if (asyncActions.includes(message.action)) {
    handleAsyncMessage(message, sender, sendResponse);
    return true; // 非同期レスポンスのため
  }

  // 同期処理
  switch (message.action) {
    case 'LOG':
      console.log(`[CarrierEntry:Content] ${message.message}`, message.data);
      break;

    case 'PROCESSING_STARTED':
      console.log('[CarrierEntry] Processing started', message.data);
      // Popupに中継（開いている場合）
      broadcastToPopup(message);
      break;

    case 'FIELD_PROCESSED':
      console.log('[CarrierEntry] Field processed', message.data?.field?.kintoneField);
      broadcastToPopup(message);
      break;

    case 'FIELD_ERROR':
      console.error('[CarrierEntry] Field error', message.data);
      broadcastToPopup(message);
      break;

    case 'PROCESSING_ERROR':
      console.error('[CarrierEntry] Processing error', message.data?.error);
      broadcastToPopup(message);
      break;

    case 'PAGE_COMPLETED':
      console.log('[CarrierEntry] Page processing completed', message.pageName);
      break;

    case 'AUTOMATION_ERROR':
      console.error('[CarrierEntry] Automation error', message.error);
      break;

    case 'GET_MAPPING':
      fetch(chrome.runtime.getURL('config/mapping.json'))
        .then(response => response.json())
        .then(data => sendResponse({ success: true, data }))
        .catch(error => sendResponse({ success: false, error: error.message }));
      return true;
  }

  return false;
});

/**
 * 非同期メッセージを処理
 */
async function handleAsyncMessage(message, sender, sendResponse) {
  try {
    switch (message.action) {
      case 'PROCESSING_COMPLETED':
        // ログを保存
        if (message.data?.logEntry) {
          await LogManager.appendLog(message.data.logEntry);
          console.log('[CarrierEntry] Log saved', message.data.logEntry.id);
        }
        // Popupに中継
        broadcastToPopup(message);
        sendResponse({ success: true });
        break;

      case 'GET_LOGS':
        const logs = await LogManager.getLogs(
          message.limit || 50,
          message.offset || 0
        );
        sendResponse({ success: true, logs });
        break;

      case 'EXPORT_LOGS':
        const exported = await LogManager.exportLogs(message.format || 'json');
        sendResponse({ success: true, data: exported, format: message.format || 'json' });
        break;

      case 'CLEAR_LOGS':
        await LogManager.clearLogs();
        sendResponse({ success: true });
        break;

      case 'GET_LOG_STATS':
        const stats = await LogManager.getStats();
        sendResponse({ success: true, stats });
        break;

      default:
        sendResponse({ success: false, error: 'Unknown action' });
    }
  } catch (error) {
    console.error('[CarrierEntry] Async message error', error);
    sendResponse({ success: false, error: error.message });
  }
}

/**
 * Popupにメッセージを中継
 */
async function broadcastToPopup(message) {
  try {
    // 全ての拡張機能のビュー（popup含む）にメッセージを送信
    const views = chrome.extension?.getViews?.({ type: 'popup' }) || [];

    if (views.length > 0) {
      // Popupが開いている場合は直接送信
      await chrome.runtime.sendMessage(message);
    }
  } catch (error) {
    // Popupが閉じている場合は無視
  }
}

// storage変更監視
chrome.storage.onChanged.addListener((changes, namespace) => {
  if (namespace !== 'local') return;

  if (changes.kintoneData) {
    console.log('[CarrierEntry] Kintone data changed',
      changes.kintoneData.newValue ? 'set' : 'cleared');
  }

  if (changes.automationActive) {
    console.log('[CarrierEntry] Automation status changed',
      changes.automationActive.newValue);
  }
});

console.log('[CarrierEntry] Background service worker started');
