## RSS Feed Generator for Wechat Official Accounts

> Python3 only! Sogou crawler credit to [Chyroc/WechatSogou](https://github.com/Chyroc/WechatSogou/)!

### Installation:

```shell
# Install dependecies
pip3 install lxml feedgen python-dateutil requests Werkzeug PyMySQL

# Clone repo
git clone https://github.com/dearrrfish/wechat-subscriptions-rss wrss
cd wrss

# Initialize database
# Create a database named `wechat`, then:
mysql -u root -p < sql/000-init.sql

# Copy from example of `config.json`, edit as your preferences
cp config.json.example config.json
vim config.json

# Run to test
python3 main.py dapapi
```



### Syntax:

`python3 main.py [-options] wechat_ids...`

#### Options:

- `-c|--config` - given path of custom config file, eg. `-c ~/config.wrss.json`
- `--db-host, --db-user, --db-password, --db-database` - override database parameters
- `--message-path` - custom location to store json files of message details, default: `messages/`
- `--message-types` - message types included in final feed. (unfinished, force to be `POST`)
- `--message-ignore-check` - skip fetching new messages, dev use
- `--feed-path` - custom location to output RSS feed xml file, default: `feeds/`
- `--feed-max` - max number of messages adding into feed, default: 20
- `--feed-ignore-check` - skip checking if has_new_messages, force generating feed
- `--syslog` - output log messages to syslog



#### Examples:

```shell
python3 main.py --feed-path /var/www/wrss/ --feed-ignore-check --syslog dsmovie sensualguru
```

