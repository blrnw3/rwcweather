-- Fog from the webcam (rwcwx/fog, POST /api/inferred/fog).
--  * obs_inferred.note: free-text reason from the classifier (the LLM judge's one-line reason for fog rows).
--  * avg_extreme.var: append 'fog' (daily fog hours, type 'total') and 'fogday' (1/0 fog seen that morning, type 'total').
-- Both are appends (new nullable column, enum values at the end), so existing rows are untouched.
-- Apply BEFORE deploying the backend that writes them:
--   mysql wx < data/migrations/20261016_fog.sql
ALTER TABLE `obs_inferred`
  ADD COLUMN `note` varchar(255) DEFAULT NULL COMMENT 'classifier reason / free text, e.g. the fog judge''s reason' AFTER `model_version`;
ALTER TABLE `avg_extreme`
  MODIFY `var` enum('rain','temp','humi','pres','wind','gust','wdir','solr','wet','sun','feels','inhumi','intemp',
    'night_temp','day_temp','day_wet','rain_rate','frost','pm2','dewpt','aqi','rain10','rain60','fog','fogday') NOT NULL;
