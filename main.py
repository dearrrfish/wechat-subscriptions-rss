#!/usr/bin/env python3

import json
import sys
import pymysql.cursors
from datetime import datetime
import dateutil.tz
from feedgen.feed import FeedGenerator

sys.path.append('./WechatSogou')

from wechatsogou.tools import *
from wechatsogou import *

message_path = 'messages/'
feed_path = 'feeds/'

def retrieve_messages(wid, conn):
    has_new_messages = False
    messages = []
    wechats = WechatSogouApi()

    exists_account = False
    print("Searching for existing account...")
    with conn.cursor() as c:
        c.execute('SELECT id FROM `accounts` WHERE id = %s', (wid))
        exists_account = c.fetchone() != None

    if not exists_account:
        print("Not found. Retrieving account info and recent messages...")
        # Retrieve both account and recent messages
        messages_and_info = wechats.get_gzh_message_and_info(wechatid=wid)
        # print(messages_and_info)
        messages = messages_and_info['gzh_messages']
        # Store account info in database
        gzh_info = messages_and_info['gzh_info']

        with conn.cursor() as c:
            c.execute(
                'INSERT INTO `accounts` (id, name, auth, intro, image) VALUES (%s, %s, %s, %s, %s)',
                (wid, gzh_info['name'], gzh_info['renzhen'], gzh_info['jieshao'], gzh_info['img'])
            )

    else:
        print("Account exists. Retrieving recent messages...")
        messages = wechats.get_gzh_message(wechatid=wid)

    # print(messages)
    print("Num of messages: ", len(messages))

    for m in messages:
        exists_message = False
        # Message ID
        mid = m['qunfa_id']
        with conn.cursor() as c:
            # Lookup in database for existing message
            c.execute('SELECT id FROM `messages` WHERE wechat_id=%s AND id=%s', (wid, mid))
            exists_message = c.fetchone() != None

        if exists_message:
            print("[%s] message exists, skip." % (mid))
            continue

        # New message
        has_new_messages = True
        mdatetime = m['datetime']
        mtype = m['type']
        message = {}
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

        filename = message_path + wid + '_' + str(mid) + '.json'
        with open(filename, 'w') as fd:
            json.dump(message, fd)

        # Store in database
        with conn.cursor() as c:
            c.execute(
                'INSERT INTO `messages` (id, wechat_id, datetime, type) VALUES (%s, %s, %s, %s)',
                (mid, wid, mdatetime, message_type)
            )

        print("[%s] >> %s" % (mid, filename))

    return has_new_messages


def generate_feed(wid, conn, max=40, message_types=['POST']):
    with conn.cursor() as c:
        c.execute('SELECT * FROM accounts WHERE `id`=%s LIMIT 1', (wid))
        account = c.fetchone()

    with conn.cursor() as c:
        c.execute(
            'SELECT * FROM messages WHERE `wechat_id`=%s AND `type` IN %s ORDER BY datetime DESC LIMIT %s',
            (wid, message_types, max)
        )

        fg = FeedGenerator()
        fg.id('wechat-%s' % wid)
        fg.title(account['name'])
        fg.subtitle(account['intro'])
        fg.link(href='http://localhost/feeds/wechat-%s.atom' % wid, rel='self')
        fg.logo(account['image'])

        message = c.fetchone()
        while message != None:
            mid = message['id']
            filename = message_path + wid + '_' + str(mid) + '.json'
            with open(filename, 'r') as fd:
                message_details = json.load(fd)

            if message_details:
                fe = fg.add_entry()
                fe.id(message_details['url'])
                fe.title(message_details['title'])
                fe.author(name=message_details['author'])
                fe.link(href=message_details['url'])
                fe.content(message_details['content'])

                dt = datetime.fromtimestamp(message['datetime'], dateutil.tz.gettz(name='Asia/Shanghai'))
                fe.updated(dt)

            else:
                print("[%s] message does not exist << %s", (mid, filename))

            message = c.fetchone()

        atom_feed = fg.atom_str(pretty=True)
        atom_filename = feed_path + 'wechat-' + wid + '.atom'
        fg.atom_file(atom_filename)


if __name__ == '__main__':
    wid = sys.argv[1]
    if not wid:
        print('No wechatid provided.')
        sys.exit(2)

    conn = pymysql.connect(
            host='localhost',
            user='root',
            passwd='momo88415',
            db='wechat',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True
           )

    print("wid = %s" % (wid))
    try:
        has_new_messages = retrieve_messages(wid, conn)
        # if has_new_messages:
        print("Generating feed...")
        generate_feed(wid, conn)

    finally:
        conn.close()
