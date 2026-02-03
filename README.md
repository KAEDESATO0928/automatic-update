# Carrier Entry Automation

kintoneの顧客データを通信キャリア（So-net）の申込サイトへ自動入力するChrome拡張機能です。

## 機能

- kintone REST APIからレコードデータを取得
- 全7ページの申込フォームに自動入力
- ページ遷移を自動検知して継続処理
- 外部JSON（`mapping.json`）によるマッピング定義

## インストール方法

1. このフォルダをダウンロード・解凍
2. Chromeで `chrome://extensions/` を開く
3. 右上の「デベロッパーモード」をON
4. 「パッケージ化されていない拡張機能を読み込む」をクリック
5. このフォルダを選択

## 使い方

### 1. 初期設定

1. 拡張機能アイコンをクリックしてポップアップを開く
2. 「API設定」セクションに以下を入力:
   - **kintone アプリID**: 顧客データが保存されているアプリのID
   - **APIトークン**: kintoneアプリで発行したAPIトークン
3. 「設定を保存」をクリック

### 2. 自動入力の実行

1. ポップアップの「レコード番号」に対象のレコードIDを入力
2. 「データ取得 & 開始」をクリック
3. So-netの申込サイトを開く（または既に開いている場合は自動で処理開始）
4. 各ページで自動入力が実行される

## ファイル構成

```
carrier-entry-extension/
├── manifest.json           # 拡張機能の設定
├── popup/
│   ├── popup.html          # ポップアップUI
│   ├── popup.js            # ポップアップのロジック
│   └── popup.css           # スタイル
├── scripts/
│   ├── content_script.js   # DOM操作のメインロジック
│   └── background.js       # Service Worker
├── config/
│   └── mapping.json        # マッピング定義（編集可能）
└── icons/
    ├── icon16.png
    ├── icon48.png
    └── icon128.png
```

## マッピング定義（mapping.json）

マッピングは以下のタイプをサポートしています：

| type | 説明 |
|------|------|
| `text` | テキストフィールドに値を入力 |
| `select` | プルダウンメニューを選択 |
| `click` | 指定セレクタの要素をクリック |
| `click_by_value` | kintoneの値に応じて対応するセレクタをクリック |
| `click_multiple` | kintoneの配列値をループして複数要素をクリック |

### マッピング例

```json
{
  "kintoneField": "plan_code",
  "selector": null,
  "type": "click_by_value",
  "valueMap": {
    "10G_EAST_HOME": "#UP1060Useable_entry_HCOE3101",
    "10G_EAST_MANSION": "#UP1060Useable_entry_HCOE3201"
  }
}
```

## kintone側の設定

### 必要なフィールド

`mapping.json`で定義されている`kintoneField`に対応するフィールドをkintoneアプリに作成してください。

### APIトークンの権限

- レコード閲覧権限が必要です

## トラブルシューティング

### データが取得できない

- kintoneのアプリIDとAPIトークンが正しいか確認
- APIトークンに閲覧権限があるか確認
- ブラウザのコンソール（F12）でエラーを確認

### 自動入力が動かない

- 対象サイト（so-net.ne.jp）を開いているか確認
- ポップアップの「現在の状態」でデータが取得済みか確認
- ブラウザのコンソールでエラーを確認

### 特定のフィールドが入力されない

- `mapping.json`のセレクタが正しいか確認
- kintoneのフィールドコードが一致しているか確認
- 対象要素がページに存在するか確認

## 注意事項

- この拡張機能は開発・テスト目的です
- 本番環境で使用する前に十分なテストを行ってください
- kintoneのAPIトークンは安全に管理してください

## 今後の拡張予定

- [ ] kintone画面内のボタンからの起動
- [ ] mapping.jsonをkintone設定アプリから取得
- [ ] エラーハンドリングの強化
- [ ] 入力結果のログ保存
