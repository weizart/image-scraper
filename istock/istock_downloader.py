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

class IStockDownloader:
    def __init__(self, keyword, save_path, site_choice):
        self.keyword = keyword
        self.downloaded = 0
        self.max_pages = 100
        self.site = "gettyimages" if site_choice == "g" else "istockphoto"
        
        # 创建下载目录
        self.download_dir = os.path.join(save_path, keyword)
        os.makedirs(self.download_dir, exist_ok=True)
        os.chmod(self.download_dir, 0o755)
        
        self.pbar = None
        
        # 修改 Chrome 选项
        chrome_options = Options()
        chrome_options.binary_location = '/usr/bin/chromium-browser'
        
        # 使用 Xvfb 而不是 headless 模式
        # chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        # 设置更真实的显示参数
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--start-maximized')
        
        # 添加硬件加速和 GPU 相关参数
        chrome_options.add_argument('--ignore-gpu-blocklist')
        chrome_options.add_argument('--enable-gpu-rasterization')
        chrome_options.add_argument('--enable-zero-copy')
        chrome_options.add_argument('--enable-native-gpu-memory-buffers')
        
        # 添加更多的反检测参数
        chrome_options.add_argument('--disable-infobars')
        chrome_options.add_argument('--lang=zh-CN,zh')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--allow-running-insecure-content')
        chrome_options.add_argument('--disable-notifications')
        
        # 添加 WebGL 参数
        chrome_options.add_argument('--use-gl=desktop')  # 使用桌面 OpenGL
        chrome_options.add_argument('--use-angle=default')  # 使用默认 ANGLE 后端
        
        # 设置更真实的 color profile
        chrome_options.add_argument('--force-color-profile=srgb')
        
        # 禁用自动化标志
        chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # 修改 navigator.webdriver
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        
        # 设置性能参数
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--allow-running-insecure-content')
        
        # 随机化 User-Agent
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0'
        ]
        chrome_options.add_argument(f'user-agent={random.choice(user_agents)}')
        
        # 添加更多的 Chrome 性能参数
        prefs = {
            'profile.default_content_setting_values': {
                'notifications': 2,
                'images': 1,
                'javascript': 1,
                'plugins': 1,
                'popups': 2,
                'geolocation': 2,
                'auto_select_certificate': 2,
                'mouselock': 2,
                'mixed_script': 1,
                'media_stream': 2,
                'media_stream_mic': 2,
                'media_stream_camera': 2,
                'protocol_handlers': 2,
                'ppapi_broker': 2,
                'automatic_downloads': 2,
                'midi_sysex': 2,
                'push_messaging': 2,
                'ssl_cert_decisions': 2,
                'metro_switch_to_desktop': 2,
                'protected_media_identifier': 2,
                'app_banner': 2,
                'site_engagement': 2,
                'durable_storage': 2
            },
            'profile.managed_default_content_settings': {
                'images': 1
            }
        }
        chrome_options.add_experimental_option('prefs', prefs)
        
        # 初始化WebDriver
        try:
            print("\n初始化Chrome浏览器...")
            cmd = ['sudo', '/usr/bin/chromedriver', '--port=4445']
            self.chromedriver_process = subprocess.Popen(cmd, 
                                                       stdout=subprocess.PIPE, 
                                                       stderr=subprocess.PIPE)
            time.sleep(2)
            
            print("ChromeDriver启动完成，尝试连接...")
            service = Service('http://localhost:4445')
            
            self.driver = webdriver.Remote(
                command_executor='http://localhost:4445',
                options=chrome_options
            )
            print("成功创建WebDriver实例")
            
            # 验证webdriver状态
            print("\n检查浏览器特征...")
            self.driver.get("https://bot.sannysoft.com")
            time.sleep(5)
            print("当前页面标题:", self.driver.title)
            print("当前URL:", self.driver.current_url)
            
            # 保存页面源码以供分析
            with open('browser_check.html', 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            print("已保存浏览器特征检测结果到 browser_check.html")
            
        except Exception as e:
            print(f"初始化Chrome浏览器失败: {str(e)}")
            if hasattr(self, 'chromedriver_process'):
                self.chromedriver_process.kill()
                stdout, stderr = self.chromedriver_process.communicate()
                print("\nChromeDriver输出:", stdout.decode())
                print("\nChromeDriver错误:", stderr.decode())
            raise
            
        self.wait = WebDriverWait(self.driver, 5)
        
        # 用于文件下载的session
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': f'https://www.{self.site}.com/',
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
                    img = item.find_element(By.TAG_NAME, 'img')
                    img_url = img.get_attribute('src')
                    
                    if not img_url or img_url.startswith('data:'):
                        continue
                        
                    if img_url.startswith('//'):
                        img_url = 'https:' + img_url
                    
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

    def inject_anti_detection_scripts(self):
        """注入更复杂的反检测代码"""
        print("\n注入反检测JavaScript...")
        
        # 注入更复杂的反检测代码
        self.driver.execute_script("""
            // WebGL 检测防护
            const getParameterProto = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                // UNMASKED_VENDOR_WEBGL
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                // UNMASKED_RENDERER_WEBGL
                if (parameter === 37446) {
                    return 'Intel Iris OpenGL Engine';
                }
                return getParameterProto.apply(this, [parameter]);
            };
            
            // 更真实的 Permissions API
            const permissionsQuery = navigator.permissions.query;
            navigator.permissions.query = function(parameters) {
                return Promise.resolve({state: 'granted'});
            };
            
            // 添加更多浏览器特征
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en-US', 'en']});
            
            // 模拟插件
            Object.defineProperty(navigator, 'plugins', {
                get: () => ({
                    length: 5,
                    item: function(index) {
                        return [
                            {name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer'},
                            {name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'},
                            {name: 'Native Client', filename: 'internal-nacl-plugin'},
                            {name: 'Widevine Content Decryption Module', filename: 'widevinecdmadapter.dll'},
                            {name: 'Microsoft Edge PDF Plugin', filename: 'internal-pdf-viewer'}
                        ][index] || null;
                    },
                    refresh: function() {},
                    namedItem: function(name) {
                        return this[0];
                    }
                })
            });
            
            // 修改 window.chrome
            window.chrome = {
                app: {
                    isInstalled: false,
                    InstallState: {
                        DISABLED: 'disabled',
                        INSTALLED: 'installed',
                        NOT_INSTALLED: 'not_installed'
                    },
                    RunningState: {
                        CANNOT_RUN: 'cannot_run',
                        READY_TO_RUN: 'ready_to_run',
                        RUNNING: 'running'
                    }
                },
                runtime: {
                    OnInstalledReason: {
                        CHROME_UPDATE: 'chrome_update',
                        INSTALL: 'install',
                        SHARED_MODULE_UPDATE: 'shared_module_update',
                        UPDATE: 'update'
                    },
                    OnRestartRequiredReason: {
                        APP_UPDATE: 'app_update',
                        OS_UPDATE: 'os_update',
                        PERIODIC: 'periodic'
                    },
                    PlatformArch: {
                        ARM: 'arm',
                        ARM64: 'arm64',
                        MIPS: 'mips',
                        MIPS64: 'mips64',
                        X86_32: 'x86-32',
                        X86_64: 'x86-64'
                    },
                    PlatformNaclArch: {
                        ARM: 'arm',
                        MIPS: 'mips',
                        MIPS64: 'mips64',
                        X86_32: 'x86-32',
                        X86_64: 'x86-64'
                    },
                    PlatformOs: {
                        ANDROID: 'android',
                        CROS: 'cros',
                        LINUX: 'linux',
                        MAC: 'mac',
                        OPENBSD: 'openbsd',
                        WIN: 'win'
                    },
                    RequestUpdateCheckStatus: {
                        NO_UPDATE: 'no_update',
                        THROTTLED: 'throttled',
                        UPDATE_AVAILABLE: 'update_available'
                    }
                }
            };
            
            // 添加 canvas 指纹防护
            const toBlob = HTMLCanvasElement.prototype.toBlob;
            const toDataURL = HTMLCanvasElement.prototype.toDataURL;
            const getImageData = CanvasRenderingContext2D.prototype.getImageData;
            
            // 在图片数据中添加微小的随机噪声
            function addNoise(data) {
                const noise = Math.floor(Math.random() * 10);
                data[0] = (data[0] + noise) % 255;
                return data;
            }
            
            HTMLCanvasElement.prototype.toBlob = function() {
                addNoise(arguments[0]);
                return toBlob.apply(this, arguments);
            };
            
            HTMLCanvasElement.prototype.toDataURL = function() {
                addNoise(arguments[0]);
                return toDataURL.apply(this, arguments);
            };
            
            CanvasRenderingContext2D.prototype.getImageData = function() {
                const imageData = getImageData.apply(this, arguments);
                addNoise(imageData.data);
                return imageData;
            };
        """)
        
        # 验证注入效果
        checks = {
            'webdriver': 'return navigator.webdriver',
            'plugins': 'return navigator.plugins.length',
            'chrome': 'return typeof window.chrome',
            'permissions': 'return navigator.permissions.query({name: "notifications"}).then(p => p.state)',
            'webgl_vendor': 'const canvas = document.createElement("canvas"); const gl = canvas.getContext("webgl"); const debugInfo = gl.getExtension("WEBGL_debug_renderer_info"); return gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL);',
            'webgl_renderer': 'const canvas = document.createElement("canvas"); const gl = canvas.getContext("webgl"); const debugInfo = gl.getExtension("WEBGL_debug_renderer_info"); return gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);'
        }
        
        print("\n验证反检测效果:")
        for name, script in checks.items():
            try:
                result = self.driver.execute_script(script)
                print(f"  {name}: {result}")
            except Exception as e:
                print(f"  {name} 检查失败: {str(e)}")

    def get_download_urls(self, max_images=None):
        # 首先注入反检测代码
        self.inject_anti_detection_scripts()
        
        page = 1
        empty_page_count = 0
        max_empty_pages = 3
        retry_count = 0
        max_retries = 5
        
        self.pbar = tqdm(total=0, desc=f"下载进度 - 当前页面: {page}/{self.max_pages}", 
                        unit="张", 
                        bar_format='{desc} [{elapsed}<{remaining}, {rate_fmt}]')
        
        # 首先访问主页并等待
        try:
            print("\n访问主页以获取cookies...")
            self.driver.get(f'https://www.{self.site}.com')
            time.sleep(random.uniform(3, 5))
            
            # 输出当前cookies
            cookies = self.driver.get_cookies()
            print("\n获取到的cookies:")
            for cookie in cookies:
                print(f"  {cookie['name']}: {cookie['value'][:30]}...")
            
        except Exception as e:
            print(f"访问主页时出错: {str(e)}")
        
        while (not max_images or self.downloaded < max_images) and page <= self.max_pages:
            try:
                url = f'https://www.{self.site}.com/search/2/image?phrase={quote(self.keyword)}&page={page}'
                print(f"\n访问搜索页面: {url}")
                
                self.driver.get(url)
                time.sleep(random.uniform(2, 4))
                
                # 输出当前页面信息
                print(f"当前URL: {self.driver.current_url}")
                print(f"页面标题: {self.driver.title}")
                
                if '/bot-wall' in self.driver.current_url or 'sign-in' in self.driver.current_url:
                    print("\n被检测为机器人，页面源码片段:")
                    print(self.driver.page_source[:500])
                
                try:
                    self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
                    
                    # 检查是否被重定向到bot-wall
                    if '/bot-wall' in self.driver.current_url or 'sign-in' in self.driver.current_url:
                        retry_count += 1
                        if retry_count >= max_retries:
                            print("\n达到最大重试次数，停止爬取")
                            break
                        
                        print(f"\n警告：被检测为机器人，第 {retry_count}/{max_retries} 次重试...")
                        time.sleep(random.uniform(15, 30))  # 增加等待时间
                        
                        # 清除cookies并重新访问
                        self.driver.delete_all_cookies()
                        time.sleep(1)
                        continue
                    
                    retry_count = 0  # 重置重试计数
                    
                    # 随机滚动页面
                    for _ in range(random.randint(3, 6)):
                        scroll_height = random.randint(300, 800)
                        self.driver.execute_script(f"window.scrollBy(0, {scroll_height});")
                        time.sleep(random.uniform(0.5, 1.5))
                    
                    selector = '.gallery-mosaic-asset'
                    self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'gallery-mosaic-asset')))
                    items = self.driver.find_elements(By.CLASS_NAME, 'gallery-mosaic-asset')
                    
                    if not items:
                        empty_page_count += 1
                        if empty_page_count >= max_empty_pages:
                            print(f"\n连续 {max_empty_pages} 页未找到内容，停止爬取")
                            break

                    empty_page_count = 0
                    
                    # 更新进度条总数
                    remaining = max_images - self.downloaded if max_images else len(items)
                    self.pbar.total = self.downloaded + min(len(items), remaining if max_images else len(items))
                    self.pbar.refresh()
                    
                    # 批量下载图片
                    downloaded_count = self.download_batch(items)
                    if downloaded_count == 0:
                        empty_page_count += 1
                        if empty_page_count >= max_empty_pages:
                            print(f"\n连续 {max_empty_pages} 页未成功下载，停止爬取")
                            break
                    
                    # 更新进度条描述
                    self.pbar.set_description(f"下载进度 - 当前页面: {page}/{self.max_pages}")
                    
                    if max_images and self.downloaded >= max_images:
                        break
                    
                    page += 1
                    time.sleep(random.uniform(0.5, 1.5))
                    
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
    parser = argparse.ArgumentParser(description='iStock/Getty Images下载工具')
    parser.add_argument('keyword', help='搜索关键词')
    parser.add_argument('--save-path', default='downloads', help='保存路径，默认为 downloads 目录')
    parser.add_argument('--site', choices=['g', 'i'], default='i', help='选择网站：g=Getty Images, i=iStock (默认: i)')
    parser.add_argument('--max-images', type=int, help='最大下载图片数量')
    args = parser.parse_args()

    os.makedirs(args.save_path, exist_ok=True)
    os.chmod(args.save_path, 0o755)

    try:
        downloader = IStockDownloader(args.keyword, args.save_path, args.site)
        downloader.get_download_urls(args.max_images)
    except Exception as e:
        print(f"\n程序运行出错: {str(e)}")

if __name__ == '__main__':
    main() 