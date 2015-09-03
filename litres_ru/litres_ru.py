#!/usr/bin/python
# -*- coding: utf-8 -*-
import argparse
from grab import Grab, error
import re
import json
import threading


def string_to_dictionary(s, pair_separator, key_value_separator):
    pairs = s.split(pair_separator)
    return dict(pair.split(key_value_separator) for pair in pairs)


def set_headers(in_grab):
    my_header = arguments.header
    if my_header:
        if type(my_header) == list:
            my_header = ';'.join(my_header)
        my_header = string_to_dictionary(my_header, ';', ':')
        in_grab.setup(headers=my_header)


def set_proxy(in_grab):
    proxy = arguments.proxy
    if proxy:
        rex = re.compile(r'(?:(?:[-a-z0-9]+\.)+)[a-z0-9]+:\d{2,4}')
        if rex.match(proxy):
            proxy = rex.match(proxy).group()
            in_grab.setup(proxy=proxy, proxy_type='http', connect_timeout=5, timeout=15)
        else:
            raise Exception('Invalid proxy name. Set in format: 127.0.0.1:3128')


def set_timeout(in_grab):
    in_grab.setup(connect_timeout=30, timeout=150)


def parser_sub(sub):
    result = []
    for item in sub.split('\r\n\r\n'):
        arr = item.split('\r\n')
        if len(arr) == 3:
            result.append({
                'id': arr[0],
                'start': arr[1][:12],
                'stop': arr[1][17:],
                'text': arr[2]
            })
        elif len(arr) == 1:
            result.append({
                'text': arr[0]
            })
    return result


lock_print = False
def push_answer(in_res):
    temp_dumps = json.dumps(in_res, ensure_ascii=False)
    temp_res = ''
    try:
        temp_res = temp_dumps.encode('utf8')
    except UnicodeDecodeError:
        temp_res = temp_dumps

    global lock_print
    while lock_print:
        pass

    lock_print = True
    print temp_res
    lock_print = False


host_url = 'http://www.litres.ru'


def parser_url(url, in_grab):
    # print '-----', url
    res = {
        'url': url,
        'name': '',
        'author': '',
        'year': '',
        'image': '',
        'description': '',
        'price': {
            'currency': '',
            'type': 'currency',
            'content': ''
        },
        'availability': '',
    }
    in_grab.go(url)
    if in_grab.doc.code != 200:
        raise error.GrabTimeoutError('code: ' + str(in_grab.doc.code))
    try:
        res['name'] = in_grab.doc.select('//div[@id="blockcenter"]/h1[@class="book-title"]').text()
    except error.DataNotFound:
        pass
    try:
        res['author'] = in_grab.doc.select('//div[@id="blockcenter"]//div[@class="book-author"]').text()
    except error.DataNotFound:
        pass
    try:
        dd_selector = in_grab.doc.select('//div[@id="blockcenter"]//dd')
        dt_selector = in_grab.doc.select('//div[@id="blockcenter"]//dt')
        if dd_selector.count() == dt_selector.count():
            for i in range(dt_selector.count()):
                s = dt_selector[i].text()
                if u'Дата написания:' in s:
                    res['year'] = int(dd_selector[i].text())
                elif u'Издательство:' in s:
                    res['publisher'] = dd_selector[i].text()
    except error.DataNotFound:
        pass
    except ValueError:
        pass
    try:
        res['image'] = in_grab.doc.select('//div[@id="book-cover"]//a[@class="bookpage-cover"]/img[2]/@src').text()
    except error.DataNotFound:
        pass
    try:
        res['description'] = in_grab.doc.select('//div[contains(@class, "book_annotation")]').text()
    except error.DataNotFound:
        pass
    try:
        s = in_grab.doc.select('//div[@id="blockcenter"]//span[@class="finalprice"] |'
                               ' //div[@id="blockcenter"]//div[@class="block48"]').text()
        price = re.search(u'[\d,.]+', s).group(0)
        price = price.replace(',', '')
        res['price']['content'] = float(price)
    except error.DataNotFound:
        pass
    except ValueError:
        pass
    except AttributeError:
        pass
    try:
        res['price']['currency'] = 'RUR'
    except error.DataNotFound:
        pass
    try:
        res['availability'] = u'в наличии'
    except error.DataNotFound:
        pass
    try:
        if u'Электронная книга' in in_grab.doc.select('//div[@id="blockcenter"]/div[@class="art_type"]').text():
            res['eBook'] = True
        else:
            res['eBook'] = False
    except error.DataNotFound:
        pass

    push_answer(res)


def thread_parser_urls(in_urls):
    g = Grab()
    set_headers(g)
    set_proxy(g)
    set_timeout(g)
    reconnect_count = 10
    for url in in_urls:
        g.go(url)
        for book_url in g.doc.select('//div[@id="master_page_div"]//div[@class="booktitle"]/div[1]/a/@href'):
            i = 0
            while i < reconnect_count:
                try:
                    parser_url(host_url + book_url.text(), g)
                    i = reconnect_count
                except error.GrabTimeoutError:
                    i += 1


def parser(threads_count=1):
    g = Grab()
    set_headers(g)
    set_proxy(g)
    set_timeout(g)

    g.go('http://www.litres.ru/zhanry/elektronnie-knigi/')
    try:
        for element in g.doc.select('//ul[@id="genres_tree"]/li/ul/li/a/@href'):
            url = element.text()
            url = host_url + url

            urls = []

            g.go(url)
            try:
                pages = int(g.doc.select('//div[@class="paginator_pages"]').text().replace(u'страниц: ', ''))
                for i in range(1, pages, 1):
                    s = url + 'page-' + str(i) + '/'
                    urls.append(s)
                    urls.append(s.replace('/elektronnie-knigi/', '/pechatnye-knigi/'))
            except error.DataNotFound:
                pass
            except ValueError:
                pass

            threads = []
            for i in range(threads_count):
                temp_urls = urls[i::threads_count]
                t = threading.Thread(target=thread_parser_urls, args=(temp_urls,))
                threads.append(t)
                t.start()

            for th in threads:
                th.join()
    except error.DataNotFound:
        pass


options_parser = argparse.ArgumentParser()
options_parser.add_argument('--proxy', '-p', help='set proxy in format: 127.0.0.1:3128')
options_parser.add_argument('--header', '-H', help='Custom header to pass to server', action='append')
options_parser.add_argument('--threads', '-t', help='set number of threads')
arguments = options_parser.parse_args()


threads_count = arguments.threads
if threads_count:
    try:
        threads_count = int(threads_count)
        if threads_count < 0:
            raise Exception('Invalid number of threads. Set a number greater than 0.')
    except ValueError:
        raise Exception('Invalid number of threads. Set integer number.')
    parser(threads_count)
else:
    parser()
