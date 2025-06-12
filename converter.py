"""
HTMLからMarkdown変換機能
"""

import os
import re
import requests
from pathlib import Path
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import html2text
from crawler import WebCrawler


class MarkdownConverter:
    def __init__(self, config):
        self.config = config
        self.crawler = WebCrawler(config)
        self.html2text = html2text.HTML2Text()
        self._setup_html2text()
        
    def _setup_html2text(self):
        """html2textの設定"""
        self.html2text.ignore_links = False
        self.html2text.ignore_images = False
        self.html2text.body_width = 0  # 行の折り返しを無効化
        self.html2text.unicode_snob = True
        self.html2text.escape_snob = True
        
    def _extract_content(self, html_content):
        """HTMLからメインコンテンツを抽出"""
        soup = BeautifulSoup(html_content, 'lxml')
        
        # コンテンツセレクターで指定された要素を取得
        content_selector = self.config['extractor']['content_selector']
        content_elements = soup.select(content_selector)
        
        if not content_elements:
            print("警告: コンテンツが見つかりませんでした")
            return None
            
        # 最初の要素を使用
        main_content = content_elements[0]
        return str(main_content)
    
    def _process_images(self, html_content, base_url):
        """画像の処理（ダウンロードまたはURL調整）"""
        soup = BeautifulSoup(html_content, 'lxml')
        
        for img in soup.find_all('img'):
            src = img.get('src')
            if not src:
                continue
                
            # 相対URLを絶対URLに変換
            absolute_url = urljoin(base_url, src)
            
            if self.config['output']['download_images']:
                # 画像をダウンロード
                local_path = self._download_image(absolute_url)
                if local_path:
                    img['src'] = local_path
            else:
                # 絶対URLに変換
                img['src'] = absolute_url
        
        return str(soup)
    
    def _download_image(self, image_url):
        """画像をダウンロード"""
        try:
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            # ファイル名を生成
            parsed_url = urlparse(image_url)
            filename = os.path.basename(parsed_url.path)
            if not filename or not any(filename.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.svg']):
                filename = f"image_{hash(image_url) % 10000}.jpg"
            
            # 保存先のパスを作成
            image_dir = Path(self.config['output']['base_dir']) / self.config['output']['image_dir_name']
            image_dir.mkdir(parents=True, exist_ok=True)
            
            image_path = image_dir / filename
            
            # 画像を保存
            with open(image_path, 'wb') as f:
                f.write(response.content)
            
            # 相対パスを返す
            return f"./{self.config['output']['image_dir_name']}/{filename}"
            
        except Exception as e:
            print(f"警告: 画像のダウンロードに失敗しました {image_url}: {e}")
            return None
    
    def _url_to_file_path(self, url):
        """URLをファイルパスに変換"""
        parsed_url = urlparse(url)
        path = parsed_url.path
        
        # パスの正規化
        if path.endswith('/'):
            path = path[:-1]
        
        if path.endswith('/index.html'):
            path = path[:-11]  # '/index.html'を削除
        elif path.endswith('.html'):
            path = path[:-5]   # '.html'を削除
        
        # ファイル名を生成
        if not path or path == '/':
            filename = "index.md"
        else:
            filename = f"{path.lstrip('/')}.md"
        
        return filename
    
    def _save_markdown(self, content, url):
        """Markdownファイルを保存"""
        filename = self._url_to_file_path(url)
        file_path = Path(self.config['output']['base_dir']) / filename
        
        # ディレクトリを作成
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # ファイルを保存
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return file_path
    
    def process_page(self, url):
        """ページを処理してMarkdownに変換・保存"""
        # ページの内容を取得
        html_content = self.crawler.get_page_content(url)
        if html_content is None:
            return None
        
        # メインコンテンツを抽出
        main_content = self._extract_content(html_content)
        if main_content is None:
            return None
        
        # 画像を処理
        processed_content = self._process_images(main_content, url)
        
        # Markdownに変換
        markdown_content = self.html2text.handle(processed_content)
        
        # ファイルに保存
        file_path = self._save_markdown(markdown_content, url)
        
        return file_path