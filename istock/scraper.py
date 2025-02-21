import os
import time
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import requests

def setup_driver():
    chrome_options = Options()
    # 添加反检测参数
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--disable-infobars')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--start-maximized')
    chrome_options.add_argument('--headless')
    
    # 设置用户代理
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    chrome_options.add_argument('--accept-language=en-US,en;q=0.9')
    
    try:
        # 直接创建driver，不使用service
        driver = webdriver.Chrome(options=chrome_options)
        
        # 修改 navigator.webdriver
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver
    except Exception as e:
        print(f"设置WebDriver时出错: {str(e)}")
        # 如果第一种方法失败，尝试第二种方法
        try:
            print("尝试使用备选方法启动WebDriver...")
            chrome_options.binary_location = '/usr/bin/chromium-browser'
            service = Service(executable_path='/usr/bin/chromedriver')
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            return driver
        except Exception as e2:
            print(f"备选方法也失败了: {str(e2)}")
            raise

def scrap(term, max_images, choice, page=1):
    site = "gettyimages" if choice == "g" else "istockphoto"
    base_url = f'https://www.{site}.com'
    
    driver = setup_driver()
    wait = WebDriverWait(driver, 10)
    
    try:
        # 首先访问主页
        print("访问主页...")
        driver.get(base_url)
        time.sleep(random.uniform(2, 4))
        
        counter = 1
        while max_images >= counter and page <= 100:
            search_url = f'{base_url}/search/2/image?phrase={term}&page={page}'
            print(f"\n正在访问页面: {search_url}")
            
            driver.get(search_url)
            time.sleep(random.uniform(3, 5))
            
            # 检查是否被重定向到bot-wall
            if '/bot-wall' in driver.current_url or 'sign-in' in driver.current_url:
                print("警告：被检测为机器人，尝试等待更长时间...")
                time.sleep(10)
                continue
            
            # 等待图片加载
            try:
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'gallery-mosaic-asset')))
            except:
                print("无法找到图片元素，尝试其他选择器...")
                
            # 滚动页面以加载更多图片
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # 获取所有图片元素
            image_elements = driver.find_elements(By.CSS_SELECTOR, 'img.gallery-asset-image')
            if not image_elements:
                image_elements = driver.find_elements(By.CSS_SELECTOR, '.gallery-mosaic-asset img')
            
            print(f"\n找到 {len(image_elements)} 个图片元素")
            
            if not image_elements:
                print("警告：没有找到任何图片元素，尝试下一页")
                page += 1
                continue
            
            # 下载图片
            for img in image_elements:
                try:
                    src = img.get_attribute('src')
                    if not src or src.startswith('data:'):
                        continue
                        
                    if src.startswith('//'):
                        src = 'https:' + src
                    
                    print(f"\n尝试下载图片 {counter} - URL: {src}")
                    
                    # 使用requests下载图片
                    headers = {
                        'User-Agent': driver.execute_script("return navigator.userAgent"),
                        'Referer': driver.current_url
                    }
                    
                    img_response = requests.get(src, headers=headers)
                    img_response.raise_for_status()
                    
                    filename = f'images/image{counter}.jpg'
                    with open(filename, 'wb') as f:
                        f.write(img_response.content)
                    print(f'成功下载图片 {counter} 到 {filename}')
                    
                    if max_images <= counter:
                        return
                    counter += 1
                    
                    # 随机延迟
                    time.sleep(random.uniform(1, 3))
                    
                except Exception as e:
                    print(f"下载图片时出错: {str(e)}")
                    continue
            
            page += 1
            
    except Exception as e:
        print(f"发生错误: {str(e)}")
    
    finally:
        driver.quit()

term = input('Enter Search Term: ').strip().replace(" ", "%20") # Encode Spaces

max_images = None
while max_images is None:
    try:  
      max_images = int(input('Enter Max Images To Scrap: '))
    except ValueError:
      print('Please Enter A valid Number!')

choice = None 
while choice is None: 
    choice = input('Scrap From gettyimages or istockphoto?  (g/i): ')[0]
    if(choice != 'g' and choice != 'i'):
       choice = None

if not os.path.isdir('images'):
    os.mkdir('images')
    print("创建images文件夹")

print(f"\n开始爬取关键词 '{term}' 的图片，目标数量: {max_images}")
scrap(term, max_images, choice=choice)
print("\n爬取完成！")
