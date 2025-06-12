"""
Webクローリングとリンク発見機能
"""

import requests
import re
import time
import logging
from urllib.parse import urljoin, urlparse, urlunparse
from bs4 import BeautifulSoup
import heapq
from typing import Set, List, Dict, Optional, Tuple


class URLPriorityQueue:
    """優先度付きURLキュー"""
    
    def __init__(self):
        """
        Initializes an empty priority queue for managing URLs.
        """
        self._queue = []
        self._index = 0
    
    def put(self, url: str, priority: int = 0):
        """
        Adds a URL to the priority queue with the specified priority.
        
        A lower priority value indicates higher priority for retrieval.
        """
        heapq.heappush(self._queue, (priority, self._index, url))
        self._index += 1
    
    def get(self) -> Optional[str]:
        """
        Retrieves and removes the highest priority URL from the queue.
        
        Returns:
            The URL with the highest priority, or None if the queue is empty.
        """
        if self._queue:
            _, _, url = heapq.heappop(self._queue)
            return url
        return None
    
    def empty(self) -> bool:
        """
        Checks whether the priority queue is empty.
        
        Returns:
            True if the queue contains no URLs; otherwise, False.
        """
        return len(self._queue) == 0
    
    def size(self) -> int:
        """
        Returns the number of URLs currently in the priority queue.
        """
        return len(self._queue)


class WebCrawler:
    def __init__(self, config):
        """
        Initializes the WebCrawler with the provided configuration.
        
        Sets up the HTTP session, logging, URL tracking structures, priority queue, and crawl statistics.
        """
        self.config = config
        self._setup_session()
        self._setup_logging()
        
        # URL管理
        self.visited_urls: Set[str] = set()
        self.normalized_urls: Dict[str, str] = {}  # 正規化URL -> 元URL
        self.queued_normalized: Set[str] = set()  # キュー済みURL（重複防止）
        self.url_queue = URLPriorityQueue()
        
        # 統計情報
        self.stats = {
            'total_crawled': 0,
            'total_failed': 0,
            'total_skipped': 0
        }
        
    def _setup_session(self):
        """
        Configures the HTTP session with custom headers and retry strategy.
        
        Sets up the session to use a specific User-Agent, appropriate Accept headers, and enables automatic retries for certain HTTP status codes.
        """
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
        """
        Configures the logger for the web crawler.
        
        Initializes a logger named 'web_crawler' with a stream handler and a standard formatter if not already set up.
        """
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
        """
        Normalizes a URL for duplicate detection.
        
        Converts the scheme and network location to lowercase, removes query parameters and fragments, and trims trailing slashes from the path except for the root. Returns a lowercase fallback if normalization fails.
        """
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
        """
        Checks whether a URL is valid for crawling based on normalization, duplication, domain, and exclusion patterns.
        
        Returns:
            A tuple containing a boolean indicating validity and a string describing the reason.
        """
        if not url:
            return False, "空のURL"
        
        # URL正規化
        normalized_url = self._normalize_url(url)
        
        # 重複チェック
        if normalized_url in self.normalized_urls:
            return False, "重複URL"
        
        # 許可されたドメインのチェック
        target_config = self.config.get('target_site', {})
        allowed_domain = target_config.get('allowed_domain', '').lower()
        
        if allowed_domain:
            try:
                url_netloc = urlparse(url).netloc.lower()
                allowed_netloc = urlparse(allowed_domain).netloc.lower()
                if url_netloc != allowed_netloc:
                    return False, f"許可されていないドメイン: {allowed_domain}"
            except Exception:
                return False, "ドメイン解析エラー"
        
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
        """
        Extracts and prioritizes links from navigation elements in HTML content.
        
        Parses the provided HTML, selects navigation elements based on a configurable CSS selector, and extracts all anchor tags with href attributes. Converts relative URLs to absolute URLs, validates each URL, and assigns a priority score to each valid link. Returns a list of tuples containing the absolute URL and its priority.
        """
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            links = []
            
            # ナビゲーションセレクターで指定された要素内のリンクを取得
            crawler_config = self.config.get('crawler', {})
            nav_selector = crawler_config.get('navigation_selector', 'nav')
            nav_elements = soup.select(nav_selector)
            
            if not nav_elements:
                self.logger.warning(f"ナビゲーション要素が見つかりません: {nav_selector}")
                # フォールバック: ページ内のすべてのリンクを対象にする
                self.logger.info("フォールバック: ページ内のすべてのリンクを検索します")
                nav_elements = [soup]
            
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
        """
        Calculates the priority score for a link based on its URL path depth and link text.
        
        The priority is lower for links with shallow paths and for those whose text contains high-priority keywords, and higher for links with deep paths or low-priority keywords. The returned priority is always non-negative.
        
        Args:
            url: The absolute URL of the link.
            link_element: The BeautifulSoup element representing the anchor tag.
        
        Returns:
            An integer representing the calculated priority (lower values indicate higher priority).
        """
        priority = 10  # デフォルト優先度
        
        # パスの深さで優先度を調整（浅いほど高優先度）
        parsed_url = urlparse(url)
        path = parsed_url.path or '/'
        path_depth = max(0, path.rstrip('/').count('/'))
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
        """
        Fetches the content of a web page with retry and timeout handling.
        
        Attempts to retrieve the specified URL using the configured HTTP session. Handles timeouts, HTTP errors, and unexpected exceptions. Adjusts response encoding if necessary. Updates failure statistics and logs relevant events.
        
        Args:
            url: The URL of the web page to fetch.
        
        Returns:
            The page content as a string if successful, or None if the request fails.
        """
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
        """
        Performs a prioritized web crawl starting from the configured URL.
        
        Retrieves the start URL from the configuration, manages the crawl using a priority queue, fetches and processes each page, extracts and queues new links, and tracks crawl statistics. Returns a list of successfully crawled URLs.
        """
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
                if normalized_link not in self.normalized_urls and normalized_link not in self.queued_normalized:
                    self.url_queue.put(link_url, priority)
                    self.queued_normalized.add(normalized_link)
                    added_count += 1
            
            if added_count > 0:
                self.logger.debug(f"新しいリンクを{added_count}個追加")
            
            # リクエスト間隔の調整
            if request_delay > 0 and not self.url_queue.empty():
                time.sleep(request_delay)
        
        self._log_crawl_summary(crawled_urls)
        return crawled_urls
    
    def _log_crawl_summary(self, crawled_urls: List[str]):
        """
        Logs a summary of the crawl results, including counts of successful, failed, and skipped pages, and lists all collected URLs.
        """
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
        """
        Fetches the content of the specified URL.
        
        Returns:
            The page content as a string if successful, or None if the fetch fails.
        """
        return self._fetch_page(url)
    
    def get_stats(self) -> Dict[str, int]:
        """
        Returns a copy of the current crawl statistics.
        
        The statistics include counts of successfully crawled, failed, and skipped pages.
        """
        return self.stats.copy()