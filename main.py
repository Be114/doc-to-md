#!/usr/bin/env python3
"""
技術ドキュメント一括Markdown化ツール
メインエントリーポイント
"""

import os
import sys
import yaml
import time
from pathlib import Path
from crawler import WebCrawler
from converter import MarkdownConverter


class DocToMarkdownTool:
    def __init__(self, config_path="config.yaml"):
        self.config = self._load_config(config_path)
        self.crawler = WebCrawler(self.config)
        self.converter = MarkdownConverter(self.config)
        
    def _load_config(self, config_path):
        """設定ファイルを読み込む"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"エラー: 設定ファイル '{config_path}' が見つかりません")
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"エラー: 設定ファイルの読み込みに失敗しました: {e}")
            sys.exit(1)
    
    def _setup_output_directory(self):
        """出力ディレクトリを作成"""
        output_dir = Path(self.config['output']['base_dir'])
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if self.config['output']['download_images']:
            image_dir = output_dir / self.config['output']['image_dir_name']
            image_dir.mkdir(exist_ok=True)
    
    def run(self):
        """メイン実行処理"""
        print("技術ドキュメント一括Markdown化ツールを開始します...")
        print(f"開始URL: {self.config['target_site']['start_url']}")
        
        # 出力ディレクトリの準備
        self._setup_output_directory()
        
        # クロール開始
        print("\nページのクロールを開始します...")
        urls = self.crawler.crawl()
        
        if not urls:
            print("警告: 対象となるURLが見つかりませんでした")
            return
        
        print(f"\n{len(urls)}個のページが見つかりました。変換を開始します...\n")
        
        # 各ページを処理
        for i, url in enumerate(urls, 1):
            print(f"[{i}/{len(urls)}] 処理中: {url}")
            
            try:
                # ページの内容を取得・変換・保存
                self.converter.process_page(url)
                
                # リクエスト間隔の調整
                if i < len(urls):  # 最後のページでない場合
                    delay = self.config['execution']['request_delay']
                    time.sleep(delay)
                    
            except Exception as e:
                print(f"エラー: {url} の処理に失敗しました: {e}")
                continue
        
        print(f"\n処理完了! 出力ディレクトリ: {self.config['output']['base_dir']}")


def main():
    """メイン関数"""
    tool = DocToMarkdownTool()
    try:
        tool.run()
    except KeyboardInterrupt:
        print("\n\n処理が中断されました")
        sys.exit(1)
    except Exception as e:
        print(f"予期しないエラーが発生しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()