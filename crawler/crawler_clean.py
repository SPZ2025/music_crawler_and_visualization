import requests
import time
import random
import json
import base64
import re
import sys
import os
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO


PROJECT_DIR = Path(__file__).resolve().parent.parent
with open(PROJECT_DIR / "secret.txt", "r", encoding="utf-8") as file:
    cookies = file.read() 

SINGER_LIST_URL = 'https://y.qq.com/n/ryqq_v2/singer_list'

headers = {
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36"
    ),

    "accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.7"
    ),

    "accept-language": "zh-CN,zh;q=0.9",

    "referer": "https://y.qq.com/n/ryqq_v2/singer_list",
    
    "cookie": cookies,
}


SINGER_LIMIT = 300
SINGER_LIMIT_PER_SINGER = 10
SLEEP_RANGE = (1.5, 4)
COMMENT_LIMIT = 3
SCROLL_TIMES = 4
PAGE_GOTO_TIMEOUT_MS = 60000
COMMENT_WAIT_TIMEOUT_MS = 15000
SITE_DIR = PROJECT_DIR / "music_site"
QQ_MUSIC_PROFILE_DIR = str(PROJECT_DIR / "qq_music_profile")
SINGERS_JSON_PATH = str(SITE_DIR / "data" / "singers.json")
SONGS_JSON_PATH = str(SITE_DIR / "data" / "songs.json")
STATIC_IMAGES_DIR = SITE_DIR / "static" / "images"

#处理cookie，后面给playwright用
def build_playwright_cookies(cookie_text):
    playwright_cookies = []
    for item in cookie_text.split(";"):
        item = item.strip()
        if not item or "=" not in item:
            continue

        name, value = item.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not name:
            continue

        playwright_cookies.append({
            "name": name,
            "value": value,
            "domain": ".qq.com",
            "path": "/",
        })

    return playwright_cookies

#playwright 歌手清单
async def fetch_rendered_html_with_scroll_async(list_url):
    async with async_playwright() as p:

        context = await p.chromium.launch_persistent_context(
            user_data_dir = QQ_MUSIC_PROFILE_DIR,
            headless = False,
            extra_http_headers = {
                "user-agent": headers["user-agent"],
                "referer": "https://y.qq.com/"
            },
        )
        try:
            playwright_cookies = build_playwright_cookies(cookies)
            if playwright_cookies:
                await context.add_cookies(playwright_cookies)
            
            page = await context.new_page()
            await page.goto(
                list_url,
                wait_until= 'domcontentloaded',
                timeout= PAGE_GOTO_TIMEOUT_MS,
            )
            for _ in range(SCROLL_TIMES):
                await page.mouse.wheel(0, 1200)
                await page.wait_for_timeout(1000)
            return await page.content()
        except PlaywrightTimeoutError:
            print(f"[警告] 打开歌手列表页面超时: {list_url}")
        finally:
            await context.close()

#playwright 爬取评论
async def fetch_comments_with_page(page, song_url, limit = COMMENT_LIMIT):
    comments = []

    comment_item_selector = "li.comment__list_item.c_b_normal"
    comment_text_selector = "p.comment__text span"
    comment_time_selector = "div.comment__date"

    try:
        await page.goto(
            song_url,
            wait_until= 'networkidle',
            timeout= PAGE_GOTO_TIMEOUT_MS,
        )
    except PlaywrightTimeoutError:
        print(f"[警告] 打开歌曲页面超时: {song_url}")
        return comments

    await page.wait_for_timeout(2000)
    await page.mouse.wheel(0, 800)
    await page.wait_for_timeout(2000)

    try:
        await page.wait_for_selector(
            comment_item_selector,
            timeout= COMMENT_WAIT_TIMEOUT_MS,
        )
    except PlaywrightTimeoutError:
        print("[警告] 没找到 song_url_comments,页面结构可能变了,请重新用开发者工具确认。")
        return comments

    comment_items = await page.locator(comment_item_selector).all()
    for item in comment_items[:limit]:
        text_locator = item.locator(comment_text_selector)
        if await text_locator.count() == 0:
            continue
        comment_text = (await text_locator.first.inner_text()).strip()
        if not comment_text:
            continue

        time_locator = item.locator(comment_time_selector)
        if await time_locator.count() == 0:
            continue
        comment_time = (await time_locator.first.inner_text()).strip()
        if not comment_time:
            continue

        comments.append({
            'comment_text': comment_text,
            'comment_time': comment_time,
        })

    return comments

