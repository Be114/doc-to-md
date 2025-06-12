"""
Webクローリングとリンク発見機能
"""

import requests
import re
import time
import logging
from urllib.parse import urljoin, urlparse, urlunparse
from bs4 import BeautifulSoup
from collections import deque
import heapq
from typing import Set, List, Dict, Optional, Tuple


class URLPriorityQueue:
    """優先度付きURLキュー"""
    
    def __init__(self):
        self._queue = []
        self._index = 0
    
    def put(self, url: str, priority: int = 0):
        """URLをキューに追加（優先度が低い数字ほど高優先度）"""
        heapq.heappush(self._queue, (priority, self._index, url))
        self._index += 1
    
    def get(self) -> Optional[str]:
        """キューからURLを取得"""
        if self._queue:
            _, _, url = heapq.heappop(self._queue)
            return url
        return None
    
    def empty(self) -> bool:
        """キューが空かどうか"""
        return len(self._queue) == 0
    
    def size(self) -> int:
        """キューのサイズ"""
        return len(self._queue)


class WebCrawler:
    def __init__(self, config):
        self.config = config
        self._setup_session()
        self._setup_logging()
        
        # URL管理
        self.visited_urls: Set[str] = set()
        self.normalized_urls: Dict[str, str] = {}  # 正規化URL -> 元URL
        self.url_queue = URLPriorityQueue()
        
        # 統計情報
        self.stats = {
            'total_crawled': 0,
            'total_failed': 0,
            'total_skipped': 0
        }
        
    def _setup_session(self):
        """HTTPセッションの設定"""
        self.session = requests.Session()
        
        # User-Agentの設定
        user_agent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        self.session.headers.update({
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # リトライ設定
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def _setup_logging(self):
        """ログの設定"""
        self.logger = logging.getLogger('web_crawler')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def _normalize_url(self, url: str) -> str:
        """URLを正規化（重複検出用）"""
        try:
            parsed = urlparse(url)
            
            # クエリパラメータとフラグメントを除去
            normalized = urlunparse((
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path.rstrip('/') if parsed.path != '/' else '/',
                '',  # params
                '',  # query
                ''   # fragment
            ))
            
            return normalized
        except Exception:
            return url.lower()
    
    def _is_valid_url(self, url: str) -> Tuple[bool, str]:
        """URLが有効かどうかをチェック"""
        if not url:
            return False, "空のURL"
        
        # URL正規化
        normalized_url = self._normalize_url(url)
        
        # 重複チェック
        if normalized_url in self.normalized_urls:
            return False, "重複URL"
        
        # 許可されたドメインのチェック
        target_config = self.config.get('target_site', {})
        allowed_domain = target_config.get('allowed_domain', '')
        
        if allowed_domain and not url.startswith(allowed_domain):
            return False, f"許可されていないドメイン: {allowed_domain}"
        
        # 除外パターンのチェック
        crawler_config = self.config.get('crawler', {})
        exclude_patterns = crawler_config.get('exclude_patterns', [])
        
        for pattern in exclude_patterns:
            try:
                if re.search(pattern, url):
                    return False, f"除外パターンに一致: {pattern}"
            except re.error as e:
                self.logger.warning(f"無効な正規表現パターン '{pattern}': {e}")
                continue
        
        return True, "有効"
    
    def _extract_links(self, url: str, html_content: str) -> List[Tuple[str, int]]:
        """HTMLからリンクを抽出（優先度付き）"""
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            links = []
            
            # ナビゲーションセレクターで指定された要素内のリンクを取得
            crawler_config = self.config.get('crawler', {})
            nav_selector = crawler_config.get('navigation_selector', 'nav')
            nav_elements = soup.select(nav_selector)
            
            if not nav_elements:
                self.logger.warning(f"ナビゲーション要素が見つかりません: {nav_selector}")
                return links
            
            for nav_element in nav_elements:
                for link in nav_element.find_all('a', href=True):
                    href = link.get('href', '').strip()
                    if not href:
                        continue
                    
                    # 相対URLを絶対URLに変換
                    try:
                        absolute_url = urljoin(url, href)
                    except Exception as e:
                        self.logger.warning(f"URL結合エラー: {url} + {href}: {e}")
                        continue
                    
                    # URL検証
                    is_valid, reason = self._is_valid_url(absolute_url)
                    if is_valid:
                        # 優先度を決定（深さベースの簡単な優先度）
                        priority = self._calculate_priority(absolute_url, link)
                        links.append((absolute_url, priority))
                    else:
                        self.logger.debug(f"スキップ: {absolute_url} - {reason}")
            
            return links
            
        except Exception as e:
            self.logger.error(f"リンク抽出エラー {url}: {e}")
            return []
    
    def _calculate_priority(self, url: str, link_element) -> int:
        """リンクの優先度を計算"""
        priority = 10  # デフォルト優先度
        
        # パスの深さで優先度を調整（浅いほど高優先度）
        path_depth = url.count('/') - 3  # http://example.com/ = 3
        priority += path_depth
        
        # リンクテキストで優先度を調整
        link_text = link_element.get_text(strip=True).lower()
        high_priority_keywords = ['index', 'overview', 'introduction', 'getting-started']
        low_priority_keywords = ['appendix', 'reference', 'changelog', 'history']
        
        if any(keyword in link_text for keyword in high_priority_keywords):
            priority -= 5  # 高優先度
        elif any(keyword in link_text for keyword in low_priority_keywords):
            priority += 5  # 低優先度
        
        return max(0, priority)
    
    def _fetch_page(self, url: str) -> Optional[str]:
        """ページを取得（リトライ機能付き）"""
        try:
            self.logger.info(f"ページ取得中: {url}")
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # エンコーディングの適切な設定
            if response.encoding == 'ISO-8859-1' and 'charset' not in response.headers.get('content-type', ''):
                response.encoding = response.apparent_encoding
            
            return response.text
            
        except requests.exceptions.Timeout:
            self.logger.warning(f"タイムアウト: {url}")
            self.stats['total_failed'] += 1
            return None
        except requests.exceptions.RequestException as e:
            self.logger.warning(f"リクエストエラー: {url} - {e}")
            self.stats['total_failed'] += 1
            return None
        except Exception as e:
            self.logger.error(f"予期しないエラー: {url} - {e}")
            self.stats['total_failed'] += 1
            return None
    
    def crawl(self) -> List[str]:
        """クロール実行"""
        target_config = self.config.get('target_site', {})
        execution_config = self.config.get('execution', {})
        
        start_url = target_config.get('start_url', '')
        request_delay = execution_config.get('request_delay', 1.0)
        
        if not start_url:
            self.logger.error("start_urlが設定されていません")
            return []
        
        self.logger.info(f"クロール開始: {start_url}")
        
        # 開始URLをキューに追加
        self.url_queue.put(start_url, priority=0)
        crawled_urls = []
        
        while not self.url_queue.empty():
            current_url = self.url_queue.get()
            
            # 正規化URLで重複チェック
            normalized_url = self._normalize_url(current_url)
            if normalized_url in self.normalized_urls:
                self.stats['total_skipped'] += 1
                continue
            
            # ページを取得
            html_content = self._fetch_page(current_url)
            if html_content is None:
                continue
            
            # 訪問済みとしてマーク
            self.normalized_urls[normalized_url] = current_url
            self.visited_urls.add(current_url)
            crawled_urls.append(current_url)
            self.stats['total_crawled'] += 1
            
            self.logger.info(f"[{self.stats['total_crawled']}] 処理完了: {current_url}")
            
            # リンクを抽出してキューに追加
            links = self._extract_links(current_url, html_content)
            added_count = 0
            
            for link_url, priority in links:
                normalized_link = self._normalize_url(link_url)
                if normalized_link not in self.normalized_urls:
                    self.url_queue.put(link_url, priority)
                    added_count += 1
            
            if added_count > 0:
                self.logger.debug(f"新しいリンクを{added_count}個追加")
            
            # リクエスト間隔の調整
            if request_delay > 0 and not self.url_queue.empty():
                time.sleep(request_delay)
        
        self.log_crawl_summary(crawled_urls)
        return crawled_urls
    
    def log_crawl_summary(self, crawled_urls: List[str]):
        """クロール結果のサマリーをログ出力"""
        self.logger.info("=== クロール完了 ===")
        self.logger.info(f"成功: {self.stats['total_crawled']} ページ")
        self.logger.info(f"失敗: {self.stats['total_failed']} ページ")
        self.logger.info(f"スキップ: {self.stats['total_skipped']} ページ")
        self.logger.info(f"合計: {len(crawled_urls)} ページを収集")
        
        if crawled_urls:
            self.logger.info("収集したURL一覧:")
            for i, url in enumerate(crawled_urls, 1):
                self.logger.info(f"  {i:3d}. {url}")
    
    def get_page_content(self, url: str) -> Optional[str]:
        """指定されたURLのページ内容を取得（converter用）"""
        return self._fetch_page(url)
    
    def normalize_url(self, url: str) -> str:
        """Public method to normalize URLs"""
        return self._normalize_url(url)
    
    def extract_links_from_content(self, url: str, html_content: str) -> List[Tuple[str, int]]:
        """Public method to extract links from HTML content"""
        return self._extract_links(url, html_content)
    
    def mark_url_as_visited(self, url: str):
        """Mark a URL as visited"""
        normalized = self._normalize_url(url)
        if normalized not in self.normalized_urls:
            self.normalized_urls[normalized] = url
            self.visited_urls.add(url)
            self.stats['total_crawled'] += 1
    
    def is_url_visited(self, url: str) -> bool:
        """Check if a URL has been visited"""
        normalized = self._normalize_url(url)
        return normalized in self.normalized_urls
    
    def fetch_page(self, url: str) -> Optional[str]:
        """Public method to fetch a page"""
        return self._fetch_page(url)
    
    def get_stats(self) -> Dict[str, int]:
        """統計情報を取得"""
        return self.stats.copy()
    
