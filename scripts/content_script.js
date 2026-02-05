/**
 * Content Script for Carrier Entry Automation
 * マッピング定義に基づいてDOMを操作する
 */

(function() {
  'use strict';

  // エラータイプ定義（errors.jsと同期）
  const ErrorTypes = {
    ELEMENT_NOT_FOUND: 'ELEMENT_NOT_FOUND',
    ELEMENT_TIMEOUT: 'ELEMENT_TIMEOUT',
    VALUE_MISSING: 'VALUE_MISSING',
    VALUE_MAP_MISSING: 'VALUE_MAP_MISSING',
    SELECTOR_MISSING: 'SELECTOR_MISSING',
    INPUT_FAILED: 'INPUT_FAILED',
    CLICK_FAILED: 'CLICK_FAILED',
    PAGE_CONFIG_NOT_FOUND: 'PAGE_CONFIG_NOT_FOUND',
    MAPPING_LOAD_FAILED: 'MAPPING_LOAD_FAILED',
    UNKNOWN: 'UNKNOWN'
  };

  // エラーメッセージ（日本語）
  const ErrorMessages = {
    [ErrorTypes.ELEMENT_NOT_FOUND]: '要素が見つかりませんでした',
    [ErrorTypes.ELEMENT_TIMEOUT]: '要素の読み込みがタイムアウトしました',
    [ErrorTypes.VALUE_MISSING]: '入力値がありません',
    [ErrorTypes.VALUE_MAP_MISSING]: '値に対応するセレクタが定義されていません',
    [ErrorTypes.SELECTOR_MISSING]: 'セレクタが定義されていません',
    [ErrorTypes.INPUT_FAILED]: '入力処理に失敗しました',
    [ErrorTypes.CLICK_FAILED]: 'クリック処理に失敗しました',
    [ErrorTypes.PAGE_CONFIG_NOT_FOUND]: 'このページの設定が見つかりません',
    [ErrorTypes.MAPPING_LOAD_FAILED]: 'マッピング設定の読み込みに失敗しました',
    [ErrorTypes.UNKNOWN]: '不明なエラーが発生しました'
  };

  // 設定
  const CONFIG = {
    WAIT_FOR_ELEMENT_TIMEOUT: 10000,
    WAIT_AFTER_INPUT: 100,
    WAIT_AFTER_CLICK: 500,
    WAIT_BETWEEN_ACTIONS: 200,
    MAX_RETRIES: 3,
    RETRY_BASE_DELAY: 1000,
    RETRY_MAX_DELAY: 10000,
    DEBUG: true
  };

  // グローバル状態
  let mappingConfig = null;
  let kintoneData = null;
  let isProcessing = false;

  /**
   * 構造化エラーを作成
   */
  function createError(type, message = null, context = {}) {
    const baseMessage = ErrorMessages[type] || ErrorMessages[ErrorTypes.UNKNOWN];
    return {
      type,
      message: message || baseMessage,
      ...context,
      timestamp: new Date().toISOString()
    };
  }

  /**
   * UUIDを生成
   */
  function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }

  /**
   * Popup/Backgroundに通知
   */
  async function notifyPopup(action, data) {
    try {
      await chrome.runtime.sendMessage({
        action,
        data,
        source: 'content_script',
        timestamp: new Date().toISOString(),
        url: window.location.href
      });
    } catch (error) {
      log('Failed to notify popup', error.message);
    }
  }

  /**
   * リトライ付き実行（指数バックオフ）
   */
  async function retryWithBackoff(fn, options = {}) {
    const {
      maxRetries = CONFIG.MAX_RETRIES,
      baseDelay = CONFIG.RETRY_BASE_DELAY,
      maxDelay = CONFIG.RETRY_MAX_DELAY,
      context = {}
    } = options;

    let lastError;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        return await fn();
      } catch (error) {
        lastError = error;

        if (attempt < maxRetries) {
          const delay = Math.min(baseDelay * Math.pow(2, attempt), maxDelay);
          log(`Retry ${attempt + 1}/${maxRetries} in ${delay}ms...`, context);
          await wait(delay);
        }
      }
    }

    // リトライ回数を記録
    if (lastError && typeof lastError === 'object') {
      lastError.retryCount = maxRetries;
    }

    throw lastError;
  }

  /**
   * 初期化
   */
  async function initialize() {
    log('Content script initializing...');

    mappingConfig = await loadMappingConfig();
    if (!mappingConfig) {
      log('Failed to load mapping config');
      await notifyPopup('PROCESSING_ERROR', {
        error: createError(ErrorTypes.MAPPING_LOAD_FAILED)
      });
      return;
    }

    log('Mapping config loaded', mappingConfig.settings);

    const stored = await chrome.storage.local.get(['kintoneData', 'automationActive']);

    if (stored.kintoneData && stored.automationActive) {
      kintoneData = stored.kintoneData;
      log('Kintone data found', { recordId: kintoneData._recordId });
      await processCurrentPage();
    } else {
      log('No active automation data');
    }

    chrome.runtime.onMessage.addListener(handleMessage);
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

    // ログエントリを初期化
    const logEntry = {
      id: generateUUID(),
      timestamp: new Date().toISOString(),
      recordId: kintoneData._recordId || '',
      pageName: pageConfig.pageName,
      pageUrl: currentUrl,
      urlPattern: pageConfig.urlPattern,
      status: 'success',
      duration: 0,
      fields: [],
      errors: []
    };

    const startTime = Date.now();

    // 処理開始を通知
    await notifyPopup('PROCESSING_STARTED', {
      pageName: pageConfig.pageName,
      url: currentUrl,
      recordId: kintoneData._recordId,
      totalFields: pageConfig.mapping.length
    });

    try {
      await wait(500);

      for (const field of pageConfig.mapping) {
        const result = await processField(field);
        logEntry.fields.push(result);

        if (result.status === 'failed' && result.error) {
          logEntry.errors.push(result.error);
        }

        await wait(CONFIG.WAIT_BETWEEN_ACTIONS);
      }

      // 全体ステータスを判定
      const failedCount = logEntry.fields.filter(f => f.status === 'failed').length;
      if (failedCount === logEntry.fields.length) {
        logEntry.status = 'failed';
      } else if (failedCount > 0) {
        logEntry.status = 'partial';
      }

      log('Page processing completed', { status: logEntry.status });

    } catch (error) {
      logEntry.status = 'failed';
      const structuredError = error.type ? error : createError(ErrorTypes.UNKNOWN, error.message);
      logEntry.errors.push(structuredError);

      await notifyPopup('PROCESSING_ERROR', { error: structuredError });
    } finally {
      logEntry.duration = Date.now() - startTime;
      isProcessing = false;

      // 処理完了を通知
      await notifyPopup('PROCESSING_COMPLETED', { logEntry });
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
    const startTime = Date.now();
    const value = kintoneData[kintoneField];

    const result = {
      kintoneField,
      description: description || kintoneField,
      type,
      selector,
      inputValue: value,
      status: 'pending',
      duration: 0,
      error: null
    };

    log(`Processing field: ${kintoneField} (${type})`, { value, selector });

    try {
      // リトライ付きで実行
      await retryWithBackoff(async () => {
        switch (type) {
          case 'text':
            await handleTextInput(selector, value, kintoneField);
            break;

          case 'select':
            await handleSelectInput(selector, value, kintoneField);
            break;

          case 'click':
            await handleClick(selector, kintoneField);
            break;

          case 'click_by_value':
            await handleClickByValue(value, valueMap, kintoneField);
            break;

          case 'click_multiple':
            await handleClickMultiple(value, valueMap, kintoneField);
            break;

          default:
            log(`Unknown type: ${type}`);
        }
      }, { context: { field: kintoneField } });

      result.status = 'success';

    } catch (error) {
      result.status = 'failed';
      result.error = error.type ? error : createError(ErrorTypes.UNKNOWN, error.message, {
        field: kintoneField,
        selector
      });

      // エラーを即座に通知
      await notifyPopup('FIELD_ERROR', {
        field: result,
        error: result.error
      });
    } finally {
      result.duration = Date.now() - startTime;

      // フィールド処理結果を通知
      await notifyPopup('FIELD_PROCESSED', { field: result });
    }

    return result;
  }

  /**
   * テキスト入力
   */
  async function handleTextInput(selector, value, fieldName) {
    if (value === undefined || value === null) {
      log(`Skipping text input: no value for ${selector}`);
      return;
    }

    const element = await waitForElement(selector);

    element.focus();
    element.value = '';
    element.value = String(value);
    dispatchInputEvents(element);

    log(`Text input completed: ${selector} = ${value}`);
    await wait(CONFIG.WAIT_AFTER_INPUT);
  }

  /**
   * プルダウン選択
   */
  async function handleSelectInput(selector, value, fieldName) {
    if (value === undefined || value === null) {
      log(`Skipping select: no value for ${selector}`);
      return;
    }

    const element = await waitForElement(selector);

    element.value = String(value);
    element.dispatchEvent(new Event('change', { bubbles: true }));

    log(`Select completed: ${selector} = ${value}`);
    await wait(CONFIG.WAIT_AFTER_INPUT);
  }

  /**
   * クリック処理
   */
  async function handleClick(selector, fieldName) {
    const element = await waitForElement(selector);

    element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    await wait(200);

    element.click();

    log(`Click completed: ${selector}`);
    await wait(CONFIG.WAIT_AFTER_CLICK);
  }

  /**
   * 値に基づくクリック（単一）
   */
  async function handleClickByValue(value, valueMap, fieldName) {
    if (!value || !valueMap) {
      log('Skipping click_by_value: no value or valueMap');
      return;
    }

    const selector = valueMap[value];
    if (!selector) {
      throw createError(ErrorTypes.VALUE_MAP_MISSING, null, {
        field: fieldName,
        value,
        availableValues: Object.keys(valueMap)
      });
    }

    await handleClick(selector, fieldName);
  }

  /**
   * 値に基づくクリック（複数）
   */
  async function handleClickMultiple(values, valueMap, fieldName) {
    if (!values || !valueMap) {
      log('Skipping click_multiple: no values or valueMap');
      return;
    }

    const valueArray = Array.isArray(values) ? values : [values];

    for (const value of valueArray) {
      const selector = valueMap[value];
      if (selector) {
        await handleClick(selector, fieldName);
      } else {
        log(`No selector found for value: ${value}`);
      }
    }
  }

  /**
   * 要素の出現を待機（タイムアウト時はエラーをthrow）
   */
  function waitForElement(selector, timeout = CONFIG.WAIT_FOR_ELEMENT_TIMEOUT) {
    return new Promise((resolve, reject) => {
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

      // タイムアウト時はエラーをthrow
      setTimeout(() => {
        observer.disconnect();
        reject(createError(ErrorTypes.ELEMENT_TIMEOUT, null, {
          selector,
          timeout
        }));
      }, timeout);
    });
  }

  /**
   * 入力イベントを発火
   */
  function dispatchInputEvents(element) {
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

    const observer = new MutationObserver(() => {
      const currentUrl = window.location.href;
      if (currentUrl !== lastUrl) {
        lastUrl = currentUrl;
        log('Page URL changed', currentUrl);

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
