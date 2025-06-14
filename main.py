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
from error_types import ErrorHandler, FileSystemError, ErrorSeverity
from logging_manager import setup_logging, StructuredLogger
from improvement_advisor import ImprovementAdvisor
from recovery_manager import RecoveryManager


class DocToMarkdownTool:
    def __init__(self, config_path="config.yaml"):
        self.config_manager = ConfigManager(config_path)
        
        # 包括的ログシステムの初期化
        self.logging_manager = setup_logging(self.config_manager.config, "doc_to_md")
        self.logging_manager.log_system_info()
        
        # 構造化ロガーの取得
        self.logger = self.logging_manager.get_logger('doc_to_markdown_tool')
        self.structured_logger = StructuredLogger(self.logger)
        
        # 各モジュールの初期化（ログ設定後）
        self.crawler = WebCrawler(self.config_manager.config)
        self.converter = MarkdownConverter(self.config_manager.config)
        
        # エラーハンドラーの初期化
        self.error_handler = ErrorHandler(self.logger)
        
        # リカバリマネージャーの初期化
        self.recovery_manager = RecoveryManager(self.config_manager.config, self.logger)
    
    def _setup_output_directory(self):
        """出力ディレクトリを作成"""
        try:
            output_config = self.config_manager.get_output_config()
            output_dir = Path(output_config['base_dir'])
            output_dir.mkdir(parents=True, exist_ok=True)
            
            if output_config['download_images']:
                image_dir = output_dir / output_config['image_dir_name']
                image_dir.mkdir(exist_ok=True)
                
        except PermissionError as e:
            error = FileSystemError(
                message="出力ディレクトリの作成権限がありません",
                file_path=str(output_dir),
                severity=ErrorSeverity.CRITICAL,
                original_exception=e
            )
            self.error_handler.handle_error(error)
            raise
        except OSError as e:
            error = FileSystemError(
                message="出力ディレクトリの作成に失敗しました",
                file_path=str(output_dir),
                severity=ErrorSeverity.CRITICAL,
                original_exception=e
            )
            self.error_handler.handle_error(error)
            raise
        except Exception as e:
            error = FileSystemError(
                message="ディレクトリ作成中の予期しないエラー",
                file_path=str(output_dir),
                severity=ErrorSeverity.HIGH,
                original_exception=e
            )
            self.error_handler.handle_error(error)
            raise
    
    def run(self):
        """メイン実行処理"""
        target_config = self.config_manager.get_target_site()
        recovery_config = self.config_manager.get_recovery_config()
        
        print("技術ドキュメント一括Markdown化ツールを開始します...")
        print(f"開始URL: {target_config['start_url']}")
        
        # リカバリファイルの確認
        resume_from_recovery = False
        if self.recovery_manager.can_resume() and recovery_config.get('auto_resume', True):
            response = input("\n前回の処理が途中で中断されています。続きから再開しますか？ (y/n): ").strip().lower()
            if response in ['y', 'yes']:
                if self.recovery_manager.load_state():
                    resume_from_recovery = True
                    print("前回の処理から再開します...")
                else:
                    print("リカバリに失敗しました。最初から開始します...")
            else:
                print("最初から開始します...")
                self.recovery_manager.cleanup_recovery_file()
        
        # 出力ディレクトリの準備
        self._setup_output_directory()
        
        try:
            # クロールと変換を統合実行
            print("\nページのクロールと変換を開始します...")
            result = self._crawl_and_convert(resume_from_recovery)
            
            if not result['success']:
                print("処理に失敗しました")
                return
            
            # 正常完了時はリカバリファイルを削除
            self.recovery_manager.cleanup_recovery_file()
            
            # 結果の表示
            self._display_results(result)
            
        except KeyboardInterrupt:
            print("\n\n処理が中断されました")
            # 中断時に現在の状態を保存
            self._save_interruption_state()
            raise
        except Exception as e:
            # 予期しないエラー時も状態を保存
            self._save_interruption_state()
            raise
    
    def _crawl_and_convert(self, resume_from_recovery: bool = False):
        """クロールと変換を統合実行（リカバリ対応）"""
        start_time = time.time()
        
        target_config = self.config_manager.get_target_site()
        execution_config = self.config_manager.get_execution_config()
        
        start_url = target_config.get('start_url', '')
        request_delay = execution_config.get('request_delay', 1.0)
        
        if not start_url:
            print("エラー: start_urlが設定されていません")
            return {'success': False}
        
        # 統計情報とトラッキング（リカバリからの復元対応）
        if resume_from_recovery:
            processed_count = self.recovery_manager.state.processed_count
            success_count = self.recovery_manager.state.success_count
            failed_count = self.recovery_manager.state.failed_count
            crawled_urls = self.recovery_manager.state.crawled_urls.copy()
            
            # クローラーの状態を復元
            self.crawler.visited_urls = self.recovery_manager.state.visited_urls.copy()
            self.crawler.failed_url_counts = self.recovery_manager.state.failed_url_counts.copy()
            
            # 正規化URLマップを再構築
            for url in self.recovery_manager.state.visited_urls:
                normalized = self.crawler._normalize_url(url)
                self.crawler.normalized_urls[normalized] = url
            
            # 統計を更新
            self.crawler.stats['total_crawled'] = len(crawled_urls)
            
            print(f"リカバリ: {processed_count}ページから再開")
            print("注意: リカバリ時は開始URLから再度リンク発見を行います")
        else:
            processed_count = 0
            success_count = 0
            failed_count = 0
            crawled_urls = []
        
        # URLキューを初期化（リカバリ時も開始URLから再探索）
        self.crawler.url_queue.put(start_url, priority=0)
        
        while not self.crawler.url_queue.empty():
            current_url = self.crawler.url_queue.get()
            
            # 重複チェック（パブリックAPIを使用）
            if self.crawler.is_url_visited(current_url):
                self.crawler.stats['total_skipped'] += 1
                continue
            
            processed_count += 1
            # 総数計算: 処理済み + 現在のキュー内URL数 + 成功/失敗済み
            total_count = processed_count + self.crawler.url_queue.size()
            print(f"[{processed_count}/{total_count}] 処理中: ({current_url})")
            
            try:
                # ページを取得（パブリックAPIを使用）
                html_content = self.crawler.fetch_page(current_url)
                if html_content is None:
                    failed_count += 1
                    continue
                
                # 訪問済みとしてマーク（パブリックAPIを使用）
                self.crawler.mark_url_as_visited(current_url)
                crawled_urls.append(current_url)  # 成功したURLを記録
                
                # コンテンツを変換・保存
                file_path = self.converter.process_page(current_url, html_content)
                if file_path:
                    success_count += 1
                    print(f"  → 保存: {file_path}")
                else:
                    failed_count += 1
                    print(f"  → 変換失敗")
                
                # 新しいリンクを抽出してキューに追加（パブリックAPIを使用）
                links = self.crawler.extract_links_from_content(current_url, html_content)
                added_count = 0
                
                for link_url, priority in links:
                    if not self.crawler.is_url_visited(link_url):
                        self.crawler.url_queue.put(link_url, priority)
                        added_count += 1
                
                if added_count > 0:
                    print(f"  → 新しいリンク{added_count}個を発見")
                
                # 定期的な状態保存
                self.recovery_manager.save_state(
                    start_url=start_url,
                    visited_urls=self.crawler.visited_urls,
                    failed_url_counts=self.crawler.failed_url_counts,
                    processed_count=processed_count,
                    success_count=success_count,
                    failed_count=failed_count,
                    crawled_urls=crawled_urls
                )
                
                # リクエスト間隔の調整
                if request_delay > 0 and not self.crawler.url_queue.empty():
                    time.sleep(request_delay)
                    
            except Exception as e:
                error = FileSystemError(
                    message="ページ処理中の予期しないエラー",
                    file_path="unknown",
                    severity=ErrorSeverity.MEDIUM,
                    original_exception=e
                )
                self.error_handler.handle_error(error)
                print(f"  → エラー: {e}")
                failed_count += 1
                continue
        
        # 処理時間の計算
        end_time = time.time()
        processing_time = end_time - start_time
        
        return {
            'success': True,
            'processed': processed_count,
            'success_count': success_count,
            'failed_count': failed_count,
            'crawled_urls': crawled_urls,
            'crawler_stats': self.crawler.get_stats(),
            'converter_stats': self.converter.get_stats(),
            'processing_time': processing_time
        }
    
    def _display_results(self, result):
        """処理結果を表示"""
        output_config = self.config_manager.get_output_config()
        
        print(f"\n=== 処理完了 ===")
        print(f"処理ページ数: {result['processed']}")
        print(f"変換成功: {result['success_count']}")
        print(f"変換失敗: {result['failed_count']}")
        
        # 成功率の計算
        if result['processed'] > 0:
            success_rate = (result['success_count'] / result['processed']) * 100
            print(f"成功率: {success_rate:.1f}%")
        
        # 画像統計
        converter_stats = result['converter_stats']
        if converter_stats['images_downloaded'] > 0 or converter_stats['images_failed'] > 0:
            print(f"画像ダウンロード成功: {converter_stats['images_downloaded']}")
            print(f"画像ダウンロード失敗: {converter_stats['images_failed']}")
        
        print(f"\n出力ディレクトリ: {output_config['base_dir']}")
        
        # 詳細な統計をログに出力
        self.crawler.log_crawl_summary(result.get('crawled_urls', []))
        self.converter.log_summary()
        
        # 全体のエラー統計サマリーを出力
        print("\n=== 全体エラー統計 ===")
        self.error_handler.log_error_summary()
        
        # 改善提案の生成と表示
        advisor = ImprovementAdvisor(self.logger)
        suggestions = advisor.analyze_results(
            crawler_stats=result['crawler_stats'],
            converter_stats=result['converter_stats'],
            error_stats=self.error_handler.get_error_summary(),
            config=self.config_manager.config,
            total_processing_time=result.get('processing_time', 0)
        )
        
        # 改善提案の表示
        if suggestions:
            print("\n" + advisor.generate_report(suggestions))
        else:
            print("\n=== 改善提案 ===")
            print("実行に問題はありませんでした。設定は適切に動作しています。")
        
        # ログにも出力
        advisor.log_suggestions(suggestions)
    
    def _save_interruption_state(self):
        """中断時の状態保存"""
        try:
            # 現在の処理状況を取得（可能な限り）
            visited_urls = getattr(self.crawler, 'visited_urls', set())
            failed_url_counts = getattr(self.crawler, 'failed_url_counts', {})
            
            # 処理済みURLから統計を推定
            processed_count = len(visited_urls)
            success_count = getattr(self.crawler, 'stats', {}).get('total_crawled', 0)
            failed_count = getattr(self.crawler, 'stats', {}).get('total_failed', 0)
            crawled_urls = list(visited_urls)
            
            # 開始URLを取得
            target_config = self.config_manager.get_target_site()
            start_url = target_config.get('start_url', '')
            
            # 強制保存
            self.recovery_manager.force_save_current_state(
                start_url=start_url,
                visited_urls=visited_urls,
                failed_url_counts=failed_url_counts,
                processed_count=processed_count,
                success_count=success_count,
                failed_count=failed_count,
                crawled_urls=crawled_urls
            )
            
            print(f"現在の進行状況をリカバリファイルに保存しました: {processed_count}ページ処理済み")
            
        except Exception as e:
            self.logger.error(f"中断時の状態保存に失敗: {e}")


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