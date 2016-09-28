
DROP TABLE IF EXISTS `wechat`.`messages`;
DROP TABLE IF EXISTS `wechat`.`accounts`;

CREATE TABLE `wechat`.`accounts` (
    `id` varchar(32) NOT NULL COMMENT 'Wechat official account.',
    `name` varchar(256) NOT NULL COMMENT 'Account name.',
    `auth` varchar(256) COMMENT 'Authorization of account.',
    `intro` text CHARACTER SET utf8 COLLATE utf8_general_ci COMMENT 'Short description of account.',
    `image` varchar(512) COMMENT 'Account image.',
    PRIMARY KEY (`id`)
)
CHARACTER SET utf8 COLLATE utf8_general_ci
COMMENT = 'Storage of posts in Wechat subscriptions.';

CREATE TABLE `wechat`.`messages` (
    `id` int(16) NOT NULL COMMENT 'Group message ID.',
    `wechat_id` varchar(100) NOT NULL COMMENT 'Wechat ID of subscription post.',
    `datetime` int(10) NOT NULL COMMENT 'Message timestamp.',
    `type` enum('TEXT', 'IMAGE', 'VOICE', 'POST', 'VIDEO') NOT NULL COMMENT 'Message type',
    PRIMARY KEY (`wechat_id`, `id`),
    CONSTRAINT `fk_wechat_id` FOREIGN KEY `fk_wechat_id` (`wechat_id`)
        REFERENCES `wechat`.`accounts` (`id`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT
)
CHARACTER SET utf8 COLLATE utf8_general_ci
COMMENT = 'Storage of posts in Wechat subscriptions.';
