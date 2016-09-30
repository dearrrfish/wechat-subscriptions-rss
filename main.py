#!/usr/bin/env python3

import sys, getopt
from os import path
import os
import json, re
import pymysql.cursors
from datetime import datetime
import dateutil.tz
from feedgen.feed import FeedGenerator

global cur_dir, script_dir, conn, wechats

cur_dir = os.getcwd()
script_dir, script_filename = path.split(path.abspath(sys.argv[0]))
sys.path.append(path.join(script_dir, 'WechatSogou'))

from wechatsogou.tools import *
from wechatsogou import *

class console:
    # HEADER = '\033[95m'
    # OKBLUE = '\033[94m'
    # OKGREEN = '\033[92m'
    # WARNING = '\033[93m'
    # FAIL = '\033[91m'
    # ENDC = '\033[0m'
    # BOLD = '\033[1m'
    # UNDERLINE = '\033[4m'

    def log(msg, end='\n', wrap=['', '']):
        msg = _wrap(msg, wrap)
        print(msg, end=end)

    def success(msg, end='\n', wrap=['', '']):
        OKGREEN = '\033[92m'
        ENDC = '\033[0m'
        msg = OKGREEN + _wrap(msg, wrap) + ENDC
        print(msg, end=end)

    def warn(msg, end='\n', wrap=['', '']):
        WARNING = '\033[93m'
        ENDC = '\033[0m'
        msg = WARNING + _wrap(msg, wrap) + ENDC
        print(msg, end=end)

    def error(msg, end='\n', wrap=['', '']):
        FAIL = '\033[91m'
        ENDC = '\033[0m'
        msg = FAIL + _wrap(msg, wrap) + ENDC
        print(msg, end=end)

def _wrap(msg, wrap=['', '']):
    if isinstance(wrap, str):
        mid_index = int(len(wrap)/2)
        wrap = [wrap[0:mid_index], wrap[mid_index:]]
    return wrap[0] + msg + wrap[1]

def retrieve_messages(wid, config):
    global conn, wechats, cur_dir
    has_new_messages = False
    messages = []

    console.log("Looking for existing account in database...", end='')
    with conn.cursor() as c:
        c.execute('SELECT id FROM `accounts` WHERE id = %s', (wid))
        exists_account = c.fetchone() != None

    if not exists_account:
        console.error('NOT FOUND', wrap='[]')
        console.log('Retrieving account info and recent messages...', end='')
        # Retrieve both account and recent messages
        messages_and_info = wechats.get_gzh_message_and_info(wechatid=wid)
        # print(messages_and_info)
        messages = messages_and_info['gzh_messages']
        # Store account info in database
        gzh_info = messages_and_info['gzh_info']
        console.success('READY', wrap='[]')

        with conn.cursor() as c:
            c.execute(
                'INSERT INTO `accounts` (id, name, auth, intro, image) VALUES (%s, %s, %s, %s, %s)',
                (wid, gzh_info['name'], gzh_info['renzhen'], gzh_info['jieshao'], gzh_info['img'])
            )

    else:
        console.success('FOUND', wrap='[]')
        console.log("Retrieving recent messages...", end='')
        messages = wechats.get_gzh_message(wechatid=wid)
        console.success('READY', wrap='[]')

    # print(json.dumps(messages))
    console.log('Processing %d messages...' % len(messages))

    for m in messages:
        exists_message = False
        # Message ID
        mid = "%s-%s-%s" % (m['qunfa_id'], m.get('main', 0), m.get('fileid', 0))
        with conn.cursor() as c:
            # Lookup in database for existing message
            c.execute('SELECT id FROM `messages` WHERE wechat_id=%s AND id=%s', (wid, mid))
            exists_message = c.fetchone() != None

        filename = path.join(_get_abspath(config.get('message_path', 'messages/'), cur_dir),
                             wid + '_' + mid + '.json')

        if exists_message and path.isfile(filename):
            console.warn('[%s] message exists, skip.' % mid)
            continue

        # New message
        mdatetime = m['datetime']
        mtype = m['type']
        message = {}
        try:
            if mtype == '1':
                message_type = 'TEXT'
                message['content'] = m.get('content', '')
            elif mtype == '3':
                message_type = 'IMAGE'
                message['url'] = m.get('img_url', '')
            elif mtype == '34':
                message_type = 'VOICE'
                message['length'] = m.get('play_length', '')
                message['fileId'] = m.get('fileid', '')
                message['src'] = m.get('audio_src', '')
            elif mtype == '49':
                message_type = 'POST'
                message['main'] = m.get('main', '')
                message['title'] = m.get('title', '')
                message['digest'] = m.get('digest', '')
                message['fileId'] = m.get('fileid', '')
                message['author'] = m.get('author', '')
                message['cover'] = m.get('cover', '')
                # message['copyright'] = m.get('copyright', '')
                # Retrieve HTML content and permanent link of post
                post = wechats.deal_article(m.get('content_url', ''))
                # print(post)
                message['content'] = post['content_html']
                message['url'] = post['yuan']

            elif mtype == '62':
                message_type = 'VIDEO'
                message['videoId'] = m.get('cnd_videoid', '')
                message['thumb'] = m.get('thumb', '')
                message['src'] = m.get('video_src', '')
            else:
                console.error('[%s] !! Unsupported message type: %s' % (mid, mtype))
                continue

        except:
            console.error('[%s] !! Failed to parse message.' % mid)
            continue

        with open(filename, 'w') as fd:
            json.dump(message, fd)

        # Store in database
        with conn.cursor() as c:
            c.execute(
                'INSERT INTO `messages` (id, wechat_id, datetime, type) VALUES (%s, %s, %s, %s) ' +
                'ON DUPLICATE KEY UPDATE wechat_id=wechat_id, datetime=datetime, type=type',
                (mid, wid, mdatetime, message_type)
            )

        has_new_messages = True
        console.log("[%s] >> %s" % (mid, filename))

    return has_new_messages


