import logging
import subprocess
from abc import ABC, abstractmethod
from typing import List, Dict
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class BaseSource(ABC):
    """抽象基类，使用 curl 绕过 geo-block"""

    def __init__(self, config: dict):
        self.config = config
        self.ua = config.get('request', {}).get(
            'user_agent',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
        )
        self.timeout = config.get('request', {}).get('timeout', 30)

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def source_url(self) -> str:
        pass

    @abstractmethod
    def fetch(self) -> List[Dict]:
        pass

    def get(self, url: str, timeout: int = None) -> BeautifulSoup:
        """使用 curl 获取页面（绕过 geo-block）。失败时返回 None 并记录具体原因。"""
        t = timeout or self.timeout
        try:
            result = subprocess.run([
                'curl', '-s', '-L',
                '-H', f'User-Agent: {self.ua}',
                '-H', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                '-H', 'Accept-Language: zh-CN,zh;q=0.9,en;q=0.8',
                '--connect-timeout', str(t),
                '--max-time', str(t + 5),
                url
            ], capture_output=True, text=True, timeout=t + 10)

            if result.returncode != 0:
                logger.warning(
                    f"[{self.name}] curl 返回非零退出码 {url}: "
                    f"code={result.returncode}, stderr={result.stderr[:200]}"
                )
                return None

            if len(result.stdout) <= 500:
                logger.warning(
                    f"[{self.name}] 响应内容过短 {url}: "
                    f"只有 {len(result.stdout)} 字节 (期望 > 500)"
                )
                return None

            return BeautifulSoup(result.stdout, 'lxml')

        except subprocess.TimeoutExpired:
            logger.error(f"[{self.name}] 请求超时 {url}: 超过 {t + 10} 秒")
            return None
        except OSError as e:
            logger.error(f"[{self.name}] curl 命令执行失败 {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"[{self.name}] 未知错误 {url}: {type(e).__name__}: {e}")
            return None

    @staticmethod
    def make_lead(title: str, url: str, date: str = '',
                  summary: str = '', source_name: str = '',
                  category: str = '') -> Dict:
        return {
            'title': title.strip(),
            'url': url.strip(),
            'date': date.strip(),
            'summary': summary.strip(),
            'source_name': source_name.strip(),
            'category': category.strip(),
        }
