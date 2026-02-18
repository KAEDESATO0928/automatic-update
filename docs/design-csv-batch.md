# SONET エントリー自動化 - CSV対応・バッチ処理 設計書

## 概要

kintoneからエクスポートしたCSVファイルを読み込み、So-net申込サイトへ自動入力するChrome拡張機能の拡張。

### 要件
- **データソース**: CSVファイル（Shift-JIS）
- **実行モード**: 1件ずつ / まとめてバッチ処理
- **後方互換**: 既存のkintone API連携も維持

---

## ファイル構成

### 新規作成
| ファイル | 役割 |
|---------|------|
| `scripts/csv-parser.js` | Shift-JIS CSV解析・フィールドマッピング |
| `scripts/batch-manager.js` | バッチ処理状態管理・オーケストレーション |
| `config/csv-mapping.json` | CSVカラム名 → kintoneField 変換定義 |

### 修正対象
| ファイル | 変更内容 |
|---------|---------|
| `popup/popup.html` | データソース切替UI、CSV選択、バッチ制御 |
| `popup/popup.css` | 新UIコンポーネントのスタイル |
| `popup/popup.js` | CSVインポート処理、モード切替、バッチ制御 |
| `scripts/background.js` | バッチ関連メッセージハンドリング |
| `manifest.json` | web_accessible_resources追加 |

---

## 設計詳細

### 1. CSV Parser (`scripts/csv-parser.js`)

```javascript
// 主要機能
parseCSV(arrayBuffer)       // Shift-JIS → UTF-8変換 + パース
mapCSVToKintone(row, config) // CSVカラム → kintoneField変換
validateRow(row)            // 必須フィールド検証
```

**Shift-JIS対応**: `TextDecoder('shift-jis')` で変換

### 2. CSVマッピング設定 (`config/csv-mapping.json`)

```json
{
  "directMappings": {
    "契約者姓　漢字": "name_last_kanji",
    "契約者名　漢字": "name_first_kanji",
    "契約者姓　カナ": "name_last_kana",
    "契約者名　カナ": "name_first_kana",
    "郵便番号（前半の3桁）": "zip_1",
    "郵便番号（後半の4桁）": "zip_2",
    "住所": "_raw_address",
    "建物名": "building",
    "部屋番号": "room"
  },
  "computedFields": [
    {
      "target": "agency_code",
      "type": "lookup",
      "sources": ["所属会社", "申込プラン"],
      "lookupTable": "agencyCodeTable"
    },
    {
      "target": ["tel_1_1", "tel_1_2", "tel_1_3"],
      "type": "split",
      "source": "連絡先電話番号",
      "delimiter": "-"
    },
    {
      "target": ["pref_code", "city", "town", "chome"],
      "type": "addressParse",
      "source": "_raw_address",
      "comment": "住所を都道府県・市区町村・町名・番地に分割"
    }
  ],
  "lookupTables": {
    "agencyCodeTable": { /* 後で設定 */ },
    "planCodeTable": { /* 後で設定 */ }
  }
}
```

### 3. バッチマネージャー (`scripts/batch-manager.js`)

**状態遷移**:
```
IDLE → LOADING → READY → PROCESSING → COMPLETED
                    ↓         ↓
                  ERROR ←── PAUSED
```

**バッチ状態**:
```javascript
{
  status: 'idle' | 'processing' | 'paused' | 'completed',
  mode: 'single' | 'batch',
  records: [],
  currentIndex: 0,
  successCount: 0,
  failedCount: 0,
  skippedCount: 0
}
```

### 4. UI設計

```
+------------------------------------------+
| データソース                              |
|  (*) API Mode    ( ) CSV Mode             |
+------------------------------------------+
| [CSV Mode]                                |
| CSVファイル: [選択] data.csv (50件)       |
|                                           |
| 実行モード                                |
|  (*) 1件ずつ    ( ) まとめて              |
|                                           |
| レコード選択                              |
| [▼ 1 - 田中太郎          ]               |
+------------------------------------------+
| [====== 実行開始 ======]                  |
+------------------------------------------+
| バッチ進捗: 3/10件 (30%)                  |
| [========>                    ]           |
| [一時停止] [キャンセル]                   |
+------------------------------------------+
```

### 5. エラーハンドリング

| エラー種別 | 対応 |
|-----------|------|
| CSV解析エラー | インポート中止、詳細表示 |
| 必須フィールド不足 | 行をスキップ、警告表示 |
| 要素タイムアウト | 自動リトライ(3回) |
| ページエラー | ユーザー選択（リトライ/スキップ/停止） |

---

## データフロー

```
CSV選択 → parseCSV() → mapCSVToKintone() → BatchManager.records[]
                                                    ↓
     ← content_script処理 ← DATA_READY ← processNextRecord()
                                                    ↓
     Page7完了検知 → RECORD_COMPLETE → 次レコードへ or 完了
```

---

## 実装フェーズ

### Phase 1: CSV Parser 基盤
- [ ] `scripts/csv-parser.js` 作成
- [ ] `config/csv-mapping.json` 作成
- [ ] Shift-JIS対応テスト

### Phase 2: UI - CSVモード
- [ ] popup.html にデータソース切替追加
- [ ] ファイル選択・プレビュー機能
- [ ] モード切替ロジック

### Phase 3: 単一レコードCSVモード
- [ ] レコード選択ドロップダウン
- [ ] 既存処理フローへの接続
- [ ] E2Eテスト

### Phase 4: バッチマネージャー
- [ ] `scripts/batch-manager.js` 作成
- [ ] 状態永続化（chrome.storage.local）
- [ ] background.js メッセージ対応

### Phase 5: バッチ実行
- [ ] 複数レコード連続処理
- [ ] Page7完了検知 → 次レコード遷移
- [ ] 進捗表示UI

### Phase 6: エラーハンドリング
- [ ] エラーダイアログUI
- [ ] リトライ/スキップ/停止アクション
- [ ] 結果サマリー・エクスポート

---

## 検証方法

1. **CSVパース検証**: サンプルCSVでShift-JIS正常読み込み確認
2. **マッピング検証**: 変換後データがmapping.jsonのフィールドと一致確認
3. **単一レコード検証**: CSV1件でPage1〜7を手動実行
4. **バッチ検証**: 3件程度で連続処理テスト
5. **エラー検証**: 意図的にエラーを発生させ復旧動作確認

---

## CSVカラム構成（確認済み）

| CSVカラム | マッピング先 |
|----------|-------------|
| 郵便番号（前半の3桁） | zip_1 |
| 郵便番号（後半の4桁） | zip_2 |
| 住所 | 要分割 → pref_code, city, town, chome |
| 建物名 | building |
| 部屋番号 | room |

---

## 未決定事項（後で設定）

- [ ] 所属会社 × 申込プラン → agency_code のルックアップテーブル
- [ ] 所属会社 × 申込プラン → plan_code のルックアップテーブル
- [ ] 住所分割ロジックの詳細（正規表現パターン）
- [ ] バッチ処理時の自動進行/手動確認の選択