def generate_feed(wid, config):
    global conn, wechats, cur_dir
    with conn.cursor() as c:
        c.execute('SELECT * FROM accounts WHERE `id`=%s LIMIT 1', (wid))
        account = c.fetchone()

    with conn.cursor() as c:
        c.execute(
            'SELECT * FROM messages WHERE `wechat_id`=%s AND `type` IN %s ORDER BY datetime DESC, id LIMIT %s',
            # TODO Support other message types
            (wid, ['POST'], config.get('feed_max', 20))
        )

        fg = FeedGenerator()
        fg.id('wechat-%s' % wid)
        fg.title(account['name'])
        fg.subtitle(account['intro'])
        fg.link(href='http://feeds.feedburner.com/wechat-%s' % wid, rel='self')
        fg.logo(account['image'])

        message = c.fetchone()
        while message != None:
            mid = message['id']
            filename = path.join(_get_abspath(config.get('message_path', 'messages/'), cur_dir),
                                 wid + '_' + mid + '.json')
            with open(filename, 'r') as fd:
                message_details = json.load(fd)

            if message_details:
                fe = fg.add_entry()
                fe.id(message_details['url'])
                fe.title(message_details['title'])
                fe.author(name=wid, email=message_details['author'])
                fe.link(href=message_details['url'])

                content = re.sub(r'(amp;|\s*data-[\w-]+="[^"]*"|\s*line-height:[^;]*;)', '',
                                 message_details['content'].replace('data-src', 'src'),
                                 flags=re.IGNORECASE)
                if message_details['cover'] != '':
                    content = '<img src="'+ message_details['cover'] + '" />' + content
                fe.content(content)

                dt = datetime.fromtimestamp(message['datetime'], dateutil.tz.gettz(name='Asia/Shanghai'))
                # fe.updated(dt)
                fe.pubdate(dt)

            else:
                console.log("[%s] message does not exist << %s", (mid, filename))

            message = c.fetchone()

        rss_feed = fg.rss_str(pretty=True)
        rss_filename = path.join(_get_abspath(config.get('feed_path', 'feeds/'), cur_dir),
                                  'wechat-' + wid + '.xml')
        fg.rss_file(rss_filename)
        console.log('Output RSS feed to %s' % rss_filename)


def _parse_argv():
    global cur_dir, script_dir
    config = {}

    # load configuration from default config file if exists
    default_config_path = path.join(script_dir, 'config.json')
    if path.isfile(default_config_path):
        with open(default_config_path, 'r') as fd:
            config.update(json.load(fd))

    # print(sys.argv)
    try:
        opts, wids = getopt.getopt(
                sys.argv[1:],
                'hc:',
                ['help', 'config=', 'db-host=', 'db-user=', 'db-password=', 'db-database=', \
                 'message-path=', 'message-types=', 'message-ignore-check', \
                 'feed-max=', 'feed-path=', 'feed-ignore-check']
            )

    except getopt.GetoptError:
        _show_help()

    argv_config = {}
    config['message_type'] = path.join(cur_dir, 'messages/')

    # print(opts)
    for opt, arg in opts:
        # print(opt,arg)
        if opt in ['-h', '--help']:
            _show_help()
        elif opt in ['-c', '--config']:
            try:
                with open(arg, 'r') as fd:
                    config.update(json.load(fd))
            except:
                _show_help('Failed to load custom configurations from given path.')
        elif opt == '--db-host':
            argv_config['db_host'] = arg
        elif opt == '--db-user':
            argv_config['db_user'] = arg
        elif opt == '--db-password':
            argv_config['db_password'] = arg
        elif opt == '--db-database':
            argv_config['db_database'] = arg
        elif opt == '--message-path':
            argv_config['message_path'] = _get_abspath(arg, cur_dir)
        elif opt == '--message-types':
            argv_config['message_types'] = argv.upper().split(',')
        elif opt == '--message-ignore-check':
            argv_config['message_ignore_check'] = True
        elif opt == '--feed-path':
            argv_config['feed_path'] = _get_abspath(arg, cur_dir)
        elif opt == '--feed-max':
            argv_config['feed_max'] = int(arg)
        elif opt == '--feed-ignore-check':
            argv_config['feed_ignore_check'] = True

    if len(wids) == 0:
        _show_help('No wechat id was given.')

    config.update(argv_config)
    config['cur_dir'] = cur_dir
    config['script_dir'] = script_dir

    return config, wids


def _get_abspath(p, base_dir):
    if p.startswith('/'):
        return p
    else:
        return path.join(base_dir, p)


def _show_help(msg=''):
    if msg != '':
        console.error(msg)
    console.log('main.py -[hc] <wechat_ids...>')
    sys.exit(2)


if __name__ == '__main__':
    global conn, wechats

    config, wids = _parse_argv()

    conn = pymysql.connect(
            host=config.get('db_host', 'localhost'),
            user=config.get('db_user', 'root'),
            passwd=config.get('db_password', ''),
            db=config.get('db_database', 'wechat'),
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True
           )
    wechats = WechatSogouApi()

    try:
        for wid in wids:
            has_new_messages = config.get('message_ignore_check', False) or retrieve_messages(wid, config)
            if  has_new_messages or config.get('feed_ignore_check', False):
                console.log("Generating feed for wechat_id=%s..." % wid)
                generate_feed(wid, config)
            else:
                console.success("No new messages.")

    finally:
        conn.close()

