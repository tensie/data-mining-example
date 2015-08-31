#!/usr/bin/python2
# -*- coding: utf-8 -*-
from argparse import ArgumentParser
from urllib import urlencode
from urllib2 import Request, urlopen
from time import mktime, strptime
from json import dumps, loads
from sys import stdout, exit, exc_info, stderr
from codecs import getwriter
from signal import signal, SIGINT

from bs4 import BeautifulSoup


def parse_users(url):
    found = []
    # SocialBlade returns 403 if urllib is detected, so we spoof UA
    req = Request(url, None, {
        "User-agent": "Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.1; WOW64; Trident/6.0)"
    })
    html = urlopen(req).read()
    soup = BeautifulSoup(html, "lxml")
    body = soup.find("div", {"id": "BodyContainer"})
    elements = body.find_all("div", {"class": "TableMonthlyStats"})
    for element in elements:
        links = element.find_all("a")
        for link in links:
            found.append(link.text)
    return found


def unique(source):
    seen = set()
    seen_add = seen.add
    return [item for item in source if not (item in seen or seen_add(item))]


def youtube_links(username):
    result = []
    html = urlopen("http://www.youtube.com/user/%s/about" % username).read()
    soup = BeautifulSoup(html, "lxml")
    container = soup.find("div", {"class": "branded-page-v2-col-container"})
    links = container.find_all("li", {"class": "channel-links-item"})
    for link in links:
        result.append(link.find("a")["href"])
    return result


def youtube(username, key):
    params = urlencode({
        "part": "snippet,statistics",
        "forUsername": username,
        "key": key,
    })
    data = loads(urlopen("https://www.googleapis.com/youtube/v3/channels?" + params).read())["items"]
    if len(data) > 0:
        data = data[0]
        return {
            "id": data["id"],
            "name": data["snippet"]["title"],
            "channel_subscribers": int(data["statistics"]["subscriberCount"]),
            "total_video_views": int(data["statistics"]["viewCount"]),
            "youtube_url": "https://www.youtube.com/channel/" + data["id"],
            "logo": data["snippet"]["thumbnails"]["high"]["url"],
            "joined_at": int(mktime(strptime(data["snippet"]["publishedAt"][:19], "%Y-%m-%dT%H:%M:%S"))),
            "description": data["snippet"]["description"],
            "links": youtube_links(username)
        }
    else:
        raise ValueError("No channels for {0}".format(username))


def read_key():
    argp = ArgumentParser()
    argp.add_argument('--key', type=str, required=True, help="YouTube API Key")
    argp.add_argument('--country', type=str, default="RU", help="Country code for SocialBlade")
    args = argp.parse_args()
    return args.country, args.key


def main():
    country, key = read_key()
    sout = getwriter("utf8")(stdout)
    serr = getwriter("utf8")(stderr)
    users = parse_users("http://socialblade.com/youtube/top/country/{0}".format(country)) + parse_users(
        "http://socialblade.com/youtube/top/country/{0}/mostsubscribed".format(country)) + parse_users(
        "http://socialblade.com/youtube/top/country/{0}/mostviewed")
    for user in unique(users):
        try:
            data = youtube(user, key)
            sout.write(dumps(data, ensure_ascii=False) + "\n")
        except Exception as e:
            exc_traceback = exc_info()[2]
            filename = line = None
            while exc_traceback is not None:
                f = exc_traceback.tb_frame
                line = exc_traceback.tb_lineno
                filename = f.f_code.co_filename
                exc_traceback = exc_traceback.tb_next
            serr.write(dumps({
                'error': True,
                'details': {
                    'message': str(e),
                    'file': filename,
                    'line': line
                }
            }, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    def signal_handler(signal, frame):
        exit(0)


    signal(SIGINT, signal_handler)
    main()
