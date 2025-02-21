import pandas as pd
import os
import time
import argparse
from datetime import datetime
import sys
from pathlib import Path
import traceback
import signal
import atexit
from flickr_scraper import get_urls

class BatchFlickrDownloader:
    def __init__(self, keywords_file, start_row, end_row, save_path, log_file=None, images_per_keyword=1500):
        self.keywords_file = keywords_file
        self.start_row = start_row
        self.end_row = end_row
        self.save_path = save_path
        self.current_row = start_row
        self.current_keyword = None
        self.min_required_images = images_per_keyword
        self.consecutive_errors = 0  # 连续错误计数
        self.error_cooldown = 3600  # API限制时的冷却时间（秒）
        self.normal_delay = 5  # 正常请求间的延迟（秒）
        self.error_delay = 30  # 错误后的延迟（秒）
        self.max_consecutive_errors = 5  # 触发冷却的连续错误次数
        
        # 创建或加载日志文件
        self.log_file = log_file or f'flickr_download_log_{datetime.now().strftime("%m%d%H%M%S")}.csv'
        self.load_or_create_log()
        
        # 注册程序退出处理
        atexit.register(self.on_exit)
        signal.signal(signal.SIGINT, self.signal_handler)
        
    def load_or_create_log(self):
        """创建或加载日志文件"""
        if os.path.exists(self.log_file):
            self.log_df = pd.read_csv(self.log_file)
        else:
            self.log_df = pd.DataFrame(columns=[
                'keyword', 'row_number', 'status', 'folder_path', 
                'start_time', 'end_time', 'duration_minutes',
                'image_count', 'total_size_mb', 'error_message'
            ])
            self.log_df.to_csv(self.log_file, index=False)
    
    def get_folder_size(self, folder_path):
        """计算文件夹总大小（MB）"""
        total_size = 0
        for path in Path(folder_path).rglob('*'):
            if path.is_file():
                total_size += path.stat().st_size
        return total_size / (1024 * 1024)  # 转换为MB
    
    def get_image_count(self, folder_path):
        """统计图片文件数量"""
        count = 0
        for path in Path(folder_path).rglob('*'):
            if path.is_file() and path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                count += 1
        return count
    
    def log_download(self, keyword, row_number, status, folder_path, start_time, 
                    end_time, image_count=0, error_message=None):
        """记录下载结果"""
        duration = (end_time - start_time).total_seconds() / 60
        total_size = self.get_folder_size(folder_path) if os.path.exists(folder_path) else 0
        
        columns = [
            'keyword', 'row_number', 'status', 'folder_path', 
            'start_time', 'end_time', 'duration_minutes',
            'image_count', 'total_size_mb', 'error_message'
        ]
        
        new_data = {
            'keyword': keyword,
            'row_number': row_number,
            'status': status,
            'folder_path': folder_path,
            'start_time': start_time.strftime('%Y-%m-%d %H:%M:%S'),
            'end_time': end_time.strftime('%Y-%m-%d %H:%M:%S'),
            'duration_minutes': round(duration, 2),
            'image_count': image_count,
            'total_size_mb': round(total_size, 2),
            'error_message': error_message
        }
        
        new_row = pd.DataFrame([new_data], columns=columns)
        
        # 检查是否存在相同关键词的记录
        existing_mask = (self.log_df['keyword'] == keyword) & (self.log_df['row_number'] == row_number)
        if existing_mask.any():
            for col in columns:
                self.log_df.loc[existing_mask, col] = new_row[col].iloc[0]
        else:
            self.log_df = pd.concat([self.log_df, new_row], ignore_index=True)
        
        self.log_df = self.log_df.sort_values('row_number').reset_index(drop=True)
        self.log_df.to_csv(self.log_file, index=False)
    
    def signal_handler(self, signum, frame):
        """处理中断信号"""
        print(f"\n程序被中断！当前处理到：行号 {self.current_row}，关键词 '{self.current_keyword}'")
        print(f"如需继续，请使用参数：--start-row {self.current_row}")
        sys.exit(1)
    
    def on_exit(self):
        """程序退出时的清理工作"""
        if hasattr(self, 'log_df'):
            self.log_df.to_csv(self.log_file, index=False)
    
    def check_failed_downloads(self):
        """检查并返回需要重新下载的行"""
        if not os.path.exists(self.log_file):
            return []
        
        failed_rows = []
        for index, row in self.log_df.iterrows():
            if (row['status'] == 'failed' or 
                row['image_count'] == 0 or 
                (row['status'] == 'success' and row['image_count'] < self.min_required_images)):
                failed_rows.append({
                    'row_number': row['row_number'],
                    'keyword': row['keyword'],
                    'reason': ('Failed status' if row['status'] == 'failed' else 
                             'Zero images' if row['image_count'] == 0 else 
                             'Insufficient images')
                })
        
        if failed_rows:
            print("\n需要重新下载的行：")
            for row in failed_rows:
                print(f"行号: {row['row_number']}, 关键词: {row['keyword']}, 原因: {row['reason']}")
        
        return failed_rows
    
    def handle_rate_limit(self):
        """处理API速率限制"""
        if self.consecutive_errors >= self.max_consecutive_errors:
            print(f"\n检测到可能的API限制，暂停{self.error_cooldown/3600}小时...")
            time.sleep(self.error_cooldown)
            self.consecutive_errors = 0  # 重置错误计数
            return True
        return False
    
    def process_keywords(self):
        """处理关键词列表"""
        keywords_df = pd.read_csv(self.keywords_file)
        
        failed_rows = self.check_failed_downloads()
        if failed_rows:
            print(f"\n发现 {len(failed_rows)} 个需要重新下载的关键词")
            retry_choice = input("是否重新下载这些关键词？(y/n): ")
            if retry_choice.lower() == 'y':
                rows_to_process = [(row['row_number'], row['keyword']) for row in failed_rows]
            else:
                rows_to_process = [(idx + 1, keywords_df.iloc[idx]['keyword']) 
                                 for idx in range(self.start_row - 1, min(self.end_row, len(keywords_df)))]
        else:
            rows_to_process = [(idx + 1, keywords_df.iloc[idx]['keyword']) 
                             for idx in range(self.start_row - 1, min(self.end_row, len(keywords_df)))]

        total_keywords = len(rows_to_process)
        print(f"\n开始处理关键词，总计 {total_keywords} 个关键词待处理")
        
        for row_number, keyword in rows_to_process:
            self.current_row = row_number
            self.current_keyword = keyword
            
            print(f"\n处理第 {row_number} 行: {keyword}")
            start_time = datetime.now()
            
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    # 检查是否需要暂停
                    if self.handle_rate_limit():
                        print("恢复下载...")
                    
                    # 调用Flickr下载器
                    folder_path = os.path.join(self.save_path, keyword.replace(" ", "_"))
                    get_urls(search=keyword, n=self.min_required_images, download=True, save_dir=self.save_path)
                    
                    # 获取下载结果
                    image_count = self.get_image_count(folder_path)
                    
                    if image_count < self.min_required_images:
                        error_msg = f"下载数量不足：仅下载了 {image_count} 张图片，少于要求的 {self.min_required_images} 张"
                        print(f"\n{error_msg}")
                        
                        self.consecutive_errors += 1
                        self.log_download(
                            keyword, row_number, 'failed',
                            folder_path, start_time, datetime.now(),
                            image_count, error_message=error_msg
                        )
                    else:
                        self.consecutive_errors = 0  # 重置连续错误计数
                        self.log_download(
                            keyword, row_number, 'success',
                            folder_path, start_time, datetime.now(),
                            image_count
                        )
                        # 成功后使用正常延迟
                        time.sleep(self.normal_delay)
                    break
                    
                except Exception as e:
                    retry_count += 1
                    self.consecutive_errors += 1
                    error_msg = f"错误: {str(e)}\n{traceback.format_exc()}"
                    print(f"\n下载失败 (尝试 {retry_count}/{max_retries}): {error_msg}")
                    
                    if retry_count == max_retries:
                        self.log_download(
                            keyword, row_number, 'failed',
                            os.path.join(self.save_path, f'{keyword}_failed'),
                            start_time, datetime.now(),
                            error_message=error_msg
                        )
                    else:
                        delay = self.error_delay * (2 ** (retry_count - 1))  # 指数退避
                        print(f"等待 {delay} 秒后重试...")
                        time.sleep(delay)
            
            # 处理完一个关键词后等待
            if self.consecutive_errors > 0:
                # 如果有错误，使用更长的延迟
                time.sleep(self.error_delay)
            else:
                time.sleep(self.normal_delay)

