"""Webcam fog: frames judged by the Weather bot's vision-LLM client (scripts/fog_judge.py), posted to
POST /api/inferred/fog, stored in obs_inferred (kind='fog') and rolled up into avg_extreme var='fog' (hours).
Fog days are derived at query time: days with fog hours > 0 (rwcwx/fog/derive.py).
See research/fog/PIPELINE_PLAN.md."""
