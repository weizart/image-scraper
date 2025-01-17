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
from pachong_all import FreepikDownloader

class BatchDownloader:
    def __init__(self, keywords_file, start_row, end_row, save_path, log_file=None):
        self.keywords_file = keywords_file
        self.start_row = start_row
        self.end_row = end_row
        self.save_path = save_path
        self.current_row = start_row
        self.current_keyword = None
        self.min_required_images = 1500  # 最少需要的图片数量
        
        # 创建或加载日志文件
        self.log_file = log_file or f'download_log_{datetime.now().strftime("%m%d%H%M%S")}.csv'
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
        
        # 确保列的顺序与原始DataFrame一致
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
            # 如果存在，按列更新该行
            for col in columns:
                self.log_df.loc[existing_mask, col] = new_row[col].iloc[0]
        else:
            # 如果不存在，添加新行
            self.log_df = pd.concat([self.log_df, new_row], ignore_index=True)
        
        # 按行号排序并保存
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
    
    def process_keywords(self):
        """处理关键词列表"""
        # 读取关键词文件
        keywords_df = pd.read_csv(self.keywords_file)
        
        # 如果有日志文件，先检查失败的下载
        failed_rows = self.check_failed_downloads()
        if failed_rows:
            print(f"\n发现 {len(failed_rows)} 个需要重新下载的关键词")
            retry_choice = input("是否重新下载这些关键词？(y/n): ")
            if retry_choice.lower() == 'y':
                # 将失败的行添加到处理队列
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
            downloader = None
            
            while retry_count < max_retries:
                try:
                    # 确保之前的实例被清理
                    if downloader:
                        try:
                            downloader.driver.quit()
                        except:
                            pass
                        try:
                            downloader.chromedriver_process.kill()
                        except:
                            pass
                        time.sleep(2)  # 等待进程完全结束
                    
                    # 在每次尝试时都创建新的下载器实例
                    downloader = FreepikDownloader(keyword, self.save_path)
                    downloader.get_download_urls()
                    
                    # 获取下载结果
                    folder_path = downloader.download_dir
                    image_count = self.get_image_count(folder_path)
                    
                    # 检查下载数量
                    if image_count < self.min_required_images:
                        error_msg = f"下载数量不足：仅下载了 {image_count} 张图片，少于要求的 {self.min_required_images} 张"
                        print(f"\n{error_msg}")
                        
                        # 记录为失败
                        self.log_download(
                            keyword, row_number, 'failed',
                            folder_path, start_time, datetime.now(),
                            image_count, error_message=error_msg
                        )
                    else:
                        # 记录成功
                        self.log_download(
                            keyword, row_number, 'success',
                            folder_path, start_time, datetime.now(),
                            image_count
                        )
                    break
                    
                except Exception as e:
                    retry_count += 1
                    error_msg = f"错误: {str(e)}\n{traceback.format_exc()}"
                    print(f"\n下载失败 (尝试 {retry_count}/{max_retries}): {error_msg}")
                    
                    if retry_count == max_retries:
                        # 记录失败
                        self.log_download(
                            keyword, row_number, 'failed',
                            os.path.join(self.save_path, f'{keyword}_failed'),
                            start_time, datetime.now(),
                            error_message=error_msg
                        )
                    else:
                        print(f"等待 10 秒后重试...")
                        time.sleep(10)
                finally:
                    # 确保在每次尝试后清理资源
                    if downloader:
                        try:
                            downloader.driver.quit()
                        except:
                            pass
                        try:
                            downloader.chromedriver_process.kill()
                        except:
                            pass
            
            # 处理完一个关键词后等待一下，确保资源被完全释放
            time.sleep(10)

def main():
    parser = argparse.ArgumentParser(description='批量下载Freepik资源')
    parser.add_argument('keywords_file', help='包含关键词的CSV文件路径')
    parser.add_argument('--start-row', type=int, default=1, help='起始行号（从1开始）')
    parser.add_argument('--end-row', type=int, help='结束行号')
    parser.add_argument('--save-path', default='downloads', help='保存路径，默认为 downloads 目录')
    parser.add_argument('--log-file', help='日志文件路径，用于断点续传')
    
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
    batch_downloader = BatchDownloader(
        args.keywords_file, args.start_row, args.end_row, 
        args.save_path, args.log_file
    )
    batch_downloader.process_keywords()

if __name__ == '__main__':
    main() 