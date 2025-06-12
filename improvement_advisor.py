"""
実行可能な改善提案付きサマリーレポート機能
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from error_types import ErrorType


@dataclass
class Suggestion:
    """改善提案の構造"""
    issue: str  # 問題の説明
    suggestion: str  # 具体的な改善提案
    priority: str  # 優先度 (HIGH, MEDIUM, LOW)
    category: str  # カテゴリ (PERFORMANCE, RELIABILITY, CONFIGURATION)


class ImprovementAdvisor:
    """改善提案システム"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.suggestions: List[Suggestion] = []
    
    def analyze_results(self, 
                       crawler_stats: Dict[str, int],
                       converter_stats: Dict[str, int],
                       error_stats: Dict[ErrorType, int],
                       config: Dict[str, Any],
                       total_processing_time: float = 0) -> List[Suggestion]:
        """実行結果を分析して改善提案を生成"""
        self.suggestions = []
        
        # ネットワーク関連の分析
        self._analyze_network_issues(crawler_stats, error_stats, config)
        
        # コンテンツ処理の分析
        self._analyze_content_processing(converter_stats, error_stats)
        
        # パフォーマンスの分析
        self._analyze_performance(crawler_stats, converter_stats, total_processing_time)
        
        # 設定の分析
        self._analyze_configuration(config, crawler_stats, error_stats)
        
        # 信頼性の分析
        self._analyze_reliability(error_stats, crawler_stats, converter_stats)
        
        return self.suggestions
    
    def _analyze_network_issues(self, crawler_stats: Dict[str, int], 
                               error_stats: Dict[ErrorType, int], 
                               config: Dict[str, Any]):
        """ネットワーク関連の問題を分析"""
        network_errors = error_stats.get(ErrorType.NETWORK_ERROR, 0)
        total_processed = crawler_stats.get('total_crawled', 0) + crawler_stats.get('total_failed', 0)
        
        if total_processed == 0:
            return
            
        error_rate = network_errors / total_processed
        request_delay = config.get('execution', {}).get('request_delay', 1.0)
        
        # ネットワークエラー率が高い場合
        if error_rate > 0.3:  # 30%以上
            if request_delay < 2.0:
                self.suggestions.append(Suggestion(
                    issue=f"ネットワークエラーが多発しています（{error_rate:.1%}）",
                    suggestion=f"config.yamlのexecution.request_delayを{request_delay + 1.0}秒以上に増やすことを検討してください",
                    priority="HIGH",
                    category="RELIABILITY"
                ))
            else:
                self.suggestions.append(Suggestion(
                    issue=f"ネットワークエラーが多発しています（{error_rate:.1%}）",
                    suggestion="対象サイトのサーバー負荷が高い可能性があります。時間を変えて再実行することを検討してください",
                    priority="MEDIUM",
                    category="RELIABILITY"
                ))
        elif error_rate > 0.1:  # 10-30%
            self.suggestions.append(Suggestion(
                issue=f"ネットワークエラーが散発しています（{error_rate:.1%}）",
                suggestion=f"request_delayを{request_delay + 0.5}秒に増やすことで安定性が向上する可能性があります",
                priority="MEDIUM",
                category="RELIABILITY"
            ))
    
    def _analyze_content_processing(self, converter_stats: Dict[str, int], 
                                  error_stats: Dict[ErrorType, int]):
        """コンテンツ処理の分析"""
        content_errors = error_stats.get(ErrorType.CONTENT_EXTRACTION_ERROR, 0)
        total_processed = converter_stats.get('total_processed', 0)
        
        if total_processed == 0:
            return
            
        content_error_rate = content_errors / total_processed
        
        # コンテンツ抽出エラー率が高い場合
        if content_error_rate > 0.2:  # 20%以上
            self.suggestions.append(Suggestion(
                issue=f"コンテンツ抽出エラーが多発しています（{content_error_rate:.1%}）",
                suggestion="config.yamlのextractor.content_selectorの設定が不適切な可能性があります。対象サイトの構造を再確認してください",
                priority="HIGH",
                category="CONFIGURATION"
            ))
        elif content_error_rate > 0.05:  # 5-20%
            self.suggestions.append(Suggestion(
                issue=f"コンテンツ抽出エラーが発生しています（{content_error_rate:.1%}）",
                suggestion="一部のページでコンテンツ抽出に失敗しています。content_selectorの調整を検討してください",
                priority="MEDIUM",
                category="CONFIGURATION"
            ))
        
        # 画像ダウンロードの分析
        images_downloaded = converter_stats.get('images_downloaded', 0)
        images_failed = converter_stats.get('images_failed', 0)
        
        if images_failed > 0 and images_downloaded + images_failed > 0:
            image_failure_rate = images_failed / (images_downloaded + images_failed)
            if image_failure_rate > 0.3:
                self.suggestions.append(Suggestion(
                    issue=f"画像ダウンロード失敗率が高いです（{image_failure_rate:.1%}）",
                    suggestion="画像ダウンロードを無効にする（output.download_images: false）ことを検討してください",
                    priority="MEDIUM",
                    category="CONFIGURATION"
                ))
    
    def _analyze_performance(self, crawler_stats: Dict[str, int], 
                           converter_stats: Dict[str, int], 
                           total_time: float):
        """パフォーマンスの分析"""
        total_pages = crawler_stats.get('total_crawled', 0)
        
        if total_pages == 0 or total_time == 0:
            return
            
        pages_per_minute = (total_pages / total_time) * 60
        
        # 処理速度の分析
        if pages_per_minute < 5:  # 1分間に5ページ未満
            self.suggestions.append(Suggestion(
                issue=f"処理速度が遅いです（{pages_per_minute:.1f}ページ/分）",
                suggestion="request_delayの値を下げるか、ログレベルを調整することで高速化できる可能性があります",
                priority="LOW",
                category="PERFORMANCE"
            ))
        
        # 大量画像処理の警告
        images_downloaded = converter_stats.get('images_downloaded', 0)
        if images_downloaded > 100:
            self.suggestions.append(Suggestion(
                issue=f"大量の画像をダウンロードしています（{images_downloaded}個）",
                suggestion="ストレージ容量と処理時間の観点から、必要に応じてdownload_imagesを無効にすることを検討してください",
                priority="LOW",
                category="PERFORMANCE"
            ))
    
    def _analyze_configuration(self, config: Dict[str, Any], 
                             crawler_stats: Dict[str, int], 
                             error_stats: Dict[ErrorType, int]):
        """設定の分析"""
        # 除外パターンの効果分析
        total_skipped = crawler_stats.get('total_skipped', 0)
        total_crawled = crawler_stats.get('total_crawled', 0)
        
        if total_crawled > 0:
            skip_rate = total_skipped / (total_crawled + total_skipped)
            
            if skip_rate > 0.5:  # 50%以上がスキップ
                self.suggestions.append(Suggestion(
                    issue=f"多くのURLがスキップされています（{skip_rate:.1%}）",
                    suggestion="crawler.exclude_patternsが過度に制限的な可能性があります。パターンの見直しを検討してください",
                    priority="MEDIUM",
                    category="CONFIGURATION"
                ))
            elif skip_rate < 0.1 and total_crawled > 50:  # 10%未満かつある程度の規模
                self.suggestions.append(Suggestion(
                    issue=f"除外パターンの効果が薄いです（スキップ率{skip_rate:.1%}）",
                    suggestion="不要なページを除外するパターンを追加することで、効率的な処理が可能になります",
                    priority="LOW",
                    category="CONFIGURATION"
                ))
        
        # ログ設定の提案
        log_config = config.get('logging', {})
        console_level = log_config.get('console_level', 'INFO')
        file_level = log_config.get('file_level', 'DEBUG')
        
        if console_level == 'DEBUG' and total_crawled > 20:
            self.suggestions.append(Suggestion(
                issue="DEBUGレベルのコンソール出力が有効です",
                suggestion="大量処理時はconsole_levelをINFOに変更することで出力量を減らせます",
                priority="LOW",
                category="PERFORMANCE"
            ))
    
    def _analyze_reliability(self, error_stats: Dict[ErrorType, int],
                           crawler_stats: Dict[str, int],
                           converter_stats: Dict[str, int]):
        """信頼性の分析"""
        total_errors = sum(error_stats.values())
        total_operations = (crawler_stats.get('total_crawled', 0) + 
                          crawler_stats.get('total_failed', 0) +
                          converter_stats.get('total_processed', 0))
        
        if total_operations == 0:
            return
            
        overall_error_rate = total_errors / total_operations
        
        # 全体的なエラー率の分析
        if overall_error_rate > 0.4:  # 40%以上
            self.suggestions.append(Suggestion(
                issue=f"全体的なエラー率が高いです（{overall_error_rate:.1%}）",
                suggestion="設定の見直しと対象サイトの再確認を強く推奨します。特にURLとCSSセレクターの確認をしてください",
                priority="HIGH",
                category="RELIABILITY"
            ))
        elif overall_error_rate > 0.2:  # 20-40%
            self.suggestions.append(Suggestion(
                issue=f"エラー率がやや高めです（{overall_error_rate:.1%}）",
                suggestion="設定の最適化によりエラー率を下げることができる可能性があります",
                priority="MEDIUM",
                category="RELIABILITY"
            ))
        
        # ファイルシステムエラーの分析
        fs_errors = error_stats.get(ErrorType.FILE_SYSTEM_ERROR, 0)
        if fs_errors > 0:
            self.suggestions.append(Suggestion(
                issue=f"ファイルシステムエラーが発生しています（{fs_errors}件）",
                suggestion="出力ディレクトリの権限とディスク容量を確認してください",
                priority="HIGH",
                category="RELIABILITY"
            ))
    
    def generate_report(self, suggestions: List[Suggestion]) -> str:
        """改善提案レポートを生成"""
        if not suggestions:
            return "実行に問題はありませんでした。設定は適切に動作しています。"
        
        # 優先度でソート
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        sorted_suggestions = sorted(suggestions, key=lambda x: priority_order.get(x.priority, 3))
        
        report_lines = ["=== 改善提案レポート ==="]
        
        current_priority = None
        for suggestion in sorted_suggestions:
            if current_priority != suggestion.priority:
                current_priority = suggestion.priority
                report_lines.append(f"\n【{current_priority}優先度】")
            
            report_lines.append(f"問題: {suggestion.issue}")
            report_lines.append(f"提案: {suggestion.suggestion}")
            report_lines.append(f"カテゴリ: {suggestion.category}")
            report_lines.append("")
        
        return "\n".join(report_lines)
    
    def log_suggestions(self, suggestions: List[Suggestion]):
        """改善提案をログに出力"""
        if not suggestions:
            self.logger.info("改善提案: 実行に問題はありませんでした")
            return
        
        self.logger.info("=== 改善提案 ===")
        
        # 優先度別に集計
        high_priority = [s for s in suggestions if s.priority == "HIGH"]
        medium_priority = [s for s in suggestions if s.priority == "MEDIUM"]
        low_priority = [s for s in suggestions if s.priority == "LOW"]
        
        if high_priority:
            self.logger.warning(f"緊急対応が必要な問題: {len(high_priority)}件")
            for suggestion in high_priority:
                self.logger.warning(f"  - {suggestion.issue}")
                self.logger.warning(f"    提案: {suggestion.suggestion}")
        
        if medium_priority:
            self.logger.info(f"改善を推奨する項目: {len(medium_priority)}件")
            for suggestion in medium_priority:
                self.logger.info(f"  - {suggestion.issue}")
                self.logger.info(f"    提案: {suggestion.suggestion}")
        
        if low_priority:
            self.logger.debug(f"最適化のための提案: {len(low_priority)}件")
            for suggestion in low_priority:
                self.logger.debug(f"  - {suggestion.issue}")
                self.logger.debug(f"    提案: {suggestion.suggestion}")