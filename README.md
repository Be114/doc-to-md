# 技術ドキュメント一括Markdown化ツール

Web上の技術ドキュメントサイトのコンテンツを、サイトの階層構造を維持したまま一括でMarkdownファイルに変換・保存するコマンドラインツールです。

## 機能

### 基本機能
- 指定されたWebサイトを自動クロールしてドキュメントページを収集
- HTMLコンテンツをMarkdown形式に変換
- 元のURL構造を維持したディレクトリ構造で保存
- 画像の自動ダウンロードとローカル保存（オプション）
- 設定ファイル（config.yaml）による柔軟な動作制御

### エラー処理・復旧機能（Phase 7.4）
- **設定可能な指数バックオフリトライ**: ネットワークエラー時の自動リトライ
- **問題ページ自動スキップ**: 連続失敗するページの自動スキップ
- **中断・再開機能**: 処理中断時の自動状態保存と再開
- **包括的ログシステム**: ファイルローテーション付きの詳細ログ
- **改善提案システム**: 実行結果に基づく設定最適化提案

### 対応ドキュメントサイト
- Python公式ドキュメント（Sphinx）
- GitHub Pages / Jekyll
- GitBook
- readthedocs.org
- VuePress
- その他のHTML静的サイト

## インストール

### 依存関係のインストール

```bash
pip install -r requirements.txt
```

## 使用方法

### クイックスタート

1. **設定例を使用**（推奨）:
```bash
# Python公式ドキュメント用
python main.py config_samples/python_docs.yaml

# GitHub Pages用
python main.py config_samples/github_pages.yaml

# GitBook用  
python main.py config_samples/gitbook.yaml

# Sphinx用
python main.py config_samples/sphinx_docs.yaml
```

2. **カスタム設定ファイルの作成**:
```bash
# 設定例をコピーして編集
cp config_samples/docs_general.yaml my_config.yaml
# my_config.yamlを編集
python main.py my_config.yaml
```

3. **デフォルト設定での実行**:
```bash
python main.py  # config.yamlを使用
```

### 設定ファイル例

詳細な設定例は `config_samples/` ディレクトリを参照してください：

```yaml
# 対象サイトの設定
target_site:
  start_url: "https://docs.python.org/3/library/index.html"
  allowed_domain: "https://docs.python.org/3/library/"

# クロール設定
crawler:
  navigation_selector: ".toctree-wrapper"
  exclude_patterns:
    - ".*#.*"
    - ".*/search.html"
    - ".*/genindex.html"

# コンテンツ抽出設定  
extractor:
  content_selector: "div[role='main']"

# 出力設定
output:
  base_dir: "./output/python_docs"
  image_dir_name: "images"
  download_images: true

# 実行設定
execution:
  request_delay: 1.5

# リトライ設定（新機能）
retry:
  max_retries: 3
  backoff_factor: 2
  initial_delay: 1.0
  max_delay: 60.0
  retry_status_codes: [429, 500, 502, 503, 504]
  skip_after_failures: 5

# リカバリ設定（新機能）
recovery:
  enable_recovery: true
  save_interval: 10
  recovery_file: "./recovery_state.json"
  auto_resume: true

# ログ設定（強化版）
logging:
  console_level: "INFO"
  file_level: "DEBUG"
  log_dir: "./logs"
  max_file_size_mb: 5
  backup_count: 5
  enable_file_logging: true
```

## 設定項目の詳細説明

### target_site（必須）
- `start_url`: クロールを開始するURL
- `allowed_domain`: クロール対象とするURLのプレフィックス

### crawler（必須）
- `navigation_selector`: リンクを抽出する要素のCSSセレクター
- `exclude_patterns`: 除外するURLのパターン（正規表現のリスト）

### extractor（必須）
- `content_selector`: 抽出するメインコンテンツ要素のCSSセレクター

### output（必須）
- `base_dir`: Markdownファイルの保存先ディレクトリ
- `image_dir_name`: 画像保存用サブディレクトリ名（デフォルト: "images"）
- `download_images`: 画像をダウンロードするかどうか（デフォルト: true）

### execution（オプション）
- `request_delay`: リクエスト間の待機時間（秒、デフォルト: 1.0）

### retry（オプション、Phase 7.4で追加）
- `max_retries`: 最大リトライ回数（デフォルト: 3）
- `backoff_factor`: 指数バックオフ係数（デフォルト: 2）
- `initial_delay`: 初期遅延時間（秒、デフォルト: 1.0）
- `max_delay`: 最大遅延時間（秒、デフォルト: 60.0）
- `retry_status_codes`: リトライ対象HTTPステータスコード
- `skip_after_failures`: 自動スキップする連続失敗回数（デフォルト: 5）

### recovery（オプション、Phase 7.4で追加）
- `enable_recovery`: リカバリ機能の有効化（デフォルト: true）
- `save_interval`: 状態保存間隔（ページ数、デフォルト: 10）
- `recovery_file`: リカバリファイルのパス（デフォルト: "./recovery_state.json"）
- `auto_resume`: 自動再開の有効化（デフォルト: true）

