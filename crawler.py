"""
Webクローリングとリンク発見機能
"""

import requests
import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from collections import deque


class WebCrawler:
    def __init__(self, config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.visited_urls = set()
        self.url_queue = deque()
        
    def _is_valid_url(self, url):
        """URLが有効かどうかをチェック"""
        if not url or url in self.visited_urls:
            return False
            
        # 許可されたドメインのチェック
        allowed_domain = self.config['target_site']['allowed_domain']
        if not url.startswith(allowed_domain):
            return False
            
        # 除外パターンのチェック
        exclude_patterns = self.config['crawler']['exclude_patterns']
        for pattern in exclude_patterns:
            if re.search(pattern, url):
                return False
                
        return True
    
    def _extract_links(self, url, html_content):
        """HTMLからリンクを抽出"""
        soup = BeautifulSoup(html_content, 'lxml')
        links = []
        
        # ナビゲーションセレクターで指定された要素内のリンクを取得
        nav_selector = self.config['crawler']['navigation_selector']
        nav_elements = soup.select(nav_selector)
        
        for nav_element in nav_elements:
            for link in nav_element.find_all('a', href=True):
                href = link['href']
                # 相対URLを絶対URLに変換
                absolute_url = urljoin(url, href)
                
                if self._is_valid_url(absolute_url):
                    links.append(absolute_url)
        
        return links
    
    def _fetch_page(self, url):
        """ページを取得"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            return response.text
        except requests.RequestException as e:
            print(f"警告: {url} の取得に失敗しました: {e}")
            return None
    
    def crawl(self):
        """クロール実行"""
        start_url = self.config['target_site']['start_url']
        self.url_queue.append(start_url)
        crawled_urls = []
        
        while self.url_queue:
            current_url = self.url_queue.popleft()
            
            if current_url in self.visited_urls:
                continue
                
            print(f"クロール中: {current_url}")
            
            # ページを取得
            html_content = self._fetch_page(current_url)
            if html_content is None:
                continue
            
            # 訪問済みとしてマーク
            self.visited_urls.add(current_url)
            crawled_urls.append(current_url)
            
            # リンクを抽出してキューに追加
            links = self._extract_links(current_url, html_content)
            for link in links:
                if link not in self.visited_urls:
                    self.url_queue.append(link)
        
        return crawled_urls
    
    def get_page_content(self, url):
        """指定されたURLのページ内容を取得（converter用）"""
        return self._fetch_page(url)