#反爬机制
def time_sleep():
    time.sleep(random.uniform(*SLEEP_RANGE))

#断点续爬机制
def load_json_list(file_path):
    if not os.path.exists(file_path):
        return []

    with open(file_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return []

    if isinstance(data, list):
        return data
    return []

#即时保存函数
def save_data(all_singers, all_songs):
    os.makedirs(os.path.dirname(SINGERS_JSON_PATH), exist_ok=True)
    with open(SINGERS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(all_singers, f, ensure_ascii=False, indent=2)

    with open(SONGS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(all_songs, f, ensure_ascii=False, indent=2)

#请求函数
def fetch_text(url):
    try:
        response = requests.get(url, headers=headers, proxies={}, timeout=10)
        response.raise_for_status()
    except requests.exceptions.HTTPError:
        raise
    response.encoding = response.apparent_encoding or 'utf-8'
    return response.text
def fetch_image(url):
    response = requests.get(url, headers=headers, proxies={}, timeout=10)
    response.raise_for_status()
    image = Image.open(BytesIO(response.content))
    return image

#照片链接提取
def extract_photo_url_singer(html_text):
    start = html_text.find('"singerDetail"')
    if start == -1:
        return ""
    part = html_text[start:start + 3000]
    m = re.search(r'"pic"\s*:\s*"((?:[^"\\]|\\.)*)"', part)
    if not m:
        return ""
    raw_value = m.group(1)
    
    url = json.loads(f'"{raw_value}"')
    if url.startswith("//"):
        url = "https:" + url
    return url
def extract_photo_url_song(html_text):
    start = html_text.find('"detail"')
    if start == -1:
        return ""
    part = html_text[start:start + 3000]
    m = re.search(r'"picurl"\s*:\s*"((?:[^"\\]|\\.)*)"', part)
    if not m:
        return "" 
    raw_value = m.group(1)
    
    url = json.loads(f'"{raw_value}"')
    if url.startswith("//"):
        url = "https:" + url
    return url

#提取所有歌手的id和名字
def extract_song_singers_from_soup(soup):
    singers = []
    seen = set()

    for a in soup.find_all('a', class_='data__singer_txt', href=True):
        href = a.get('href', '')
        m = re.search(r'/singer/([a-zA-Z0-9]+)', href)
        if not m:
            continue

        singer_id = m.group(1)
        singer_name = a.get_text().strip()
        if not singer_id or not singer_name or singer_id in seen:
            continue

        singers.append({
            'singer_id': singer_id,
            'singer_name': singer_name,
        })
        seen.add(singer_id)

    return singers

#写入歌曲字典
def set_song_singer_fields(song_info, singers):
    if not singers:
        return False

    singer_ids = [singer['singer_id'] for singer in singers]
    singer_names = [singer['singer_name'] for singer in singers]

    song_info['song_singer_id'] = singer_ids[0]
    song_info['song_singer_ids'] = singer_ids
    song_info['song_singer'] = ' / '.join(singer_names)
    song_info['song_singers'] = singer_names
    return True

#歌词提取
def fetch_lyric(songmid):
    lyric_url = "https://c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_new.fcg"
    params = {
        "songmid": songmid,
        "format": "json",
        "nobase64": 0,
        "g_tk": 5381,
        "loginUin": 0,
        "hostUin": 0,
        "inCharset": "utf8",
        "outCharset": "utf-8",
        "notice": 0,
        "platform": "yqq",
        "needNewCode": 0,
    }

    data = None
    for attempt in range(3):
        try:
            response = requests.get(lyric_url, params=params, headers=headers, proxies={}, timeout=20)
            response.raise_for_status()
            data = response.json()
            break
        except requests.exceptions.Timeout:
            print(f"[警告] 歌词请求超时: {songmid}, 第 {attempt + 1} 次")
            time.sleep(random.uniform(3, 6))
        except requests.exceptions.RequestException as e:
            print(f"[警告] 歌词请求失败: {songmid}, {e}")
            return []

    if data is None:
        return []

    raw_lyric = data.get("lyric", "")
    if not raw_lyric:
        return []

    try:
        text = base64.b64decode(raw_lyric).decode("utf-8", errors="ignore")
    except Exception:
        return []

    lyrics = []
    for line in text.splitlines():
        if re.match(r"^\[(ti|ar|al|by|offset):", line):
            continue
        line = re.sub(r"\[(?:\d{1,2}:)?\d{1,2}:\d{1,2}(?:\.\d{1,3})?\]", "", line).strip()
        if line:
            lyrics.append(line)
    return lyrics


# ------------------------------------------------------------------------
#第一层：歌手列表
#-------------------------------------------------------------------------
def parse_singer_list_html(html_text, limit = SINGER_LIMIT):
    soup = BeautifulSoup(html_text, 'lxml')
    ul = soup.find('ul', class_= 'singer_list_txt')

    singers = []
    if ul is None:
        print("[警告] 没找到 singer_list_txt,页面结构可能变了,请重新用开发者工具确认。")
        return singers

    for a in ul.find_all('a', href = True):
        href = a.get('href')
        m = re.search(r'/singer/([a-zA-Z0-9]+)', href)
        if not m:
            continue

        singer_id = m.group(1)
        singer_name = a.get_text().strip()
        if not singer_name:
            continue

        singer = {'singer_id': str(singer_id), 'singer_name': str(singer_name), 
                  'singer_url': f'https://y.qq.com/n/ryqq_v2/singer/{singer_id}'}
        singers.append(singer)

        if len(singers) >= limit:
            break

    return singers
async def crawl_singer_list_async(limit = SINGER_LIMIT):
    html_text = await fetch_rendered_html_with_scroll_async(SINGER_LIST_URL)
    time_sleep()
    return parse_singer_list_html(html_text, limit)

#-------------------------------------------------------------------------
#第二层：歌手主页
#-------------------------------------------------------------------------
def crawl_singer_info(singer_dic, limit = SINGER_LIMIT_PER_SINGER):
    SINGER_INFO_URL = singer_dic['singer_url']
    html_text = fetch_text(SINGER_INFO_URL)
    time_sleep()

    soup = BeautifulSoup(html_text, 'lxml')
    popup = soup.find(id='popup_data_detail')

    singer_info = dict(singer_dic)
    if popup is None:
        print("[警告] 没找到 singer_info_txt,页面结构可能变了,请重新用开发者工具确认。")
    else:
        last_key = None
        for p in popup.find_all('p'):
            content = p.get_text().strip()
            if not content:
                continue

            m = re.match(r"^([^:：\s]{1,8})\s*[:：]\s*(.*)$", content)
            if m:
                key = m.group(1).strip()
                value = m.group(2).strip()
                singer_info[key] = value
                last_key = key
            elif last_key:
                singer_info[last_key] = singer_info[last_key] + "\n" + content

    photo_url = extract_photo_url_singer(html_text)
    singer_info['singer_photo_url'] = photo_url
    if not photo_url:
        print(f"[警告] {singer_dic['singer_name']} 没找到 pic 字段,photo_url 将为空。")

    songs = []
    m = re.findall(r'/n/ryqq_v2/songDetail/([a-zA-Z0-9]+)',html_text)
    seen = set()
    for id in m:
        if id in seen:
            continue
        seen.add(id)
        songs.append({
            'song_id': id,
            'song_url': f'https://y.qq.com/n/ryqq_v2/songDetail/{id}',
            'song_singer_id': singer_dic['singer_id'],
            'song_singer_ids': [singer_dic['singer_id']],
            'song_singer': singer_dic['singer_name'],
            'song_singers': [singer_dic['singer_name']],
        })
        if len(songs) >= limit:
            break
        
    return singer_info, songs

#-------------------------------------------------------------------------
#第三层：歌曲主页
#-------------------------------------------------------------------------
def crawl_song_info(song_dic):

    SONG_URL = song_dic['song_url']
    html_text = fetch_text(SONG_URL)
    song_info = dict(song_dic)

    soup = BeautifulSoup(html_text, 'lxml')

    h1 = soup.find('h1', class_ = 'data__name_txt', title = True)
    if h1 is None:
        print("[警告] 没找到 song_title_txt,页面结构可能变了,请重新用开发者工具确认。")
    else:
        song_title = h1.get_text().strip()
        song_info['song_title'] = song_title
    
    song_singers = extract_song_singers_from_soup(soup)
    if not set_song_singer_fields(song_info, song_singers):
        print("[警告] 没找到 song_singer_txt,页面结构可能变了,请重新用开发者工具确认。")

    
    photo_url = extract_photo_url_song(html_text)
    song_info['song_photo_url'] = photo_url
    if not photo_url:
        print(f"[警告] {song_dic['song_id']} 没找到 photo_url,photo_url 将为空。")

    lyrics = fetch_lyric(song_dic['song_id'])
    song_info['song_lyrics'] = lyrics
    if not lyrics:
        print(f"[警告] {song_dic['song_id']} 没拿到歌词")

    return song_info

#-------------------------------------------------------------------------
#合并：处理信息
#-------------------------------------------------------------------------
def deal_singer_info(_singer_info):
    photo_url = _singer_info['singer_photo_url']
    if not photo_url:
        print(f"[跳过] {_singer_info.get('singer_name')} 缺少歌手图片，歌手数据不完整")
        return {}
    image = fetch_image(photo_url)

    image_dir = STATIC_IMAGES_DIR / "singers"
    image_dir.mkdir(parents=True, exist_ok=True)
    image_path = image_dir / f"{_singer_info['singer_id']}.jpg"
    image.save(image_path)

    _singer_info["singer_photo_path"] = f"static/images/singers/{_singer_info['singer_id']}.jpg"
    return _singer_info
    
def deal_song_info(_song_info):
    photo_url = _song_info['song_photo_url']
    if not photo_url:
        print(f"[跳过] {_song_info.get('song_id')} 缺少歌曲图片，歌曲数据不完整")
        return {}
    image = fetch_image(photo_url)

    image_dir = STATIC_IMAGES_DIR / "songs"
    image_dir.mkdir(parents=True, exist_ok=True)
    image_path = image_dir / f"{_song_info['song_id']}.jpg"
    image.save(image_path)

    _song_info["song_photo_path"] = f"static/images/songs/{_song_info['song_id']}.jpg"
    return _song_info

#主逻辑：过程中动态增添评论
async def main_logic_async():
    all_singers = load_json_list(SINGERS_JSON_PATH)
    all_songs = load_json_list(SONGS_JSON_PATH)
    crawled_singer_ids = {singer.get("singer_id") for singer in all_singers}
    crawled_song_ids = {song.get("song_id") for song in all_songs}

    try:
        singer_list = await crawl_singer_list_async()

        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir= QQ_MUSIC_PROFILE_DIR,
                headless= False,
                extra_http_headers= {
                    "user-agent": headers["user-agent"],
                    "referer": "https://y.qq.com/",
                },
            )
            try:
                playwright_cookies = build_playwright_cookies(cookies)
                if playwright_cookies:
                    await context.add_cookies(playwright_cookies)

                page = await context.new_page()

                for singer_dic in singer_list[240:]:
                    singer_id = singer_dic["singer_id"]
                    singer_exists = singer_id in crawled_singer_ids
                    if singer_exists:
                        print(f"[跳过] 歌手已存在: {singer_dic['singer_name']} ({singer_id})")

                    singer_info, songs = crawl_singer_info(singer_dic)
                    if not singer_exists:
                        temp = deal_singer_info(singer_info)
                        if not temp:
                            continue
                        all_singers.append(temp)
                        crawled_singer_ids.add(singer_id)
                        save_data(all_singers, all_songs)

                    for song_dic in songs:
                        song_id = song_dic["song_id"]
                        if song_id in crawled_song_ids:
                            print(f"[跳过] 歌曲已存在: {song_id}")
                            continue

                        song_info = crawl_song_info(song_dic)
                        comments = await fetch_comments_with_page(page, song_info["song_url"])
                        song_info['song_comments'] = comments
                        if not comments:
                            print(f"[警告]{song_dic['song_id']}没拿到评论")

                        temp = deal_song_info(song_info)
                        if not temp:
                            continue
                        all_songs.append(temp)
                        crawled_song_ids.add(song_id)
                        save_data(all_singers, all_songs)
            finally:
                await context.close()

    finally:
        save_data(all_singers, all_songs)

        print(f"已保存 {len(all_singers)} 位歌手、{len(all_songs)} 首歌曲的数据")

def main_logic():
    asyncio.run(main_logic_async())

#运行！yeyeyeye
if __name__ == "__main__":
    main_logic()