### logging（オプション、Phase 7.3で強化）
- `console_level`: コンソール出力レベル（DEBUG/INFO/WARNING/ERROR/CRITICAL）
- `file_level`: ファイル出力レベル（DEBUG/INFO/WARNING/ERROR/CRITICAL）
- `log_dir`: ログファイル保存ディレクトリ（デフォルト: "./logs"）
- `max_file_size_mb`: ログファイル最大サイズ（MB、デフォルト: 5）
- `backup_count`: バックアップファイル保持数（デフォルト: 5）
- `enable_file_logging`: ファイルログ有効化（デフォルト: true）

## ファイル構成

```
doc-to-md/
├── main.py                 # メインエントリーポイント
├── crawler.py              # Webクローリング機能（Phase 7.4強化）
├── converter.py            # HTML→Markdown変換機能
├── config_manager.py       # 設定管理と検証
├── error_types.py          # エラー分類システム（Phase 7.2）
├── logging_manager.py      # 包括的ログシステム（Phase 7.3）
├── improvement_advisor.py  # 改善提案システム（Phase 7.3）
├── recovery_manager.py     # リカバリ機能（Phase 7.4）
├── config.yaml             # デフォルト設定ファイル
├── requirements.txt        # 依存ライブラリ
├── README.md               # このファイル
├── CLAUDE.md               # 開発プラン
└── config_samples/         # 設定例ディレクトリ
    ├── README.md           # 設定例の説明
    ├── python_docs.yaml    # Python公式ドキュメント用
    ├── sphinx_docs.yaml    # Sphinx/readthedocs用
    ├── github_pages.yaml   # GitHub Pages/Jekyll用
    ├── gitbook.yaml        # GitBook用
    ├── docs_general.yaml   # 汎用ドキュメントサイト用
    └── minimal.yaml        # 最小設定例
```

## 新機能の詳細（Phase 7.4）

### 中断・再開機能
処理を中断（Ctrl+C）した場合、次回実行時に続きから再開できます：

```bash
$ python main.py config_samples/python_docs.yaml
# ... 処理中にCtrl+Cで中断

$ python main.py config_samples/python_docs.yaml
前回の処理が途中で中断されています。続きから再開しますか？ (y/n): y
前回の処理から再開します...
リカバリ: 150ページから再開
```

### 改善提案システム
実行完了後、処理結果を分析して設定最適化の提案を表示：

```
=== 改善提案 ===
[HIGH] request_delayを2.0秒に増加することをお勧めします（現在: 1.0秒）
[MEDIUM] max_retriesを5回に増加することをお勧めします（失敗率: 15%）
[LOW] ログレベルをWARNINGに変更することをお勧めします
```

### 包括的ログシステム
詳細なログがファイルに保存され、問題の分析が可能：

```
logs/
├── doc_to_md.log      # メインログファイル
├── doc_to_md.log.1    # ローテーションバックアップ
└── doc_to_md.log.2
```

## 注意事項

- このツールは静的なHTMLサイトを対象としています
- JavaScriptで動的に生成されるコンテンツには対応していません
- サーバーに負荷をかけないよう、適切なリクエスト間隔を設定してください
- 対象サイトの利用規約を確認してから使用してください
- 大量のページを処理する場合は、リカバリ機能を有効にしてください

## トラブルシューティング

### よくある問題と解決方法

**1. コンテンツが正しく抽出されない**
```bash
# ブラウザの開発者ツールで正しいセレクターを確認
# 設定ファイルのcontent_selectorを調整
content_selector: "main, .content, article"
```

**2. リンクが検出されない**
```bash
# navigation_selectorを調整
navigation_selector: "nav, .sidebar, .toc"
```

**3. エラーが多発する**
```bash
# リトライ設定を調整
retry:
  max_retries: 5
  initial_delay: 2.0
  skip_after_failures: 3
```

**4. 処理が遅い**
```bash
# 改善提案システムの提案に従って設定を最適化
# request_delayを調整
execution:
  request_delay: 0.5  # 高速化（負荷に注意）
```

**5. メモリ不足**
```bash
# save_intervalを小さくして頻繁に保存
recovery:
  save_interval: 5
```

### ログの確認方法

詳細なエラー情報は `logs/doc_to_md.log` で確認できます：

```bash
# 最新のエラーを確認
tail -n 50 logs/doc_to_md.log

# エラーのみを表示
grep "ERROR\|CRITICAL" logs/doc_to_md.log

# 特定URLの問題を確認
grep "example.com" logs/doc_to_md.log
```

## エラー処理（強化版）

### 自動エラー処理
- **ネットワークエラー**: 指数バックオフで自動リトライ
- **コンテンツエラー**: ログ記録後にスキップ
- **連続失敗**: 設定された回数後に自動スキップ
- **システムエラー**: 詳細ログ記録と適切な終了処理

### エラー統計
実行完了時にエラーの詳細統計が表示されます：

```
=== 全体エラー統計 ===
ネットワークエラー: 5件
コンテンツ抽出エラー: 2件
自動スキップ: 3ページ

=== 失敗URL統計 ===
自動スキップ: https://example.com/broken-page (5回)
失敗: https://example.com/slow-page (3回)
```