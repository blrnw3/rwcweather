CREATE SCHEMA IF NOT EXISTS wx;

USE wx;

CREATE TABLE IF NOT EXISTS `obs` (
  `t` datetime NOT NULL,
  `src` enum ('live', 'local', 'backfill', 'interpolation') DEFAULT 'live',
  `rain` float unsigned DEFAULT NULL COMMENT 'DAILY total rain',
  `humi` tinyint unsigned DEFAULT NULL,
  `pres` decimal(5,1) unsigned DEFAULT NULL,
  `wind` decimal(3,1) unsigned DEFAULT NULL COMMENT 'avg wind speed over the past 60s',
  `gust` decimal(3,1) unsigned DEFAULT NULL COMMENT 'max gust over the past 60s',
  `temp` decimal(3,1) DEFAULT NULL,
  `wdir` smallint(3) unsigned DEFAULT NULL,
  `solr` smallint(4) unsigned DEFAULT NULL,
  `pm2` smallint(3) unsigned DEFAULT NULL COMMENT 'PM-2.5 level',
  `wet` tinyint unsigned DEFAULT 0 COMMENT '1 if raining else 0',
  `sun` tinyint unsigned DEFAULT 0 COMMENT '1 if sunny else 0',
  `inhumi` tinyint unsigned DEFAULT NULL,
  `intemp` decimal(3,1) DEFAULT NULL,
  `t_obs` datetime NOT NULL COMMENT 'Actual datetime of the observation',
  `t_mod` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'last modified',
  PRIMARY KEY (`t`)
) ENGINE=InnoDB
DEFAULT CHARSET utf8
COMMENT 'Weather observations (once-per-minute sensor readings)';

CREATE TABLE IF NOT EXISTS `avg_extreme` (
  `d` date NOT NULL,
  `var` enum(
        'rain', 'temp', 'humi', 'pres', 'wind', 'gust', 'wdir', 'solr', 'wet', 'sun', 'feels', 'inhumi', 'intemp',
        'night_temp', 'day_temp', 'day_wet', 'rain_rate', 'frost', 'pm2', 'dewpt', 'aqi'
   ) not null,
  `type` enum('avg', 'total', 'min', 'max') not null,
  `period` enum('day') not null default 'day',
  `val` double not null,
  `at` datetime default null comment 'when the extreme val occurred first in the period',
  `cnt` int not null comment 'number of obs involved in avg/extreme',
  `t_mod` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'last modified',
  `overridden` tinyint unsigned DEFAULT 0 COMMENT '1 if manually overridden',
  `comment` varchar(255) DEFAULT NULL COMMENT 'if manually updated, comment optional. e.g. source',
   PRIMARY KEY (`d`, `var`, `type`, `period`),
   KEY `var_type_val` (`var`, `type`, `val`),
   KEY `var_type_d` (`var`, `type`, `d`),
   KEY `d_key` (`d`)
) ENGINE=InnoDB
DEFAULT CHARSET utf8
COMMENT 'Averages, totals, extremes (just daily for now)';

CREATE TABLE IF NOT EXISTS `change_extreme` (
  `d` date NOT NULL,
  `var` enum('rain', 'temp', 'humi', 'pres', 'wind', 'gust', 'solr', 'feels', 'inhumi', 'intemp') not null,
  `type` enum('avg', 'total', 'min', 'max') not null,
  `duration` smallint not null,
  `period` enum('day') not null default 'day',
  `val` double not null,
  `val_exact` decimal(4,2) default null,
  `at` time default null,
   PRIMARY KEY (`d`),
   KEY `var_type_val` (`var`, `type`, `val`),
   KEY `var_type_d` (`var`, `type`, `d`),
   KEY `d_key` (`d`)
) ENGINE=InnoDB
 DEFAULT CHARSET utf8
 COMMENT 'Intra-day change extremes';

CREATE TABLE IF NOT EXISTS `event` (
  `d` date NOT NULL,
  `period` enum('day') not null default 'day',
  `snow` double unsigned DEFAULT NULL,
  `lysnw` decimal(3,1) unsigned DEFAULT NULL,
  `hail` enum('-', 's', 'm', 'l') DEFAULT NULL,
  `thunder` enum('-', 's', 'm', 'l') DEFAULT NULL,
  `fog` boolean DEFAULT NULL,
  `comms` text DEFAULT NULL,
  `extra` text DEFAULT NULL,
  `issues` text DEFAULT NULL,
  `away` boolean DEFAULT null,
   PRIMARY KEY (`d`)
) ENGINE=InnoDB
 DEFAULT CHARSET utf8
 COMMENT 'Event/comment log';

-- Daily anom --
--CREATE TABLE IF NOT EXISTS `anom_daily` (
--  `d` date NOT NULL,
--  `tmin` decimal(3,1) DEFAULT NULL,
--  `tmax` decimal(3,1) DEFAULT NULL,
----   `tmean` decimal(4,2) DEFAULT NULL,
--  `wmean` float unsigned DEFAULT NULL,
--  `rain` float unsigned DEFAULT NULL,
----   `trange` decimal(3,1) unsigned DEFAULT NULL,
--  `sunhr` decimal(3,1) unsigned DEFAULT NULL,
--  `wethr` float unsigned DEFAULT NULL,
--  `hail` float unsigned DEFAULT NULL,
--  `thunder` float unsigned DEFAULT NULL,
--  `fog` float unsigned DEFAULT NULL,
----   `rdays` float unsigned DEFAULT NULL,
--
--  PRIMARY KEY (`d`)
--) ENGINE=InnoDB DEFAULT CHARSET = utf8;
--
--
---- Monthly anom --
--CREATE TABLE IF NOT EXISTS `anom_monthly` (
--  `m` date NOT NULL, -- TODO datatype for months
--  `tmin` decimal(3,1) DEFAULT NULL,
--  `tmax` decimal(3,1) DEFAULT NULL,
--  `tmean` decimal(4,2) DEFAULT NULL,
--  `wmean` decimal(3,1) DEFAULT NULL,
--  `rain` decimal(4,1) unsigned DEFAULT NULL,
--  `trange` decimal(3,1) unsigned DEFAULT NULL,
--  `sunhr` int unsigned DEFAULT NULL,
--  `wethr` int unsigned DEFAULT NULL,
--  `hail` tinyint(2) unsigned DEFAULT NULL,
--  `thunder` tinyint(2) unsigned DEFAULT NULL,
--  `fog` tinyint(2) unsigned DEFAULT NULL,
--
--  `sunmax` int unsigned DEFAULT NULL,
--
--  `rdays` int unsigned DEFAULT NULL,
--  `days_frost` decimal(2,1) unsigned DEFAULT NULL,
--  `days_storm` decimal(2,1) unsigned DEFAULT NULL,
--  `days_snow` decimal(2,1) unsigned DEFAULT NULL,
--  `days_snowfall` decimal(2,1) unsigned DEFAULT NULL,
--
--  PRIMARY KEY (`m`)
--) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8;
