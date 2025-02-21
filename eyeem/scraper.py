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
        self.max_pages = 100  # 最大页数限制
        
        # 创建下载目录
        self.download_dir = os.path.join(save_path, keyword)
        os.makedirs(self.download_dir, exist_ok=True)
        os.chmod(self.download_dir, 0o755)
        
        self.pbar = None
        
        # 设置Chrome选项
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
        
        # 初始化WebDriver
        try:
            cmd = ['sudo', '/usr/bin/chromedriver', '--port=4445']  # 使用4445端口
            self.chromedriver_process = subprocess.Popen(cmd, 
                                                       stdout=subprocess.PIPE, 
                                                       stderr=subprocess.PIPE)
            time.sleep(2)
            
            service = Service('http://localhost:4445')
            
            self.driver = webdriver.Remote(
                command_executor='http://localhost:4445',
                options=chrome_options
            )
        except Exception as e:
            print(f"初始化Chrome浏览器失败: {str(e)}")
            if hasattr(self, 'chromedriver_process'):
                self.chromedriver_process.kill()
            if hasattr(self, 'chromedriver_process'):
                stdout, stderr = self.chromedriver_process.communicate()
                print("ChromeDriver输出:")
                print(stdout.decode())
                print("ChromeDriver错误:")
                print(stderr.decode())
            raise
            
        self.wait = WebDriverWait(self.driver, 5)
        
        # 用于文件下载的session
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
        except Exception as e:
            print(f"下载失败详细信息: {str(e)}")
        return False

    def download_batch(self, items):
        successful_downloads = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for item in items:
                try:
                    img = item if item.tag_name == 'img' else item.find_element(By.CSS_SELECTOR, 'img')
                    img_url = img.get_attribute('src')
                    
                    if not img_url:
                        continue
                    
                    img_id = img_url.split('/')[-1].split('?')[0]
                    if not img_id.lower().endswith(('.jpg', '.jpeg', '.png')):
                        img_id += '.jpg'
                    
                    filename = os.path.join(self.download_dir, img_id)
                    futures.append(executor.submit(self.download_file, img_url, filename))
                except:
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
                    time.sleep(5)
                    
                    # 使用与原网站相同的选择器
                    selector = 'figure[data-cy="resource-thumbnail"]'
                    self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    items = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if not items:
                        empty_page_count += 1
                        if empty_page_count >= max_empty_pages:
                            print(f"\n连续 {max_empty_pages} 页未找到内容，停止爬取")
                            break
                        page += 1
                        continue

                    empty_page_count = 0
                    
                    self.pbar.total = self.downloaded + len(items)
                    self.pbar.refresh()
                    
                    downloaded_count = self.download_batch(items)
                    if downloaded_count == 0:
                        empty_page_count += 1
                        if empty_page_count >= max_empty_pages:
                            print(f"\n连续 {max_empty_pages} 页未成功下载，停止爬取")
                            break
                    
                    self.pbar.set_description(f"下载进度 - 当前页面: {page}/{self.max_pages}")
                    
                    page += 1
                    time.sleep(random.uniform(0.5,1.5))
                    
                except Exception as e:
                    print(f"\n处理页面时发生错误: {str(e)}")
                    break

            except Exception as e:
                print(f"\n访问页面时发生错误: {str(e)}")
                break
        
        if self.pbar:
            self.pbar.close()
        print(f"\n爬取完成，共下载 {self.downloaded} 张图片")

def main():
    parser = argparse.ArgumentParser(description='Eyeem资源下载工具')
    parser.add_argument('keyword', help='搜索关键词')
    parser.add_argument('--save-path', default='downloads', help='保存路径，默认为 downloads 目录')
    args = parser.parse_args()

    os.makedirs(args.save_path, exist_ok=True)
    os.chmod(args.save_path, 0o755)

    try:
        downloader = EyeemDownloader(args.keyword, args.save_path)
        downloader.get_download_urls()
    except Exception as e:
        print(f"\n程序运行出错: {str(e)}")

if __name__ == '__main__':
    main() 