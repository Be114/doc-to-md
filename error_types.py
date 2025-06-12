"""
エラー分類とハンドリング機能
"""

from enum import Enum
from typing import Dict, Any, Optional
import logging


class ErrorType(Enum):
    """エラーの種別を定義"""
    NETWORK_ERROR = "network_error"
    CONTENT_EXTRACTION_ERROR = "content_extraction_error"
    FILE_SYSTEM_ERROR = "file_system_error"
    CONFIG_ERROR = "config_error"


class ErrorSeverity(Enum):
    """エラーの重要度を定義"""
    LOW = "low"          # 処理継続可能
    MEDIUM = "medium"    # 警告が必要だが処理継続可能
    HIGH = "high"        # 処理中断が必要
    CRITICAL = "critical" # 即座にプログラム終了が必要


class DocToMdError(Exception):
    """プロジェクト共通の基底例外クラス"""
    
    def __init__(self, 
                 message: str, 
                 error_type: ErrorType,
                 severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                 url: Optional[str] = None,
                 file_path: Optional[str] = None,
                 original_exception: Optional[Exception] = None):
        self.message = message
        self.error_type = error_type
        self.severity = severity
        self.url = url
        self.file_path = file_path
        self.original_exception = original_exception
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """エラー情報を辞書形式で返す"""
        return {
            'message': self.message,
            'error_type': self.error_type.value,
            'severity': self.severity.value,
            'url': self.url,
            'file_path': self.file_path,
            'original_exception': str(self.original_exception) if self.original_exception else None
        }


class NetworkError(DocToMdError):
    """ネットワーク関連のエラー"""
    
    def __init__(self, message: str, url: str, 
                 severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                 original_exception: Optional[Exception] = None):
        super().__init__(
            message=message,
            error_type=ErrorType.NETWORK_ERROR,
            severity=severity,
            url=url,
            original_exception=original_exception
        )


class ContentExtractionError(DocToMdError):
    """コンテンツ抽出関連のエラー"""
    
    def __init__(self, message: str, url: str,
                 severity: ErrorSeverity = ErrorSeverity.LOW,
                 original_exception: Optional[Exception] = None):
        super().__init__(
            message=message,
            error_type=ErrorType.CONTENT_EXTRACTION_ERROR,
            severity=severity,
            url=url,
            original_exception=original_exception
        )


class FileSystemError(DocToMdError):
    """ファイルシステム関連のエラー"""
    
    def __init__(self, message: str, file_path: str,
                 severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                 original_exception: Optional[Exception] = None):
        super().__init__(
            message=message,
            error_type=ErrorType.FILE_SYSTEM_ERROR,
            severity=severity,
            file_path=file_path,
            original_exception=original_exception
        )


class ConfigError(DocToMdError):
    """設定関連のエラー"""
    
    def __init__(self, message: str,
                 severity: ErrorSeverity = ErrorSeverity.CRITICAL,
                 original_exception: Optional[Exception] = None):
        super().__init__(
            message=message,
            error_type=ErrorType.CONFIG_ERROR,
            severity=severity,
            original_exception=original_exception
        )


class ErrorHandler:
    """エラー処理の統合管理クラス"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.error_stats = {
            ErrorType.NETWORK_ERROR: 0,
            ErrorType.CONTENT_EXTRACTION_ERROR: 0,
            ErrorType.FILE_SYSTEM_ERROR: 0,
            ErrorType.CONFIG_ERROR: 0
        }
    
    def handle_error(self, error: DocToMdError) -> bool:
        """
        エラーを処理し、処理継続可能かどうかを返す
        
        Returns:
            bool: True=処理継続可能, False=処理中断が必要
        """
        self.error_stats[error.error_type] += 1
        
        # ログレベルの決定
        if error.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(f"[{error.error_type.value.upper()}] {error.message}")
        elif error.severity == ErrorSeverity.HIGH:
            self.logger.error(f"[{error.error_type.value.upper()}] {error.message}")
        elif error.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(f"[{error.error_type.value.upper()}] {error.message}")
        else:
            self.logger.info(f"[{error.error_type.value.upper()}] {error.message}")
        
        # 詳細情報のログ出力
        if error.url:
            self.logger.debug(f"  URL: {error.url}")
        if error.file_path:
            self.logger.debug(f"  File: {error.file_path}")
        if error.original_exception:
            self.logger.debug(f"  Original: {error.original_exception}")
        
        # 処理継続判定
        return error.severity in [ErrorSeverity.LOW, ErrorSeverity.MEDIUM]
    
    def should_retry(self, error: DocToMdError) -> bool:
        """エラーに対してリトライすべきかどうかを判定"""
        retry_conditions = {
            ErrorType.NETWORK_ERROR: True,  # ネットワークエラーはリトライ
            ErrorType.CONTENT_EXTRACTION_ERROR: False,  # コンテンツエラーはスキップ
            ErrorType.FILE_SYSTEM_ERROR: True,  # ファイルシステムエラーは代替パス試行
            ErrorType.CONFIG_ERROR: False  # 設定エラーはリトライしない
        }
        
        return retry_conditions.get(error.error_type, False)
    
    def get_error_summary(self) -> Dict[str, int]:
        """エラー統計情報を取得"""
        return self.error_stats.copy()
    
    def log_error_summary(self):
        """エラー統計のサマリーをログ出力"""
        total_errors = sum(self.error_stats.values())
        if total_errors == 0:
            self.logger.info("エラーは発生しませんでした")
            return
        
        self.logger.info("=== エラー統計サマリー ===")
        self.logger.info(f"総エラー数: {total_errors}")
        
        for error_type, count in self.error_stats.items():
            if count > 0:
                self.logger.info(f"  {error_type.value}: {count}件")