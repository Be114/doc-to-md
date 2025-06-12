"""
包括的ログシステム管理
構造化ログレベル、ファイル出力、ローテーション機能を提供
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from enum import Enum


class LogLevel(Enum):
    """ログレベルの定義"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LoggingManager:
    """包括的ログシステム管理クラス"""
    
    def __init__(self, config: Dict[str, Any], app_name: str = "doc_to_md"):
        self.config = config
        self.app_name = app_name
        self.loggers: Dict[str, logging.Logger] = {}
        
        # ログ設定を取得
        self.log_config = self._get_log_config()
        
        # ルートロガーの設定
        self._setup_root_logger()
        
        # ログディレクトリの作成
        self._ensure_log_directory()
    
    def _get_log_config(self) -> Dict[str, Any]:
        """ログ設定を取得（デフォルト値付き）"""
        default_config = {
            'console_level': 'INFO',
            'file_level': 'DEBUG',
            'log_dir': './logs',
            'max_file_size_mb': 5,
            'backup_count': 5,
            'log_format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'date_format': '%Y-%m-%d %H:%M:%S',
            'enable_file_logging': True
        }
        
        log_config = self.config.get('logging', {})
        
        # デフォルト値とマージ
        for key, default_value in default_config.items():
            if key not in log_config:
                log_config[key] = default_value
        
        return log_config
    
    def _get_log_level(self, level_str: str) -> int:
        """文字列からログレベルを取得"""
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        return level_map.get(level_str.upper(), logging.INFO)
    
    def _ensure_log_directory(self):
        """ログディレクトリの存在確保"""
        if self.log_config['enable_file_logging']:
            log_dir = Path(self.log_config['log_dir'])
            log_dir.mkdir(parents=True, exist_ok=True)
    
    def _setup_root_logger(self):
        """ルートロガーの設定"""
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)  # 最低レベルをDEBUGに設定
        
        # 既存のハンドラーをクリア
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # フォーマッターの作成
        formatter = logging.Formatter(
            fmt=self.log_config['log_format'],
            datefmt=self.log_config['date_format']
        )
        
        # コンソールハンドラーの設定
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self._get_log_level(self.log_config['console_level']))
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # ファイルハンドラーの設定（有効な場合）
        if self.log_config['enable_file_logging']:
            self._setup_file_handler(root_logger, formatter)
    
    def _setup_file_handler(self, logger: logging.Logger, formatter: logging.Formatter):
        """ファイルハンドラーの設定（ローテーション付き）"""
        log_file = Path(self.log_config['log_dir']) / f"{self.app_name}.log"
        
        # ローテーションファイルハンドラー
        max_bytes = self.log_config['max_file_size_mb'] * 1024 * 1024  # MBをバイトに変換
        file_handler = logging.handlers.RotatingFileHandler(
            filename=str(log_file),
            maxBytes=max_bytes,
            backupCount=self.log_config['backup_count'],
            encoding='utf-8'
        )
        
        file_handler.setLevel(self._get_log_level(self.log_config['file_level']))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    def get_logger(self, name: str) -> logging.Logger:
        """名前付きロガーを取得"""
        if name not in self.loggers:
            logger = logging.getLogger(name)
            # 個別の設定は不要（ルートロガーの設定を継承）
            self.loggers[name] = logger
        
        return self.loggers[name]
    
    def set_log_level(self, console_level: Optional[str] = None, file_level: Optional[str] = None):
        """実行時にログレベルを変更"""
        root_logger = logging.getLogger()
        
        for handler in root_logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                # コンソールハンドラー
                if console_level:
                    handler.setLevel(self._get_log_level(console_level))
            elif isinstance(handler, logging.handlers.RotatingFileHandler):
                # ファイルハンドラー
                if file_level:
                    handler.setLevel(self._get_log_level(file_level))
    
    def log_system_info(self):
        """システム情報をログ出力"""
        logger = self.get_logger('system')
        logger.info("=== ログシステム初期化完了 ===")
        logger.info(f"アプリケーション名: {self.app_name}")
        logger.info(f"コンソールログレベル: {self.log_config['console_level']}")
        
        if self.log_config['enable_file_logging']:
            logger.info(f"ファイルログレベル: {self.log_config['file_level']}")
            logger.info(f"ログディレクトリ: {self.log_config['log_dir']}")
            logger.info(f"最大ファイルサイズ: {self.log_config['max_file_size_mb']}MB")
            logger.info(f"バックアップ数: {self.log_config['backup_count']}")
        else:
            logger.info("ファイルログ: 無効")
    
    def get_log_stats(self) -> Dict[str, Any]:
        """ログシステムの統計情報を取得"""
        stats = {
            'console_level': self.log_config['console_level'],
            'file_logging_enabled': self.log_config['enable_file_logging'],
            'log_directory': self.log_config['log_dir'],
            'active_loggers': list(self.loggers.keys())
        }
        
        if self.log_config['enable_file_logging']:
            stats.update({
                'file_level': self.log_config['file_level'],
                'max_file_size_mb': self.log_config['max_file_size_mb'],
                'backup_count': self.log_config['backup_count']
            })
            
            # ログファイルのサイズ情報
            log_file = Path(self.log_config['log_dir']) / f"{self.app_name}.log"
            if log_file.exists():
                stats['current_log_file_size_mb'] = round(log_file.stat().st_size / (1024 * 1024), 2)
            else:
                stats['current_log_file_size_mb'] = 0
        
        return stats


class StructuredLogger:
    """構造化ログ出力のためのヘルパークラス"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def debug(self, message: str, **kwargs):
        """DEBUG レベルのログ出力"""
        self._log_with_context(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """INFO レベルのログ出力"""
        self._log_with_context(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """WARNING レベルのログ出力"""
        self._log_with_context(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """ERROR レベルのログ出力"""
        self._log_with_context(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """CRITICAL レベルのログ出力"""
        self._log_with_context(logging.CRITICAL, message, **kwargs)
    
    def _log_with_context(self, level: int, message: str, **kwargs):
        """コンテキスト情報付きログ出力"""
        if kwargs:
            context_parts = []
            for key, value in kwargs.items():
                context_parts.append(f"{key}={value}")
            context_str = " | ".join(context_parts)
            full_message = f"{message} | {context_str}"
        else:
            full_message = message
        
        self.logger.log(level, full_message)


def setup_logging(config: Dict[str, Any], app_name: str = "doc_to_md") -> LoggingManager:
    """ログシステムのセットアップ（統合関数）"""
    return LoggingManager(config, app_name)