"""
中断・再開機能の管理
処理の進行状況を保存し、中断からの復旧を可能にする
"""

import json
import os
import time
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from datetime import datetime


class RecoveryState:
    """リカバリ状態を管理するクラス"""
    
    def __init__(self):
        self.start_url: str = ""
        self.visited_urls: Set[str] = set()
        self.failed_url_counts: Dict[str, int] = {}
        self.processed_count: int = 0
        self.success_count: int = 0
        self.failed_count: int = 0
        self.crawled_urls: List[str] = []
        self.timestamp: str = ""
        self.config_checksum: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """状態を辞書形式に変換"""
        return {
            'start_url': self.start_url,
            'visited_urls': list(self.visited_urls),
            'failed_url_counts': self.failed_url_counts,
            'processed_count': self.processed_count,
            'success_count': self.success_count,
            'failed_count': self.failed_count,
            'crawled_urls': self.crawled_urls,
            'timestamp': self.timestamp,
            'config_checksum': self.config_checksum
        }
    
    def from_dict(self, data: Dict[str, Any]):
        """辞書から状態を復元"""
        self.start_url = data.get('start_url', '')
        self.visited_urls = set(data.get('visited_urls', []))
        self.failed_url_counts = data.get('failed_url_counts', {})
        self.processed_count = data.get('processed_count', 0)
        self.success_count = data.get('success_count', 0)
        self.failed_count = data.get('failed_count', 0)
        self.crawled_urls = data.get('crawled_urls', [])
        self.timestamp = data.get('timestamp', '')
        self.config_checksum = data.get('config_checksum', '')


class RecoveryManager:
    """リカバリ機能の管理クラス"""
    
    def __init__(self, config: Dict[str, Any], logger: Optional[logging.Logger] = None):
        self.config = config
        self.recovery_config = config.get('recovery', {})
        self.logger = logger or logging.getLogger(__name__)
        
        self.recovery_file = Path(self.recovery_config.get('recovery_file', './recovery_state.json'))
        self.save_interval = self.recovery_config.get('save_interval', 10)
        self.enable_recovery = self.recovery_config.get('enable_recovery', True)
        
        self.state = RecoveryState()
        self.save_counter = 0
    
    def _calculate_config_checksum(self) -> str:
        """設定のチェックサムを計算"""
        # 設定の主要部分をJSON文字列化してハッシュ
        key_config = {
            'target_site': self.config.get('target_site', {}),
            'crawler': self.config.get('crawler', {}),
            'extractor': self.config.get('extractor', {}),
            'output': self.config.get('output', {})
        }
        import hashlib
        config_str = json.dumps(key_config, sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()
    
    def has_recovery_file(self) -> bool:
        """リカバリファイルが存在するかチェック"""
        return self.recovery_file.exists() and self.enable_recovery
    
    def can_resume(self) -> bool:
        """再開可能かどうかを判定"""
        if not self.has_recovery_file():
            return False
        
        try:
            with open(self.recovery_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            saved_checksum = data.get('config_checksum', '')
            current_checksum = self._calculate_config_checksum()
            
            if saved_checksum != current_checksum:
                self.logger.warning("設定が変更されているため、リカバリファイルは使用できません")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"リカバリファイルの検証に失敗: {e}")
            return False
    
    def load_state(self) -> bool:
        """保存された状態を読み込み"""
        if not self.can_resume():
            return False
        
        try:
            with open(self.recovery_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.state.from_dict(data)
            
            self.logger.info("=== リカバリ状態を読み込み ===")
            self.logger.info(f"前回の実行時刻: {self.state.timestamp}")
            self.logger.info(f"開始URL: {self.state.start_url}")
            self.logger.info(f"処理済みページ数: {self.state.processed_count}")
            self.logger.info(f"成功: {self.state.success_count}, 失敗: {self.state.failed_count}")
            self.logger.info(f"訪問済みURL数: {len(self.state.visited_urls)}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"リカバリ状態の読み込みに失敗: {e}")
            return False
    
    def save_state(self, 
                   start_url: str,
                   visited_urls: Set[str],
                   failed_url_counts: Dict[str, int],
                   processed_count: int,
                   success_count: int,
                   failed_count: int,
                   crawled_urls: List[str]):
        """現在の状態を保存"""
        if not self.enable_recovery:
            return
        
        self.save_counter += 1
        
        # 設定されたインターバルでのみ保存
        if self.save_counter % self.save_interval != 0:
            return
        
        try:
            self.state.start_url = start_url
            self.state.visited_urls = visited_urls.copy()
            self.state.failed_url_counts = failed_url_counts.copy()
            self.state.processed_count = processed_count
            self.state.success_count = success_count
            self.state.failed_count = failed_count
            self.state.crawled_urls = crawled_urls.copy()
            self.state.timestamp = datetime.now().isoformat()
            self.state.config_checksum = self._calculate_config_checksum()
            
            # 親ディレクトリを作成
            self.recovery_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 一時ファイルに書き込んでから置き換え（アトミック操作）
            temp_file = self.recovery_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.state.to_dict(), f, ensure_ascii=False, indent=2)
            
            temp_file.replace(self.recovery_file)
            
            self.logger.debug(f"リカバリ状態を保存: {processed_count}ページ処理済み")
            
        except Exception as e:
            self.logger.error(f"リカバリ状態の保存に失敗: {e}")
    
    def cleanup_recovery_file(self):
        """リカバリファイルを削除"""
        try:
            if self.recovery_file.exists():
                self.recovery_file.unlink()
                self.logger.info("リカバリファイルを削除しました")
        except Exception as e:
            self.logger.warning(f"リカバリファイルの削除に失敗: {e}")
    
    def get_resume_info(self) -> Dict[str, Any]:
        """再開情報を取得"""
        return {
            'can_resume': self.can_resume(),
            'recovery_file': str(self.recovery_file),
            'enable_recovery': self.enable_recovery,
            'state': self.state.to_dict() if self.state else {}
        }
    
    def force_save_current_state(self,
                                start_url: str,
                                visited_urls: Set[str],
                                failed_url_counts: Dict[str, int],
                                processed_count: int,
                                success_count: int,
                                failed_count: int,
                                crawled_urls: List[str]):
        """インターバルに関係なく現在の状態を強制保存"""
        original_counter = self.save_counter
        self.save_counter = self.save_interval - 1  # 次回保存されるように調整
        
        self.save_state(start_url, visited_urls, failed_url_counts, 
                       processed_count, success_count, failed_count, crawled_urls)
        
        self.save_counter = original_counter