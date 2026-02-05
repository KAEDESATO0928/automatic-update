/**
 * Log Manager for Carrier Entry Automation
 * ログの永続化と管理
 */

const LogManager = {
  STORAGE_KEY: 'operationLogs',
  MAX_ENTRIES: 100,

  /**
   * ログエントリを追加
   * @param {Object} logEntry - ログエントリ
   * @returns {Promise<Object>} 追加されたログエントリ
   */
  async appendLog(logEntry) {
    try {
      const { operationLogs = [] } = await chrome.storage.local.get(this.STORAGE_KEY);

      // 先頭に追加
      operationLogs.unshift(logEntry);

      // 最大件数を超えたら古いものを削除
      if (operationLogs.length > this.MAX_ENTRIES) {
        operationLogs.splice(this.MAX_ENTRIES);
      }

      await chrome.storage.local.set({ [this.STORAGE_KEY]: operationLogs });
      console.log('[CarrierEntry:LogManager] Log saved', logEntry.id);

      return logEntry;
    } catch (error) {
      console.error('[CarrierEntry:LogManager] Failed to save log', error);
      throw error;
    }
  },

  /**
   * ログを取得
   * @param {number} limit - 取得件数
   * @param {number} offset - オフセット
   * @returns {Promise<Array>} ログエントリの配列
   */
  async getLogs(limit = 50, offset = 0) {
    try {
      const { operationLogs = [] } = await chrome.storage.local.get(this.STORAGE_KEY);
      return operationLogs.slice(offset, offset + limit);
    } catch (error) {
      console.error('[CarrierEntry:LogManager] Failed to get logs', error);
      return [];
    }
  },

  /**
   * 特定のログを取得
   * @param {string} id - ログID
   * @returns {Promise<Object|null>} ログエントリまたはnull
   */
  async getLogById(id) {
    try {
      const { operationLogs = [] } = await chrome.storage.local.get(this.STORAGE_KEY);
      return operationLogs.find(log => log.id === id) || null;
    } catch (error) {
      console.error('[CarrierEntry:LogManager] Failed to get log by id', error);
      return null;
    }
  },

  /**
   * ログをクリア
   * @returns {Promise<void>}
   */
  async clearLogs() {
    try {
      await chrome.storage.local.remove(this.STORAGE_KEY);
      console.log('[CarrierEntry:LogManager] Logs cleared');
    } catch (error) {
      console.error('[CarrierEntry:LogManager] Failed to clear logs', error);
      throw error;
    }
  },

  /**
   * ログをエクスポート
   * @param {string} format - 'json' or 'csv'
   * @returns {Promise<string>} エクスポートされたデータ
   */
  async exportLogs(format = 'json') {
    const { operationLogs = [] } = await chrome.storage.local.get(this.STORAGE_KEY);

    if (format === 'json') {
      return JSON.stringify(operationLogs, null, 2);
    }

    if (format === 'csv') {
      return this.convertToCSV(operationLogs);
    }

    throw new Error(`Unknown format: ${format}`);
  },

  /**
   * ログをCSV形式に変換
   * @param {Array} logs - ログエントリの配列
   * @returns {string} CSV文字列
   */
  convertToCSV(logs) {
    if (logs.length === 0) {
      return '';
    }

    const headers = [
      'ID',
      'Timestamp',
      'RecordID',
      'Page',
      'URL',
      'Status',
      'Duration(ms)',
      'TotalFields',
      'SuccessFields',
      'FailedFields',
      'Errors'
    ];

    const rows = logs.map(log => {
      const successCount = log.fields ? log.fields.filter(f => f.status === 'success').length : 0;
      const failedCount = log.fields ? log.fields.filter(f => f.status === 'failed').length : 0;

      return [
        log.id,
        log.timestamp,
        log.recordId,
        `"${log.pageName || ''}"`,
        `"${log.pageUrl || ''}"`,
        log.status,
        log.duration,
        log.fields ? log.fields.length : 0,
        successCount,
        failedCount,
        log.errors ? log.errors.length : 0
      ];
    });

    return [headers.join(','), ...rows.map(row => row.join(','))].join('\n');
  },

  /**
   * ログの統計情報を取得
   * @returns {Promise<Object>} 統計情報
   */
  async getStats() {
    const { operationLogs = [] } = await chrome.storage.local.get(this.STORAGE_KEY);

    const stats = {
      totalLogs: operationLogs.length,
      successCount: 0,
      partialCount: 0,
      failedCount: 0,
      totalFields: 0,
      successFields: 0,
      failedFields: 0
    };

    for (const log of operationLogs) {
      if (log.status === 'success') stats.successCount++;
      else if (log.status === 'partial') stats.partialCount++;
      else if (log.status === 'failed') stats.failedCount++;

      if (log.fields) {
        stats.totalFields += log.fields.length;
        stats.successFields += log.fields.filter(f => f.status === 'success').length;
        stats.failedFields += log.fields.filter(f => f.status === 'failed').length;
      }
    }

    return stats;
  }
};

// Service Workerでも使えるようにエクスポート
if (typeof self !== 'undefined') {
  self.LogManager = LogManager;
}
