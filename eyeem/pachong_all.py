from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import argparse
import os
import time
import requests
from urllib.parse import quote
import random
import subprocess
from tqdm import tqdm
import concurrent.futures
from datetime import datetime

class EyeemDownloader:
    def __init__(self, keyword, save_path):
        self.keyword = keyword
        self.downloaded = 0
        self.max_pages = 100
        self.download_dir = os.path.join(save_path, keyword)
        
        os.makedirs(self.download_dir, exist_ok=True)
        os.chmod(self.download_dir, 0o755)
        
        self.pbar = None
        self._setup_chrome_options()
        self._init_webdriver()
        self._setup_session()

    def _setup_chrome_options(self):
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.binary_location = '/usr/bin/chromium-browser'
        chrome_options.add_argument('--remote-debugging-port=9223')
        chrome_options.add_argument(f'user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        self.chrome_options = chrome_options

    def _init_webdriver(self):
        try:
            cmd = ['sudo', '/usr/bin/chromedriver', '--port=4445']
            self.chromedriver_process = subprocess.Popen(cmd,
                                                       stdout=subprocess.PIPE,
                                                       stderr=subprocess.PIPE)
            time.sleep(2)

            service = Service('http://localhost:4445')
            self.driver = webdriver.Remote(
                command_executor='http://localhost:4445',
                options=self.chrome_options
            )
            
            self.wait = WebDriverWait(self.driver, 5)
            
        except Exception as e:
            print(f"\n初始化WebDriver失败: {str(e)}")
            if hasattr(self, 'chromedriver_process'):
                self.chromedriver_process.kill()
                stdout, stderr = self.chromedriver_process.communicate()
                print(f"ChromeDriver输出: {stdout.decode()}")
                print(f"ChromeDriver错误: {stderr.decode()}")
            raise

    def _setup_session(self):
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://www.eyeem.com/',
        }

    def __del__(self):
        if hasattr(self, 'driver'):
            try:
                self.driver.quit()
            except:
                pass
        
        if hasattr(self, 'chromedriver_process'):
            try:
                self.chromedriver_process.kill()
            except:
                pass
        
        if hasattr(self, 'pbar'):
            try:
                self.pbar.close()
            except:
                pass

    def download_file(self, url, filename):
        try:
            response = self.session.get(url, headers=self.headers)
            if response.status_code == 200:
                with open(filename, 'wb') as f:
                    f.write(response.content)
                return True
            else:
                return False
                
        except Exception as e:
            print(f"\n下载文件失败: {str(e)}, URL: {url}")
            return False

    def download_batch(self, items):
        successful_downloads = 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for item in items:
                try:
                    img_url = item.get_attribute('src')
                    if not img_url:
                        continue
                    
                    # 获取更大尺寸的图片
                    img_url = img_url.replace('/w/300', '/w/1200')
                    
                    # 提取原始文件名（图片ID-时间戳）
                    # 例如：从 https://cdn.eyeem.com/thumb/7ad248b908f64b2fab12fb588f57993a2c648f6b-1535213669029/w/1200
                    # 提取 7ad248b908f64b2fab12fb588f57993a2c648f6b-1535213669029
                    img_id = img_url.split('/thumb/')[-1].split('/w/')[0]
                    if not img_id.lower().endswith(('.jpg', '.jpeg', '.png')):
                        img_id += '.jpg'
                    
                    filename = os.path.join(self.download_dir, img_id)
                    futures.append(executor.submit(self.download_file, img_url, filename))
                except Exception as e:
                    print(f"\n处理图片URL时出错: {str(e)}")
                    continue
            
            for future in concurrent.futures.as_completed(futures):
                if future.result():
                    successful_downloads += 1
                    self.downloaded += 1
                    if self.pbar:
                        self.pbar.update(1)
        
        return successful_downloads

    def get_download_urls(self):
        page = 1
        empty_page_count = 0
        max_empty_pages = 3
        
        self.pbar = tqdm(total=0, desc=f"下载进度 - 当前页面: {page}/{self.max_pages}",
                        unit="张",
                        bar_format='{desc} [{elapsed}<{remaining}, {rate_fmt}]')
        
        while page <= self.max_pages:
            try:
                url = f'https://www.eyeem.com/search/pictures/{quote(self.keyword)}?collection=mixed&marketScore[]=great&marketStatus=commercial&page={page}&q={quote(self.keyword)}&replaceQuery=true&sort=relevance'

                
                self.driver.get(url)
                
                try:
                    self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
                    time.sleep(3)  # 增加等待时间，确保页面完全加载
                    
                    # 检查页面标题或特定元素，确认页面加载正确
                    if "Page Not Found" in self.driver.title:
                        print("\n页面未找到")
                        break
                    
                    items = self.driver.find_elements(By.CSS_SELECTOR, 'img[src*="cdn.eyeem.com"]')
                    current_page_items = len(items)

                    
                    if current_page_items == 0:
                        empty_page_count += 1
                        if empty_page_count >= max_empty_pages:
                            print(f"\n连续 {max_empty_pages} 页未找到内容，停止爬取")
                            break
                    else:
                        empty_page_count = 0  # 只有在当前页面没有图片时才增加计数
                        
                        # 更新进度条
                        self.pbar.total = self.downloaded + current_page_items
                        self.pbar.refresh()
                        
                        # 下载图片
                        downloaded_count = self.download_batch(items)
                        
                        if downloaded_count == 0:
                            print(f"警告：本页未成功下载任何图片")
                    
                    self.pbar.set_description(f"下载进度 - 当前页面: {page}/{self.max_pages}")
                    page += 1
                    time.sleep(random.uniform(1.5, 2.5))
                    
                except Exception as e:
                    print(f"\n处理页面时发生错误: {str(e)}")
                    break

            except Exception as e:
                print(f"\n访问页面时发生错误: {str(e)}")
                break
        
        if self.pbar:
            self.pbar.close()

def main():
    parser = argparse.ArgumentParser(description='Eyeem资源下载工具')
    parser.add_argument('keyword', help='搜索关键词')
    parser.add_argument('--save-path', default='downloads', help='保存路径，默认为 downloads 目录')
    args = parser.parse_args()

    try:
        os.makedirs(args.save_path, exist_ok=True)
        os.chmod(args.save_path, 0o755)
        
        downloader = EyeemDownloader(args.keyword, args.save_path)
        downloader.get_download_urls()
        
    except Exception as e:
        print(f"\n程序运行出错: {str(e)}")

if __name__ == '__main__':
    main() 