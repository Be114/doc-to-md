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