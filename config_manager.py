"""
設定管理クラス
設定ファイルの読み込み、検証、デフォルト値の提供を行う
"""

import os
import sys
import yaml
import re
from typing import Dict, Any, List, Optional
from pathlib import Path
from error_types import ErrorHandler, ConfigError, ErrorSeverity
import logging


class ConfigValidationError(Exception):
    """設定検証エラー"""
    pass


class ConfigManager:
    """設定管理クラス"""
    
    # デフォルト設定
    DEFAULT_CONFIG = {
        'target_site': {
            'start_url': '',
            'allowed_domain': ''
        },
        'crawler': {
            'navigation_selector': 'nav',
            'exclude_patterns': [
                r'.*#.*',           # アンカーリンク
                r'.*/search\.html', # 検索ページ
                r'.*/genindex\.html' # インデックスページ
            ]
        },
        'extractor': {
            'content_selector': 'main'
        },
        'output': {
            'base_dir': './output',
            'image_dir_name': 'images',
            'download_images': True
        },
        'execution': {
            'request_delay': 1.0
        },
        'logging': {
            'console_level': 'INFO',
            'file_level': 'DEBUG',
            'log_dir': './logs',
            'max_file_size_mb': 5,
            'backup_count': 5,
            'enable_file_logging': True,
            'log_format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'date_format': '%Y-%m-%d %H:%M:%S'
        }
    }
    
    # 必須設定項目
    REQUIRED_CONFIG_KEYS = [
        'target_site.start_url',
        'target_site.allowed_domain',
        'crawler.navigation_selector',
        'extractor.content_selector',
        'output.base_dir'
    ]
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        
        # ログとエラーハンドラーの初期化
        self.logger = logging.getLogger('config_manager')
        self.error_handler = ErrorHandler(self.logger)
        
        self.config = self._load_and_validate_config()
    
    def _load_config_file(self) -> Dict[str, Any]:
        """設定ファイルを読み込む"""
        if not os.path.exists(self.config_path):
            error = ConfigError(
                message=f"設定ファイル '{self.config_path}' が見つかりません",
                severity=ErrorSeverity.CRITICAL
            )
            self.error_handler.handle_error(error)
            raise FileNotFoundError(f"設定ファイル '{self.config_path}' が見つかりません")
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            error = ConfigError(
                message=f"設定ファイルの読み込みに失敗しました: {e}",
                severity=ErrorSeverity.CRITICAL,
                original_exception=e
            )
            self.error_handler.handle_error(error)
            raise ConfigValidationError(f"設定ファイルの読み込みに失敗しました: {e}")
        except Exception as e:
            error = ConfigError(
                message=f"設定ファイルの読み込み中にエラーが発生しました: {e}",
                severity=ErrorSeverity.CRITICAL,
                original_exception=e
            )
            self.error_handler.handle_error(error)
            raise ConfigValidationError(f"設定ファイルの読み込み中にエラーが発生しました: {e}")
    
    def _merge_with_defaults(self, user_config: Dict[str, Any]) -> Dict[str, Any]:
        """ユーザー設定とデフォルト設定をマージ"""
        def deep_merge(default: Dict, user: Dict) -> Dict:
            merged = default.copy()
            for key, value in user.items():
                if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                    merged[key] = deep_merge(merged[key], value)
                else:
                    merged[key] = value
            return merged
        
        return deep_merge(self.DEFAULT_CONFIG, user_config)
    
    def _get_nested_value(self, config: Dict[str, Any], key_path: str) -> Any:
        """ネストした設定値を取得"""
        keys = key_path.split('.')
        value = config
        for key in keys:
            if not isinstance(value, dict) or key not in value:
                return None
            value = value[key]
        return value
    
    def _validate_required_keys(self, config: Dict[str, Any]) -> None:
        """必須キーの存在チェック"""
        missing_keys = []
        for key_path in self.REQUIRED_CONFIG_KEYS:
            value = self._get_nested_value(config, key_path)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing_keys.append(key_path)
        
        if missing_keys:
            error = ConfigError(
                message=f"必須設定項目が不足しています: {', '.join(missing_keys)}",
                severity=ErrorSeverity.CRITICAL
            )
            self.error_handler.handle_error(error)
            raise ConfigValidationError(f"必須設定項目が不足しています: {', '.join(missing_keys)}")
    
    def _validate_types(self, config: Dict[str, Any]) -> None:
        """型チェック"""
        type_checks = [
            ('target_site.start_url', str),
            ('target_site.allowed_domain', str),
            ('crawler.navigation_selector', str),
            ('crawler.exclude_patterns', list),
            ('extractor.content_selector', str),
            ('output.base_dir', str),
            ('output.image_dir_name', str),
            ('output.download_images', bool),
            ('execution.request_delay', (int, float)),
            ('logging.console_level', str),
            ('logging.file_level', str),
            ('logging.log_dir', str),
            ('logging.max_file_size_mb', (int, float)),
            ('logging.backup_count', int),
            ('logging.enable_file_logging', bool),
            ('logging.log_format', str),
            ('logging.date_format', str)
        ]
        
        for key_path, expected_type in type_checks:
            value = self._get_nested_value(config, key_path)
            if value is not None and not isinstance(value, expected_type):
                error_msg = (
                    f"設定項目 '{key_path}' の型が正しくありません。"
                    f"期待される型: {expected_type.__name__ if hasattr(expected_type, '__name__') else expected_type}, "
                    f"実際の型: {type(value).__name__}"
                )
                error = ConfigError(
                    message=error_msg,
                    severity=ErrorSeverity.CRITICAL
                )
                self.error_handler.handle_error(error)
                raise ConfigValidationError(error_msg)
    
    def _validate_values(self, config: Dict[str, Any]) -> None:
        """値の妥当性チェック"""
        # URLの形式チェック
        start_url = self._get_nested_value(config, 'target_site.start_url')
        if start_url and not (start_url.startswith('http://') or start_url.startswith('https://')):
            error = ConfigError(
                message="start_urlは有効なHTTP/HTTPSのURLである必要があります",
                severity=ErrorSeverity.CRITICAL
            )
            self.error_handler.handle_error(error)
            raise ConfigValidationError("start_urlは有効なHTTP/HTTPSのURLである必要があります")
        
        allowed_domain = self._get_nested_value(config, 'target_site.allowed_domain')
        if allowed_domain and not (allowed_domain.startswith('http://') or allowed_domain.startswith('https://')):
            error = ConfigError(
                message="allowed_domainは有効なHTTP/HTTPSのURLである必要があります",
                severity=ErrorSeverity.CRITICAL
            )
            self.error_handler.handle_error(error)
            raise ConfigValidationError("allowed_domainは有効なHTTP/HTTPSのURLである必要があります")
        
        # リクエスト遅延の範囲チェック
        request_delay = self._get_nested_value(config, 'execution.request_delay')
        if request_delay is not None:
            if request_delay < 0:
                error = ConfigError(
                    message="request_delayは0以上の値である必要があります",
                    severity=ErrorSeverity.CRITICAL
                )
                self.error_handler.handle_error(error)
                raise ConfigValidationError("request_delayは0以上の値である必要があります")
            if request_delay > 60:
                error = ConfigError(
                    message="request_delayは60秒以下である必要があります",
                    severity=ErrorSeverity.HIGH
                )
                self.error_handler.handle_error(error)
                raise ConfigValidationError("request_delayは60秒以下である必要があります")
        
        # 除外パターンの正規表現チェック
        exclude_patterns = self._get_nested_value(config, 'crawler.exclude_patterns')
        if exclude_patterns:
            for pattern in exclude_patterns:
                try:
                    re.compile(pattern)
                except re.error as e:
                    error = ConfigError(
                        message=f"除外パターン '{pattern}' は有効な正規表現ではありません: {e}",
                        severity=ErrorSeverity.CRITICAL,
                        original_exception=e
                    )
                    self.error_handler.handle_error(error)
                    raise ConfigValidationError(f"除外パターン '{pattern}' は有効な正規表現ではありません: {e}")
        
        # ログレベルの妥当性チェック
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        
        console_level = self._get_nested_value(config, 'logging.console_level')
        if console_level and console_level.upper() not in valid_log_levels:
            error = ConfigError(
                message=f"logging.console_levelは有効なログレベルである必要があります: {', '.join(valid_log_levels)}",
                severity=ErrorSeverity.CRITICAL
            )
            self.error_handler.handle_error(error)
            raise ConfigValidationError(f"logging.console_levelは有効なログレベルである必要があります: {', '.join(valid_log_levels)}")
        
        file_level = self._get_nested_value(config, 'logging.file_level')
        if file_level and file_level.upper() not in valid_log_levels:
            error = ConfigError(
                message=f"logging.file_levelは有効なログレベルである必要があります: {', '.join(valid_log_levels)}",
                severity=ErrorSeverity.CRITICAL
            )
            self.error_handler.handle_error(error)
            raise ConfigValidationError(f"logging.file_levelは有効なログレベルである必要があります: {', '.join(valid_log_levels)}")
        
        # ログファイルサイズとバックアップ数のチェック
        max_file_size = self._get_nested_value(config, 'logging.max_file_size_mb')
        if max_file_size is not None:
            if max_file_size <= 0:
                error = ConfigError(
                    message="logging.max_file_size_mbは正の値である必要があります",
                    severity=ErrorSeverity.CRITICAL
                )
                self.error_handler.handle_error(error)
                raise ConfigValidationError("logging.max_file_size_mbは正の値である必要があります")
            if max_file_size > 100:
                error = ConfigError(
                    message="logging.max_file_size_mbは100MB以下である必要があります",
                    severity=ErrorSeverity.HIGH
                )
                self.error_handler.handle_error(error)
                raise ConfigValidationError("logging.max_file_size_mbは100MB以下である必要があります")
        
        backup_count = self._get_nested_value(config, 'logging.backup_count')
        if backup_count is not None:
            if backup_count < 0:
                error = ConfigError(
                    message="logging.backup_countは0以上の値である必要があります",
                    severity=ErrorSeverity.CRITICAL
                )
                self.error_handler.handle_error(error)
                raise ConfigValidationError("logging.backup_countは0以上の値である必要があります")
            if backup_count > 20:
                error = ConfigError(
                    message="logging.backup_countは20以下である必要があります",
                    severity=ErrorSeverity.HIGH
                )
                self.error_handler.handle_error(error)
                raise ConfigValidationError("logging.backup_countは20以下である必要があります")
    
    def _validate_config(self, config: Dict[str, Any]) -> None:
        """設定の検証"""
        self._validate_required_keys(config)
        self._validate_types(config)
        self._validate_values(config)
    
    def _load_and_validate_config(self) -> Dict[str, Any]:
        """設定ファイルの読み込みと検証"""
        try:
            # 設定ファイルを読み込み
            user_config = self._load_config_file()
            
            # デフォルト設定とマージ
            merged_config = self._merge_with_defaults(user_config)
            
            # 設定を検証
            self._validate_config(merged_config)
            
            return merged_config
            
        except (FileNotFoundError, ConfigValidationError) as e:
            # エラーは既にハンドラーでログ出力済み
            print(f"設定エラー: {e}")
            sys.exit(1)
        except Exception as e:
            error = ConfigError(
                message=f"予期しないエラーが発生しました: {e}",
                severity=ErrorSeverity.CRITICAL,
                original_exception=e
            )
            self.error_handler.handle_error(error)
            print(f"予期しないエラーが発生しました: {e}")
            sys.exit(1)
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """設定値を取得"""
        value = self._get_nested_value(self.config, key_path)
        return value if value is not None else default
    
    def get_target_site(self) -> Dict[str, str]:
        """対象サイト設定を取得"""
        return self.config['target_site']
    
    def get_crawler_config(self) -> Dict[str, Any]:
        """クローラー設定を取得"""
        return self.config['crawler']
    
    def get_extractor_config(self) -> Dict[str, str]:
        """抽出器設定を取得"""
        return self.config['extractor']
    
    def get_output_config(self) -> Dict[str, Any]:
        """出力設定を取得"""
        return self.config['output']
    
    def get_execution_config(self) -> Dict[str, Any]:
        """実行設定を取得"""
        return self.config['execution']
    
    def get_logging_config(self) -> Dict[str, Any]:
        """ログ設定を取得"""
        return self.config['logging']
    
    def print_config(self) -> None:
        """現在の設定を表示（デバッグ用）"""
        print("現在の設定:")
        print(yaml.dump(self.config, default_flow_style=False, allow_unicode=True, indent=2))