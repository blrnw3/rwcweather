-- avg_extreme.var: add 'rain10' and 'rain60' (daily max rain in any 10 / 60 minutes, type 'max', at = time reached).
-- Appends to the enum, so existing rows are untouched (no table rebuild on MariaDB/MySQL for an append).
-- Apply BEFORE deploying the backend that writes them (save_latest would log "wet/intensity update failed"):
--   mysql wx < data/migrations/20261014_avg_extreme_rain10_rain60.sql
ALTER TABLE `avg_extreme`
  MODIFY `var` enum('rain','temp','humi','pres','wind','gust','wdir','solr','wet','sun','feels','inhumi','intemp',
    'night_temp','day_temp','day_wet','rain_rate','frost','pm2','dewpt','aqi','rain10','rain60') NOT NULL;
