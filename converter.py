"""
HTMLからMarkdown変換機能
"""

import os
import re
import requests
import logging
from pathlib import Path
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import html2text
from typing import Optional, Dict, Any


class MarkdownConverter:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._setup_html2text()
        self._setup_logging()
        self._setup_session()
        
        # 統計情報
        self.stats = {
            'total_processed': 0,
            'total_success': 0,
            'total_failed': 0,
            'images_downloaded': 0,
            'images_failed': 0
        }
        
    def _setup_html2text(self):
        """html2textの設定"""
        self.html2text = html2text.HTML2Text()
        
        # 基本設定
        self.html2text.ignore_links = False
        self.html2text.ignore_images = False
        self.html2text.body_width = 0  # 行の折り返しを無効化
        self.html2text.unicode_snob = True
        self.html2text.escape_snob = True
        
        # マークダウン出力の改善
        self.html2text.mark_code = True
        self.html2text.wrap_links = False
        self.html2text.bypass_tables = False
        self.html2text.ignore_emphasis = False
        self.html2text.skip_internal_links = False
        
        # リスト処理の改善
        self.html2text.ul_item_mark = '-'
        self.html2text.emphasis_mark = '*'
        self.html2text.strong_mark = '**'
    
    def _setup_logging(self):
        """ログの設定"""
        self.logger = logging.getLogger('markdown_converter')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def _setup_session(self):
        """HTTP セッションの設定"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
        })
        
        # リトライ設定
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        retry_strategy = Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
    def _get_config(self, key_path: str, default: Any = None) -> Any:
        """設定値を取得（ConfigManagerスタイル）"""
        keys = key_path.split('.')
        value = self.config
        for key in keys:
            if not isinstance(value, dict) or key not in value:
                return default
            value = value[key]
        return value
        
    def _extract_content(self, html_content: str) -> Optional[str]:
        """HTMLからメインコンテンツを抽出"""
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            
            # コンテンツセレクターで指定された要素を取得
            content_selector = self._get_config('extractor.content_selector', 'main')
            self.logger.debug(f"コンテンツセレクター: {content_selector}")
            
            content_elements = soup.select(content_selector)
            
            if not content_elements:
                self.logger.warning(f"コンテンツが見つかりませんでした。セレクター: {content_selector}")
                # フォールバック: body要素を使用
                content_elements = soup.select('body')
                if content_elements:
                    self.logger.info("フォールバック: body要素を使用します")
                else:
                    self.logger.error("body要素も見つかりませんでした")
                    return None
                    
            # 最初の要素を使用
            main_content = content_elements[0]
            
            # 不要な要素を除去
            self._clean_content(main_content)
            
            return str(main_content)
            
        except Exception as e:
            self.logger.error(f"コンテンツ抽出エラー: {e}")
            return None
    
    def _clean_content(self, content_element):
        """コンテンツから不要な要素を除去"""
        # 除去する要素のセレクター
        unwanted_selectors = [
            'script', 'style', 'nav', 'header', 'footer',
            '.advertisement', '.ads', '.social-share',
            '.breadcrumb', '.pagination', '#comments'
        ]
        
        for selector in unwanted_selectors:
            for element in content_element.select(selector):
                element.decompose()
    
    def _process_images(self, html_content: str, base_url: str) -> str:
        """画像の処理（ダウンロードまたはURL調整）"""
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            
            for img in soup.find_all('img'):
                src = img.get('src')
                if not src:
                    continue
                    
                # 相対URLを絶対URLに変換
                try:
                    absolute_url = urljoin(base_url, src)
                except Exception as e:
                    self.logger.warning(f"URL結合エラー: {base_url} + {src}: {e}")
                    continue
                
                download_images = self._get_config('output.download_images', True)
                
                if download_images:
                    # 画像をダウンロード
                    local_path = self._download_image(absolute_url)
                    if local_path:
                        img['src'] = local_path
                        self.stats['images_downloaded'] += 1
                    else:
                        # ダウンロード失敗時は絶対URLを設定
                        img['src'] = absolute_url
                        self.stats['images_failed'] += 1
                else:
                    # 絶対URLに変換
                    img['src'] = absolute_url
            
            return str(soup)
            
        except Exception as e:
            self.logger.error(f"画像処理エラー: {e}")
            return html_content
    
    def _download_image(self, image_url: str) -> Optional[str]:
        """画像をダウンロード"""
        try:
            self.logger.debug(f"画像ダウンロード中: {image_url}")
            
            # 画像URLの検証
            if not self._is_valid_image_url(image_url):
                self.logger.debug(f"無効な画像URL: {image_url}")
                return None
            
            response = self.session.get(image_url, timeout=15)
            response.raise_for_status()
            
            # コンテンツタイプの確認
            content_type = response.headers.get('content-type', '').lower()
            if not content_type.startswith('image/'):
                self.logger.warning(f"画像ではないコンテンツ: {content_type}")
                return None
            
            # ファイル名を生成
            filename = self._generate_image_filename(image_url, content_type)
            
            # 保存先のパスを作成
            output_config = self._get_config('output', {})
            base_dir = output_config.get('base_dir', './output')
            image_dir_name = output_config.get('image_dir_name', 'images')
            
            image_dir = Path(base_dir) / image_dir_name
            image_dir.mkdir(parents=True, exist_ok=True)
            
            image_path = image_dir / filename
            
            # ファイルサイズチェック（10MB制限）
            content_length = len(response.content)
            if content_length > 10 * 1024 * 1024:  # 10MB
                self.logger.warning(f"画像ファイルが大きすぎます: {content_length} bytes")
                return None
            
            # 画像を保存
            with open(image_path, 'wb') as f:
                f.write(response.content)
            
            # 相対パスを返す
            return f"./{image_dir_name}/{filename}"
            
        except requests.exceptions.Timeout:
            self.logger.warning(f"画像ダウンロードタイムアウト: {image_url}")
            return None
        except requests.exceptions.RequestException as e:
            self.logger.warning(f"画像ダウンロードエラー: {image_url} - {e}")
            return None
        except Exception as e:
            self.logger.error(f"予期しない画像ダウンロードエラー: {image_url} - {e}")
            return None
    
    def _is_valid_image_url(self, url: str) -> bool:
        """画像URLの妥当性チェック"""
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
            
            # 一般的な画像拡張子のチェック
            path = parsed.path.lower()
            image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.bmp']
            
            # 拡張子チェック（ただし、拡張子がなくても画像の可能性がある）
            if any(path.endswith(ext) for ext in image_extensions):
                return True
            
            # クエリパラメータに画像関連の情報があるかチェック
            if 'image' in url.lower() or 'img' in url.lower():
                return True
                
            return True  # 寛容に判定
            
        except Exception:
            return False
    
    def _generate_image_filename(self, image_url: str, content_type: str) -> str:
        """画像ファイル名を生成"""
        try:
            parsed_url = urlparse(image_url)
            original_filename = os.path.basename(parsed_url.path)
            
            # 拡張子の決定
            if content_type == 'image/jpeg':
                ext = '.jpg'
            elif content_type == 'image/png':
                ext = '.png'
            elif content_type == 'image/gif':
                ext = '.gif'
            elif content_type == 'image/svg+xml':
                ext = '.svg'
            elif content_type == 'image/webp':
                ext = '.webp'
            else:
                ext = '.jpg'  # デフォルト
            
            # ファイル名の処理
            if original_filename and not original_filename.startswith('.'):
                # 元のファイル名から拡張子を除去
                name_without_ext = os.path.splitext(original_filename)[0]
                # 無効な文字を除去
                name_without_ext = re.sub(r'[^\w\-.]', '_', name_without_ext)
                if name_without_ext:
                    return f"{name_without_ext}{ext}"
            
            # ハッシュベースのファイル名を生成
            url_hash = abs(hash(image_url)) % 100000
            return f"image_{url_hash:05d}{ext}"
            
        except Exception:
            # フォールバック
            return f"image_{abs(hash(image_url)) % 100000:05d}.jpg"
    
    def _url_to_file_path(self, url: str) -> str:
        """URLをファイルパスに変換"""
        try:
            parsed_url = urlparse(url)
            path = parsed_url.path or '/'
            
            # パスの正規化
            if path.endswith('/'):
                path = path.rstrip('/')
            
            # 特殊なファイル名の処理
            if path.endswith('/index.html') or path.endswith('/index.htm'):
                path = path.rsplit('/index.', 1)[0]
            elif path.endswith('.html') or path.endswith('.htm'):
                path = os.path.splitext(path)[0]
            
            # ファイル名を生成
            if not path or path == '/':
                filename = "index.md"
            else:
                # パスからファイル名を生成
                clean_path = path.lstrip('/')
                # 無効な文字を置換
                clean_path = re.sub(r'[<>:"|?*]', '_', clean_path)
                filename = f"{clean_path}.md"
            
            return filename
            
        except Exception as e:
            self.logger.error(f"URLからファイルパス変換エラー: {url} - {e}")
            # フォールバック
            return f"page_{abs(hash(url)) % 100000:05d}.md"
    
    def _save_markdown(self, content: str, url: str) -> Optional[Path]:
        """Markdownファイルを保存"""
        try:
            filename = self._url_to_file_path(url)
            
            output_config = self._get_config('output', {})
            base_dir = output_config.get('base_dir', './output')
            file_path = Path(base_dir) / filename
            
            # ディレクトリを作成
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # ファイルを保存
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.logger.debug(f"Markdownファイル保存: {file_path}")
            return file_path
            
        except Exception as e:
            self.logger.error(f"Markdownファイル保存エラー: {url} - {e}")
            return None
    
    def process_page(self, url: str, html_content: str = None) -> Optional[Path]:
        """ページを処理してMarkdownに変換・保存"""
        self.stats['total_processed'] += 1
        
        try:
            self.logger.info(f"ページ処理開始: {url}")
            
            # HTMLコンテンツが提供されていない場合は取得
            if html_content is None:
                self.logger.error("HTMLコンテンツが提供されていません")
                self.stats['total_failed'] += 1
                return None
            
            # メインコンテンツを抽出
            main_content = self._extract_content(html_content)
            if main_content is None:
                self.logger.error(f"コンテンツ抽出に失敗: {url}")
                self.stats['total_failed'] += 1
                return None
            
            # 画像を処理
            processed_content = self._process_images(main_content, url)
            
            # Markdownに変換
            try:
                markdown_content = self.html2text.handle(processed_content)
            except Exception as e:
                self.logger.error(f"Markdown変換エラー: {url} - {e}")
                self.stats['total_failed'] += 1
                return None
            
            # ファイルに保存
            file_path = self._save_markdown(markdown_content, url)
            if file_path is None:
                self.stats['total_failed'] += 1
                return None
            
            self.stats['total_success'] += 1
            self.logger.info(f"ページ処理完了: {url} -> {file_path}")
            return file_path
            
        except Exception as e:
            self.logger.error(f"ページ処理中の予期しないエラー: {url} - {e}")
            self.stats['total_failed'] += 1
            return None
    
    def get_stats(self) -> Dict[str, int]:
        """統計情報を取得"""
        return self.stats.copy()
    
    def log_summary(self):
        """処理結果のサマリーをログ出力"""
        self.logger.info("=== Markdown変換完了 ===")
        self.logger.info(f"処理ページ数: {self.stats['total_processed']}")
        self.logger.info(f"成功: {self.stats['total_success']}")
        self.logger.info(f"失敗: {self.stats['total_failed']}")
        self.logger.info(f"画像ダウンロード成功: {self.stats['images_downloaded']}")
        self.logger.info(f"画像ダウンロード失敗: {self.stats['images_failed']}")
        
        if self.stats['total_processed'] > 0:
            success_rate = (self.stats['total_success'] / self.stats['total_processed']) * 100
            self.logger.info(f"成功率: {success_rate:.1f}%")