# 技術ドキュメント一括Markdown化ツール

Web上の技術ドキュメントサイトのコンテンツを、サイトの階層構造を維持したまま一括でMarkdownファイルに変換・保存するコマンドラインツールです。

## 機能

- 指定されたWebサイトを自動クロールしてドキュメントページを収集
- HTMLコンテンツをMarkdown形式に変換
- 元のURL構造を維持したディレクトリ構造で保存
- 画像の自動ダウンロードとローカル保存（オプション）
- 設定ファイル（config.yaml）による柔軟な動作制御

## インストール

### 依存関係のインストール

```bash
pip install -r requirements.txt
```

## 使用方法

### 1. 設定ファイルの編集

`config.yaml`ファイルを編集して、対象サイトと動作設定を指定します：

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
  request_delay: 1
```

### 2. ツールの実行

```bash
python main.py
```

## 設定項目の説明

### target_site
- `start_url`: クロールを開始するURL
- `allowed_domain`: クロール対象とするURLのプレフィックス

### crawler
- `navigation_selector`: リンクを抽出する要素のCSSセレクター
- `exclude_patterns`: 除外するURLのパターン（正規表現）

### extractor
- `content_selector`: 抽出するメインコンテンツ要素のCSSセレクター

### output
- `base_dir`: Markdownファイルの保存先ディレクトリ
- `image_dir_name`: 画像保存用サブディレクトリ名
- `download_images`: 画像をダウンロードするかどうか

### execution
- `request_delay`: リクエスト間の待機時間（秒）

## ファイル構成

```
doc-to-md/
├── main.py           # メインエントリーポイント
├── crawler.py        # Webクローリング機能
├── converter.py      # HTML→Markdown変換機能
├── config.yaml       # 設定ファイル
├── requirements.txt  # 依存ライブラリ
├── README.md         # このファイル
└── CLAUDE.md         # 開発プラン
```

## 注意事項

- このツールは静的なHTMLサイトを対象としています
- JavaScriptで動的に生成されるコンテンツには対応していません
- サーバーに負荷をかけないよう、適切なリクエスト間隔を設定してください
- 対象サイトの利用規約を確認してから使用してください

## エラー処理

- 個別ページの取得や変換に失敗しても、処理は継続されます
- エラーはコンソールに表示されます
- ネットワークエラーやコンテンツ抽出エラーに対応しています