/**
 * Error Types and Utilities for Carrier Entry Automation
 * エラー型定義とユーティリティ
 */

// エラータイプ定義
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

/**
 * 構造化エラーを作成
 * @param {string} type - ErrorTypesの値
 * @param {string} message - 追加メッセージ（オプション）
 * @param {Object} context - コンテキスト情報
 * @returns {Object} 構造化エラーオブジェクト
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
 * ユーザー向けエラーメッセージをフォーマット
 * @param {Object} error - エラーオブジェクト
 * @returns {string} フォーマットされたメッセージ
 */
function formatErrorForUser(error) {
  const parts = [error.message];

  if (error.field) {
    parts.push(`フィールド: ${error.field}`);
  }
  if (error.selector) {
    parts.push(`セレクタ: ${error.selector}`);
  }
  if (error.value !== undefined) {
    parts.push(`値: ${error.value}`);
  }
  if (error.retryCount !== undefined) {
    parts.push(`リトライ: ${error.retryCount}回`);
  }

  return parts.join(' | ');
}

/**
 * UUIDを生成
 * @returns {string} UUID
 */
function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

// エクスポート（content scriptで使用）
if (typeof window !== 'undefined') {
  window.CarrierEntryErrors = {
    ErrorTypes,
    ErrorMessages,
    createError,
    formatErrorForUser,
    generateUUID
  };
}