def main():
    parser = argparse.ArgumentParser(description='批量下载Flickr图片')
    parser.add_argument('keywords_file', help='包含关键词的CSV文件路径')
    parser.add_argument('--start-row', type=int, default=1, help='起始行号（从1开始）')
    parser.add_argument('--end-row', type=int, help='结束行号')
    parser.add_argument('--save-path', default='downloads', help='保存路径，默认为 downloads 目录')
    parser.add_argument('--log-file', help='日志文件路径，用于断点续传')
    parser.add_argument('--images-per-keyword', type=int, default=5000, help='每个关键词需要下载的最少图片数量')
    
    args = parser.parse_args()
    
    # 读取CSV文件获取总行数
    total_rows = len(pd.read_csv(args.keywords_file))
    if args.end_row is None:
        args.end_row = total_rows
    
    # 验证参数
    if args.start_row < 1 or args.start_row > total_rows:
        print(f"错误：起始行号必须在 1 到 {total_rows} 之间")
        return
    if args.end_row < args.start_row or args.end_row > total_rows:
        print(f"错误：结束行号必须在 {args.start_row} 到 {total_rows} 之间")
        return
    
    # 确保保存路径存在
    os.makedirs(args.save_path, exist_ok=True)
    
    # 开始批量下载
    batch_downloader = BatchFlickrDownloader(
        args.keywords_file, args.start_row, args.end_row, 
        args.save_path, args.log_file, args.images_per_keyword
    )
    batch_downloader.process_keywords()

if __name__ == '__main__':
    main() 