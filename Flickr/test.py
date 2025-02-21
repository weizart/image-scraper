import flickrapi
import urllib.request
import os

# Replace with your own Flickr API key and secret
api_key = '2b58cb9e9948ddca307c5eeac7008aba'
api_secret = 'Y002f592155836c09'

# 创建downloads目录
os.makedirs('downloads', exist_ok=True)

flickr = flickrapi.FlickrAPI(api_key, api_secret, format='parsed-json')
query = 'honeybees on flowers'
num_images = 10

photos = flickr.photos.search(text=query, per_page=num_images, media='photos', sort='relevance')
for i, photo in enumerate(photos['photos']['photo']):
    url = f"http://farm{photo['farm']}.staticflickr.com/{photo['server']}/{photo['id']}_{photo['secret']}.jpg"
    urllib.request.urlretrieve(url, os.path.join('downloads', f"{i}.jpg"))
    print(f"Downloaded {i+1}/{num_images}")

print("Done.")