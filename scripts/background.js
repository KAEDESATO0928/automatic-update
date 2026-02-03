/**
 * Background Service Worker for Carrier Entry Automation
 * ページ遷移の監視とメッセージング
 */

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
  // 完全にロードされた場合のみ
  if (changeInfo.status !== 'complete') return;
  
  // 対象サイトかチェック
  if (!tab.url || !tab.url.includes('so-net.ne.jp')) return;
  
  console.log('[CarrierEntry] Target page loaded', tab.url);
  
  // 自動化が有効か確認
  const { automationActive, kintoneData } = await chrome.storage.local.get([
    'automationActive',
    'kintoneData'
  ]);
  
  if (automationActive && kintoneData) {
    // content scriptに処理開始を通知
    try {
      await chrome.tabs.sendMessage(tabId, {
        action: 'PAGE_LOADED',
        url: tab.url
      });
      console.log('[CarrierEntry] Notified content script');
    } catch (error) {
      // content scriptがまだ準備できていない場合
      console.log('[CarrierEntry] Content script not ready, will retry');
    }
  }
});

// メッセージハンドラ
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log('[CarrierEntry] Message received in background', message);
  
  switch (message.action) {
    case 'LOG':
      // content scriptからのログ
      console.log(`[CarrierEntry:Content] ${message.message}`, message.data);
      break;
      
    case 'PAGE_COMPLETED':
      // ページ処理完了通知
      console.log('[CarrierEntry] Page processing completed', message.pageName);
      break;
      
    case 'AUTOMATION_ERROR':
      // エラー通知
      console.error('[CarrierEntry] Automation error', message.error);
      break;
      
    case 'GET_MAPPING':
      // マッピング設定を返す（必要に応じて）
      fetch(chrome.runtime.getURL('config/mapping.json'))
        .then(response => response.json())
        .then(data => sendResponse({ success: true, data }))
        .catch(error => sendResponse({ success: false, error: error.message }));
      return true; // 非同期レスポンスのため
  }
  
  return false;
});

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
