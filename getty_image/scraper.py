import requests
import os
import time
import re
import random
from unidecode import unidecode
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

class GettyImageScraper:
    def __init__(self):
        self.session = self._create_session()
        self.headers = self._get_headers()
        
    def _create_session(self):
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session
    
    def _get_headers(self):
        ua = UserAgent()
        return {
            'User-Agent': ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Referer': 'https://www.gettyimages.com/'
        }
    
    def _random_delay(self):
        time.sleep(random.uniform(3, 7))
    
    def _make_request(self, url, retry_count=0):
        try:
            self._random_delay()
            self.headers['User-Agent'] = UserAgent().random
            response = self.session.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            if retry_count < 3:
                print(f"请求失败，正在重试 ({retry_count + 1}/3)...")
                time.sleep(random.uniform(5, 10))
                return self._make_request(url, retry_count + 1)
            else:
                print(f"请求失败: {str(e)}")
                return None

    def scrape_images(self, search_terms, pages_to_scrape):
        os.makedirs("output", exist_ok=True)
        
        for search_term in search_terms:
            print(f"\n开始搜索: {search_term}...")
            page_number = 1
            last_page = False
            
            while page_number <= pages_to_scrape and not last_page:
                url = f"https://www.gettyimages.com/photos/{search_term}?assettype=image&license=rf&alloweduse=availableforalluses&family=creative&phrase={search_term}&sort=mostpopular&numberofpeople=none&page={page_number}"
                
                response = self._make_request(url)
                if not response:
                    continue
                
                print(f"HTTP 状态码: {response.status_code}")
                
                if response.status_code == 403:
                    print("检测到反爬虫限制，等待更长时间...")
                    time.sleep(random.uniform(30, 60))
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                if "bot-wall" in response.url or "sign-in" in response.url:
                    print("被重定向到验证页面，暂停爬取...")
                    time.sleep(6)
                    continue
                
                h1 = soup.find('h1')
                if h1 and "Oops" in h1.text:
                    last_page = True
                    continue
                
                images = soup.find_all('img', {'class': 'MosaicAsset-module__thumb___yvFP5'})
                print(f"找到 {len(images)} 张图片")
                
                if images:
                    dir_name = f"output/{search_term}"
                    os.makedirs(dir_name, exist_ok=True)
                    
                    for image in images:
                        try:
                            image_url = image['src']
                            if not image_url.startswith('http'):
                                image_url = 'https:' + image_url
                            
                            img_response = self._make_request(image_url)
                            if not img_response:
                                continue
                            
                            alt = self._clean_filename(image.get('alt', 'untitled'))
                            filename = f"{dir_name}/{alt}.jpg"
                            
                            with open(filename, 'wb') as f:
                                f.write(img_response.content)
                            print(f"已保存: {filename}")
                            
                        except Exception as e:
                            print(f"保存图片时出错: {str(e)}")
                            continue
                else:
                    print(f"在第 {page_number} 页未找到图片")
                
                next_page = soup.find('button', {'class': 'PaginationRow-module__button___QQbMu PaginationRow-module__nextButton___gH3HZ'})
                if next_page:
                    page_number += 1
                else:
                    last_page = True
    
    def _clean_filename(self, filename):
        # 清理文件名
        filename = unidecode(filename)
        filename = re.sub(r'[^\w., ]', '_', filename)
        filename = re.sub(r'/', ' ', filename)
        filename = re.sub(r'_ ', ' ', filename)
        filename = re.sub(r'__+', '_', filename)
        filename = re.sub(r'_', ' ', filename)
        filename = filename.replace('  ', ' ')
        filename = filename.rsplit('.', 1)[0]
        return filename[:250]

def main():
    try:
        with open('list.txt', 'r', encoding='utf-8') as f:
            search_terms = f.read().splitlines()
        
        pages_to_scrape = input("请输入要爬取的页数: ")
        pages_to_scrape = int(pages_to_scrape)
        
        scraper = GettyImageScraper()
        scraper.scrape_images(search_terms, pages_to_scrape)
        
    except FileNotFoundError:
        print("错误: 找不到 list.txt 文件")
    except ValueError:
        print("错误: 请输入有效的页数")
    except Exception as e:
        print(f"发生错误: {str(e)}")
    finally:
        print("\n爬取完成!")

if __name__ == "__main__":
    main()