/**
 * Content Script for Carrier Entry Automation
 * マッピング定義に基づいてDOMを操作する
 */

(function() {
  'use strict';

  // 設定
  const CONFIG = {
    WAIT_FOR_ELEMENT_TIMEOUT: 10000,  // 要素待機タイムアウト(ms)
    WAIT_AFTER_INPUT: 100,            // 入力後の待機時間(ms)
    WAIT_AFTER_CLICK: 500,            // クリック後の待機時間(ms)
    WAIT_BETWEEN_ACTIONS: 200,        // アクション間の待機時間(ms)
    DEBUG: true
  };

  // グローバル状態
  let mappingConfig = null;
  let kintoneData = null;
  let isProcessing = false;

  /**
   * 初期化
   */
  async function initialize() {
    log('Content script initializing...');
    
    // マッピング設定を読み込み
    mappingConfig = await loadMappingConfig();
    if (!mappingConfig) {
      log('Failed to load mapping config');
      return;
    }
    
    log('Mapping config loaded', mappingConfig.settings);
    
    // 保存済みkintoneデータを確認
    const stored = await chrome.storage.local.get(['kintoneData', 'automationActive']);
    
    if (stored.kintoneData && stored.automationActive) {
      kintoneData = stored.kintoneData;
      log('Kintone data found', { recordId: kintoneData._recordId });
      
      // 現在のページに対応する処理を実行
      await processCurrentPage();
    } else {
      log('No active automation data');
    }
    
    // メッセージリスナー設定
    chrome.runtime.onMessage.addListener(handleMessage);
    
    // ページ変更監視（SPAの場合）
    observePageChanges();
  }

  /**
   * マッピング設定を読み込み
   */
  async function loadMappingConfig() {
    try {
      const url = chrome.runtime.getURL('config/mapping.json');
      const response = await fetch(url);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      log('Error loading mapping config', error);
      return null;
    }
  }

  /**
   * メッセージハンドラ
   */
  function handleMessage(message, sender, sendResponse) {
    log('Message received', message);
    
    switch (message.action) {
      case 'DATA_READY':
        kintoneData = message.data;
        processCurrentPage();
        break;
        
      case 'DATA_CLEARED':
        kintoneData = null;
        isProcessing = false;
        break;
        
      case 'GET_STATUS':
        sendResponse({
          hasData: !!kintoneData,
          isProcessing,
          currentUrl: window.location.href
        });
        break;
    }
    
    return true;
  }

  /**
   * 現在のページを処理
   */
  async function processCurrentPage() {
    if (!mappingConfig || !kintoneData) {
      log('Missing config or data');
      return;
    }
    
    if (isProcessing) {
      log('Already processing, skipping');
      return;
    }
    
    const currentUrl = window.location.href;
    const pageConfig = findPageConfig(currentUrl);
    
    if (!pageConfig) {
      log('No mapping for current URL', currentUrl);
      return;
    }
    
    log(`Processing page: ${pageConfig.pageName}`);
    isProcessing = true;
    
    try {
      // DOMが安定するまで少し待機
      await wait(500);
      
      // マッピングに従って処理
      for (const field of pageConfig.mapping) {
        await processField(field);
        await wait(CONFIG.WAIT_BETWEEN_ACTIONS);
      }
      
      log('Page processing completed');
    } catch (error) {
      log('Error processing page', error);
    } finally {
      isProcessing = false;
    }
  }

  /**
   * URLからページ設定を検索
   */
  function findPageConfig(url) {
    return mappingConfig.pages.find(page => url.includes(page.urlPattern));
  }

  /**
   * フィールドを処理
   */
  async function processField(field) {
    const { kintoneField, selector, type, valueMap, description } = field;
    
    // kintoneの値を取得（next_btn等のアクション用フィールドは値不要）
    const value = kintoneData[kintoneField];
    
    log(`Processing field: ${kintoneField} (${type})`, { value, selector });
    
    try {
      switch (type) {
        case 'text':
          await handleTextInput(selector, value);
          break;
          
        case 'select':
          await handleSelectInput(selector, value);
          break;
          
        case 'click':
          await handleClick(selector);
          break;
          
        case 'click_by_value':
          await handleClickByValue(value, valueMap);
          break;
          
        case 'click_multiple':
          await handleClickMultiple(value, valueMap);
          break;
          
        default:
          log(`Unknown type: ${type}`);
      }
    } catch (error) {
      log(`Error processing field ${kintoneField}`, error.message);
    }
  }

  /**
   * テキスト入力
   */
  async function handleTextInput(selector, value) {
    if (value === undefined || value === null) {
      log(`Skipping text input: no value for ${selector}`);
      return;
    }
    
    const element = await waitForElement(selector);
    if (!element) {
      throw new Error(`Element not found: ${selector}`);
    }
    
    // 既存値をクリアして入力
    element.focus();
    element.value = '';
    element.value = String(value);
    
    // イベント発火（Reactなどのフレームワーク対応）
    dispatchInputEvents(element);
    
    log(`Text input completed: ${selector} = ${value}`);
    await wait(CONFIG.WAIT_AFTER_INPUT);
  }

  /**
   * プルダウン選択
   */
  async function handleSelectInput(selector, value) {
    if (value === undefined || value === null) {
      log(`Skipping select: no value for ${selector}`);
      return;
    }
    
    const element = await waitForElement(selector);
    if (!element) {
      throw new Error(`Element not found: ${selector}`);
    }
    
    // 値を設定
    element.value = String(value);
    
    // changeイベント発火
    element.dispatchEvent(new Event('change', { bubbles: true }));
    
    log(`Select completed: ${selector} = ${value}`);
    await wait(CONFIG.WAIT_AFTER_INPUT);
  }

  /**
   * クリック処理
   */
  async function handleClick(selector) {
    const element = await waitForElement(selector);
    if (!element) {
      throw new Error(`Element not found: ${selector}`);
    }
    
    // スクロールして表示
    element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    await wait(200);
    
    // クリック
    element.click();
    
    log(`Click completed: ${selector}`);
    await wait(CONFIG.WAIT_AFTER_CLICK);
  }

  /**
   * 値に基づくクリック（単一）
   */
  async function handleClickByValue(value, valueMap) {
    if (!value || !valueMap) {
      log('Skipping click_by_value: no value or valueMap');
      return;
    }
    
    const selector = valueMap[value];
    if (!selector) {
      log(`No selector found for value: ${value}`);
      return;
    }
    
    await handleClick(selector);
  }

  /**
   * 値に基づくクリック（複数）
   */
  async function handleClickMultiple(values, valueMap) {
    if (!values || !valueMap) {
      log('Skipping click_multiple: no values or valueMap');
      return;
    }
    
    // 配列でない場合は配列に変換
    const valueArray = Array.isArray(values) ? values : [values];
    
    for (const value of valueArray) {
      const selector = valueMap[value];
      if (selector) {
        await handleClick(selector);
      } else {
        log(`No selector found for value: ${value}`);
      }
    }
  }

  /**
   * 要素の出現を待機
   */
  function waitForElement(selector, timeout = CONFIG.WAIT_FOR_ELEMENT_TIMEOUT) {
    return new Promise((resolve) => {
      // 即座にチェック
      const element = document.querySelector(selector);
      if (element) {
        resolve(element);
        return;
      }
      
      // MutationObserverで監視
      const observer = new MutationObserver((mutations, obs) => {
        const el = document.querySelector(selector);
        if (el) {
          obs.disconnect();
          resolve(el);
        }
      });
      
      observer.observe(document.body, {
        childList: true,
        subtree: true
      });
      
      // タイムアウト
      setTimeout(() => {
        observer.disconnect();
        resolve(null);
      }, timeout);
    });
  }

  /**
   * 入力イベントを発火
   */
  function dispatchInputEvents(element) {
    // 複数のイベントを発火（フレームワーク互換性のため）
    const events = [
      new Event('input', { bubbles: true }),
      new Event('change', { bubbles: true }),
      new KeyboardEvent('keyup', { bubbles: true })
    ];
    
    events.forEach(event => element.dispatchEvent(event));
  }

  /**
   * ページ変更を監視（SPA対応）
   */
  function observePageChanges() {
    let lastUrl = window.location.href;
    
    // URLの変更を監視
    const observer = new MutationObserver(() => {
      const currentUrl = window.location.href;
      if (currentUrl !== lastUrl) {
        lastUrl = currentUrl;
        log('Page URL changed', currentUrl);
        
        // 少し待ってから処理
        setTimeout(() => {
          isProcessing = false;
          processCurrentPage();
        }, 1000);
      }
    });
    
    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
    
    // popstateイベントも監視
    window.addEventListener('popstate', () => {
      log('Popstate event');
      setTimeout(() => {
        isProcessing = false;
        processCurrentPage();
      }, 1000);
    });
  }

  /**
   * 待機
   */
  function wait(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * ログ出力
   */
  function log(message, data = null) {
    if (!CONFIG.DEBUG) return;
    
    const prefix = '[CarrierEntry]';
    if (data) {
      console.log(prefix, message, data);
    } else {
      console.log(prefix, message);
    }
  }

  // DOMContentLoaded後に初期化
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize);
  } else {
    initialize();
  }

})();
