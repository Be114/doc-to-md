# 設定ファイルサンプル

このディレクトリには、様々なドキュメントサイトに対応した設定ファイルのサンプルが含まれています。

## サンプル一覧

### 1. python_docs.yaml
**用途**: Python公式ドキュメント用
- 対象: https://docs.python.org/3/library/
- 特徴: Sphinxベースのドキュメントに最適化
- セレクター: `.toctree-wrapper` (ナビゲーション)、`div[role='main']` (コンテンツ)

```bash
python main.py config_samples/python_docs.yaml
```

### 2. docs_general.yaml
**用途**: 一般的なドキュメントサイト用
- 対象: GitBook、Sphinx、VuePress等の汎用ドキュメントサイト
- 特徴: 多くのドキュメントサイトで共通的に使用されるセレクター
- セレクター: `nav` (ナビゲーション)、`main` (コンテンツ)

```bash
python main.py config_samples/docs_general.yaml
```

### 3. minimal.yaml
**用途**: 最小設定例
- 対象: 設定の学習・テスト用
- 特徴: 必須項目のみを含む最小構成
- セレクター: `nav` (ナビゲーション)、`main` (コンテンツ)

```bash
python main.py config_samples/minimal.yaml
```

### 4. sphinx_docs.yaml
**用途**: Sphinxドキュメント用
- 対象: readthedocs.org、Sphinxベースのサイト
- 特徴: Sphinxの特徴的な構造に最適化（toctree等）
- セレクター: `.toctree-wrapper, .wy-menu-vertical` (ナビゲーション)、`div[role='main']` (コンテンツ)

```bash
python main.py config_samples/sphinx_docs.yaml
```

### 5. github_pages.yaml
**用途**: GitHub Pages / Jekyll用
- 対象: GitHub Pagesでホストされているドキュメント
- 特徴: Jekyll、GitHub Pagesの構造に最適化
- セレクター: `nav, .sidebar, .sidebar-nav` (ナビゲーション)、`main, .content, .markdown-body` (コンテンツ)

```bash
python main.py config_samples/github_pages.yaml
```

### 6. gitbook.yaml
**用途**: GitBook用
- 対象: GitBookでホストされているドキュメント
- 特徴: GitBookの動的な構造に対応
- セレクター: `.sidebar, [data-testid='sidebar']` (ナビゲーション)、`main, .page-inner` (コンテンツ)

```bash
python main.py config_samples/gitbook.yaml
```

## 新機能（Phase 7.4）

### リトライ機能強化
すべての設定例にリトライ機能が追加されました：

```yaml
retry:
  max_retries: 3                    # 最大リトライ回数
  backoff_factor: 2                 # 指数バックオフ係数
  initial_delay: 1.0                # 初期遅延時間（秒）
  max_delay: 60.0                   # 最大遅延時間（秒）
  retry_status_codes: [429, 500, 502, 503, 504]  # リトライ対象ステータス
  skip_after_failures: 5            # 自動スキップする失敗回数
```

### リカバリ機能
処理中断時の自動保存・再開機能：

```yaml
recovery:
  enable_recovery: true             # リカバリ機能の有効化
  save_interval: 10                 # 状態保存間隔（ページ数）
  recovery_file: "./recovery.json"  # リカバリファイルパス
  auto_resume: true                 # 自動再開の有効化
```

中断されたクロール処理は次回実行時に自動的に再開できます。

## カスタム設定の作成

新しいサイトに対応するには：

1. 上記のサンプルをベースにコピー
2. 対象サイトに合わせて以下を調整：
   - `target_site.start_url`: 開始URL
   - `target_site.allowed_domain`: 許可ドメイン
   - `crawler.navigation_selector`: ナビゲーション要素のCSSセレクター
   - `extractor.content_selector`: メインコンテンツ要素のCSSセレクター

## よく使用されるCSSセレクター

### ナビゲーション (navigation_selector)
- `.toctree-wrapper` - Sphinx（Python docs等）
- `.sidebar` - GitBook
- `.sidebar-nav` - VuePress
- `nav` - HTML5セマンティック（汎用）
- `.navigation` - 汎用
- `.menu` - 汎用

### コンテンツ (content_selector)
- `div[role='main']` - ARIA（アクセシビリティ対応サイト）
- `main` - HTML5セマンティック
- `.content` - 汎用
- `.main-content` - 汎用
- `.markdown-body` - GitHub Pages
- `article` - HTML5セマンティック

## トラブルシューティング

コンテンツが正しく抽出されない場合：

1. ブラウザの開発者ツールでページ構造を確認
2. 適切なCSSセレクターを見つける
3. 設定ファイルを調整してテスト実行