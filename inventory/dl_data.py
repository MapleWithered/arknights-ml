import hashlib
import json
import os
import re
import shutil
from functools import lru_cache

import bs4
import requests
from retry import retry

collect_path = 'images/collect/'


@retry(tries=3)
def request_get(url):
    return requests.get(url)


def update_items():
    global items
    print('update_items')
    resp = request_get(
        'https://raw.githubusercontent.com/Kengxxiao/ArknightsGameData/master/zh_CN/gamedata/excel/item_table.json')
    md5 = hashlib.md5()
    md5.update(resp.content)
    items_map = resp.json()['items']
    items = [item for item in items_map.values()]
    data = {
        'hash': md5.hexdigest(),
        'data': items
    }
    remove_flag = False
    if os.path.exists('items.json'):
        with open('items.json', 'r', encoding='utf-8') as f:
            old_data = json.load(f)
            if old_data.get('hash') != data['hash']:
                remove_flag = True
    else:
        remove_flag = True

    if remove_flag:
        print('remove old collect')
        shutil.rmtree(collect_path)
        os.mkdir(collect_path)

    with open('items.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    items = data['data']
    return data['data']


def get_items():
    if not os.path.exists('items.json'):
        return update_items()
    else:
        with open('items.json', 'r', encoding='utf-8') as f:
            return json.load(f)['data']


items = get_items()


def get_items_id_map():
    res = {}
    for item in items:
        res[item['itemId']] = item
    return res


@lru_cache(1)
def get_items_name_map():
    res = {}
    for item in items:
        res[item['name']] = item
    return res


def download_icons():
    update_items()
    flag1 = download_from_items_page()
    flag2 = download_latest_event_icons()
    return flag1 and flag2


def download_from_items_page():
    print('checking item page...')
    resp = request_get('http://prts.wiki/w/%E9%81%93%E5%85%B7%E4%B8%80%E8%A7%88')
    soup = bs4.BeautifulSoup(resp.text, features='html.parser')
    data_devs = soup.find_all("div", {"class": "smwdata"})
    # print(data_devs[0])
    total = len(data_devs)
    c = 0
    update_flag = False
    for data_dev in data_devs:
        item_name = data_dev['data-name']
        flag = save_img(item_name, data_dev['data-file'])
        if flag:
            update_flag = True
            print(item_name)
        c += 1
        # print(f'{c}/{total} {item_name}')
    return update_flag


def download_latest_event_icons():
    print('checking event page...')
    resp = request_get('http://prts.wiki/w/%E9%A6%96%E9%A1%B5')
    soup = bs4.BeautifulSoup(resp.text, features='html.parser')
    event_menu = soup.find_all(text='当前活动')
    update_flag = False
    if event_menu:
        li = event_menu[0].parent.parent
        a_list = li.find_all('a')
        for a_tag in a_list:
            event_url = 'http://prts.wiki' + a_tag['href']
            print('handle event:', a_tag.text)
            flag = download_from_event_page(event_url)
            if flag:
                update_flag = True
    return update_flag


def download_from_event_page(event_url):
    resp = request_get(event_url)
    soup = bs4.BeautifulSoup(resp.text, features='html.parser')
    item_imgs = soup.find_all('img', attrs={'alt': re.compile('道具')})
    item_set = set()
    update_flag = False
    for item_img in item_imgs:
        if item_img['alt'] in item_set:
            continue
        item_set.add(item_img['alt'])
        item_name = item_img.parent['title']
        img_url = 'http://prts.wiki' + item_img['data-srcset'].split(', ')[-1][:-3]
        flag = save_img(item_name, img_url)
        if flag:
            update_flag = True
    return update_flag


def save_img(item_name, img_url):
    items_name_map = get_items_name_map()
    item = items_name_map.get(item_name)
    item_id = 'other'
    if item and item['itemType'] in {'MATERIAL', 'ARKPLANNER', 'ACTIVITY_ITEM'}:
        item_id = item['itemId']
        if item['itemType'] != 'ACTIVITY_ITEM' and not item_id.isdigit() or len(item_id) < 5:
            item_id = 'other'
    if img_url == '':
        print(f'skip {item_name}, img_url: {img_url}')
        return False
    if not os.path.exists(collect_path + item_id):
        os.mkdir(collect_path + item_id)
    filepath = collect_path + item_id + '/%s.png' % item_name
    if os.path.exists(filepath):
        return False
    print(f'downloading {item_id}/{item_name} ...')
    print(f'img_url: {img_url}')
    rc = 0
    while rc <= 3:
        try:
            resp = request_get(img_url)
            with open(filepath, 'wb') as f:
                f.write(resp.content)
            return True
        except Exception as e:
            print(e)
            rc += 1
    raise RuntimeError(f'save_img reach max retry count, {item_id, item_name, img_url}')


if __name__ == '__main__':
    download_icons()
    # print(download_latest_event_icons())
    # download_from_event_page('http://prts.wiki/w/%E5%AF%86%E6%9E%97%E6%82%8D%E5%B0%86%E5%BD%92%E6%9D%A52021#%E5%A4%A7%E9%85%8B%E9%95%BF%E4%B9%8B%E8%B7%AF')
