#!/usr/bin/env python3
"""
技術ドキュメント一括Markdown化ツール
メインエントリーポイント
"""

import sys
import time
import argparse
from pathlib import Path
from config_manager import ConfigManager
from crawler import WebCrawler
from converter import MarkdownConverter


class DocToMarkdownTool:
    def __init__(self, config_path="config.yaml"):
        self.config_manager = ConfigManager(config_path)
        self.crawler = WebCrawler(self.config_manager.config)
        self.converter = MarkdownConverter(self.config_manager.config)
    
    def _setup_output_directory(self):
        """出力ディレクトリを作成"""
        output_config = self.config_manager.get_output_config()
        output_dir = Path(output_config['base_dir'])
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if output_config['download_images']:
            image_dir = output_dir / output_config['image_dir_name']
            image_dir.mkdir(exist_ok=True)
    
    def run(self):
        """メイン実行処理"""
        target_config = self.config_manager.get_target_site()
        output_config = self.config_manager.get_output_config()
        execution_config = self.config_manager.get_execution_config()
        
        print("技術ドキュメント一括Markdown化ツールを開始します...")
        print(f"開始URL: {target_config['start_url']}")
        
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
                    delay = execution_config['request_delay']
                    time.sleep(delay)
                    
            except Exception as e:
                print(f"エラー: {url} の処理に失敗しました: {e}")
                continue
        
        print(f"\n処理完了! 出力ディレクトリ: {output_config['base_dir']}")


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description='技術ドキュメント一括Markdown化ツール',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python main.py                                    # config.yamlを使用
  python main.py config_samples/python_docs.yaml   # 引数で設定ファイルを指定
  python main.py --config config_samples/minimal.yaml  # --configオプションで指定

設定ファイルサンプル:
  config_samples/python_docs.yaml  - Python公式ドキュメント用
  config_samples/docs_general.yaml - 一般的なドキュメントサイト用
  config_samples/minimal.yaml      - 最小設定例
        """)
    
    parser.add_argument(
        'config_file', 
        nargs='?', 
        default='config.yaml',
        help='設定ファイルのパス (デフォルト: config.yaml)'
    )
    parser.add_argument(
        '--config', '-c',
        dest='config_file',
        help='設定ファイルのパス (引数と同じ)'
    )
    
    args = parser.parse_args()
    
    tool = DocToMarkdownTool(args.config_file)
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