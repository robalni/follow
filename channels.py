import yaml
from html.parser import HTMLParser
import re
import feedparser
import urllib.request
import json
import dateutil.parser
from datetime import datetime
from time import mktime
from tzlocal import get_localzone

twitch_apiurl_base = 'https://api.twitch.tv/kraken/'
twitch_client_id = 'dl1xe55lg2y26u8njj769lxhq3i47r'
twitch_accept = 'application/vnd.twitchtv.v5+json'

max_content_length = 370

class Channel():
    def __init__(self, channel):
        self.channel = channel

    def get_posts(self):
        posts = []
        if not 'feed' in self.channel and not 'stream' in self.channel:
            self.fill_out_channel()
        if 'feed' in self.channel:
            posts += self.get_posts_from_feed()
        if 'stream' in self.channel:
            posts += self.get_posts_from_stream()
        return posts

    def get_posts_from_feed(self):
        posts = []
        print("Fetching feed from {}".format(self.channel['feed']))
        feed = feedparser.parse(self.channel['feed'])
        for item in feed['items']:
            content = None
            if 'content' in item:
                for c in item['content']:
                    if c['type'] == 'text/plain':
                        content = c['value']
                if content is None:
                    s = HTMLStripper()
                    s.feed(item['content'][0]['value'])
                    content = s.get_data()
                if len(content) > max_content_length:
                    content = content[:max_content_length] + '...'
            if content is None and 'description' in item:
                s = HTMLStripper()
                s.feed(item['description'])
                content = s.get_data()
                if len(content) > max_content_length:
                    content = content[:max_content_length] + '...'

            date = None
            if 'published_parsed' in item:
                date = item['published_parsed']
            if date is None and'updated_parsed' in item:
                date = item['updated_parsed']
            if date is None and 'published' in item:
                date = dateutil.parser.parse(item['published']).timetuple()
            if date:
                date = datetime.fromtimestamp(mktime(date)).astimezone(get_localzone())
            url = ''
            if 'link' in item:
                url = item['link']
            media = []
            if 'enclosures' in item:
                media += item['enclosures']
                for m in media:
                    m['filename'] = m['href'].split('/')[-1]
            posts.append({
                'title': item['title'],
                'url': url,
                'content': content,
                'channel': self.channel,
                'date': date,
                'media': media,
            })
        return posts

    def get_posts_from_stream(self):
        posts = []
        m = re.match(r'(?:https?://)?api.twitch.tv/kraken/streams/([^/]+)', self.stream)
        if m:
            userid = m.group(1)
            apiurl = twitch_apiurl_base + 'streams/' + userid
            req = urllib.request.Request(apiurl)
            req.add_header('Accept', twitch_accept)
            req.add_header('Client-ID', twitch_client_id)
            obj = json.loads(str(urllib.request.urlopen(req).read(), 'utf-8'))
            stream = obj['stream']
            if stream:
                date = dateutil.parser.parse(stream['created_at']).astimezone(get_localzone())
                posts.append({
                    'title': stream['channel']['status'],
                    'url': self.home,
                    'content': "Playing: " + stream['game'],
                    'channel': self.channel,
                    'date': date,
                })
        return posts

    @property
    def name(self):
        return self.get_property('name')

    @property
    def image(self):
        return self.get_property('image')

    @property
    def url(self):
        return self.get_property('url')

    @property
    def home(self):
        return self.get_property('home')

    @property
    def stream(self):
        return self.get_property('stream')

    @property
    def media(self):
        return self.get_property('media')

    def get_property(self, name):
        if type(self.channel) is str:
            self.fill_out_channel()
        if name in self.channel:
            return self.channel[name]
        else:
            return ''

    def channel_from_youtube(url):
        channel_id = None
        image = None
        channel = None
        m = re.match(r'(?:https?://)?(?:www\.)?youtube\.com/user/([^/]+)', url)
        if m:
            html = str(urllib.request.urlopen(url).read())
            m2 = re.search(r'data-channel-external-id="([^"]+)"', html)
            if m2:
                channel_id = m2.group(1)
        else:
            m = re.match(r'(?:https?://)?(?:www\.)?youtube\.com/channel/([^/]+)', url)
            if m:
                html = str(urllib.request.urlopen(url).read())
                channel_id = m.group(1)
            else:
                return None
        m_img = re.search(r'<img class="appbar-nav-avatar" src="([^"]+)', html)
        if m_img:
            image = m_img.group(1)
        if channel_id:
            feed_url = (
                'https://www.youtube.com/feeds/videos.xml?channel_id=' 
                    + channel_id
            )
            feed = feedparser.parse(feed_url)
            if 'feed' in feed:
                feed = feed['feed']
                channel = {
                    'feed': feed_url,
                }
                if 'title' in feed:
                    channel['name'] = feed['title']
                print(image)
                channel['image'] = image
        return channel

    def channel_from_twitch(url):
        m = re.match(r'(?:https?://)?(?:www\.)?twitch.tv/([^/]+)', url)
        if not m:
            return None
        username = m.group(1)

        apiurl = twitch_apiurl_base + 'users?login=' + username
        req = urllib.request.Request(apiurl)
        req.add_header('Accept', twitch_accept)
        req.add_header('Client-ID', twitch_client_id)
        response = str(urllib.request.urlopen(req).read(), 'utf-8')
        obj = json.loads(response)
        users = obj['users']
        if len(users) > 0:
            user = users[0]
        else:
            print("User not found: {}".format(url))
            return None

        name = user['display_name']
        home = 'https://www.twitch.tv/' + user['name']
        image = user['logo']
        userid = user['_id']
        return {
            'name': name,
            'home': home,
            'image': image,
            'stream': 'https://api.twitch.tv/kraken/streams/' + userid
        }

    def channel_from_url(url):
        c = Channel.channel_from_youtube(url)
        if c:
            return c
        c = Channel.channel_from_twitch(url)
        if c:
            return c
        return None

    def fill_out_channel(self):
        if type(self.channel) is str:
            c = Channel.channel_from_url(self.channel)
            if c:
                self.channel = c

class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.fed = []
    def handle_data(self, d):
        self.fed.append(d)
    def get_data(self):
        return ''.join(self.fed)

def get_channels():
    with open('list.yml') as f:
        obj = yaml.load(f)
    return [Channel(ch) for ch in obj]

def get_all_posts():
    channels = get_channels()
    posts = []
    for ch in channels:
        posts += ch.get_posts()
    return sorted(posts, reverse = True, key = lambda ch: ch['date'])
