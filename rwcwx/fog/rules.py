"""Pure fog rules (no DB): the decision for one judged frame, the rain veto and the daily rollup.

Decision (Ben, 2026-10-16):
  fog = judge says yes AND confidence >= THRESHOLD AND the frame passed the client's gates AND no rain veto.
Rain veto: rain and fog don't really coexist here, so >= VETO_MIN_TIPS rain-gauge tips (0.01 in each) within
  +/- VETO_WINDOW_MIN of the frame force fog = no, whatever the judge said. The judge's answer is kept
  (prob, note) for audit and the row is flagged 'rain_veto'.
Window: frames from sun elevation >= MIN_ELEV_DEG (dawn) to LAST_LOCAL_HOUR:00 local time (1 pm PT).
Rollup: each judged frame stands for FRAME_MIN minutes. Daily fog hours = fog frames x FRAME_MIN / 60;
  a fog day (derived at query time) is a day with fog hours > 0. Nothing is stored unless >= MIN_COVERAGE of the window's frames
  were judged (gated frames don't count as judged).
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable, List, Optional, Sequence

THRESHOLD = 0.85
VETO_MIN_TIPS = 2
VETO_WINDOW_MIN = 30
TIP_IN = 0.01
FRAME_MIN = 30
MIN_ELEV_DEG = 5.0
LAST_LOCAL_HOUR = 13
MIN_COVERAGE = 0.5

KIND = "fog"
GATE_FLAGS = ("ir", "glitch", "frozen", "lowsun", "missing", "unusable", "judge_err")
VETO_FLAG = "rain_veto"
NOTE_MAX = 255


def tips_near(t: datetime, tips: Iterable[tuple], window_min: int = VETO_WINDOW_MIN) -> int:
    """Number of 0.01 in tips within +/- window of t. tips = (t, amount_in) pairs, naive UTC like obs.t."""
    w = timedelta(minutes=window_min)
    return int(round(sum(a for tt, a in tips if t - w <= tt <= t + w) / TIP_IN))


def parse_flags(flags: Optional[str]) -> List[str]:
    return [f.strip() for f in (flags or "").split(",") if f.strip()]


def join_flags(flags: Sequence[str]) -> Optional[str]:
    out = []
    for f in flags:
        if f and f not in out:
            out.append(f)
    return ",".join(out)[:64] or None


@dataclass
class Decision:
    value: Optional[int]     # 1 fog, 0 no fog, None = not judged (gated / judge error)
    flags: Optional[str]


def decide(fog: Optional[bool], confidence: Optional[float], flags: Optional[str], n_tips: int,
           threshold: float = THRESHOLD, veto_min_tips: int = VETO_MIN_TIPS) -> Decision:
    fl = [f for f in parse_flags(flags) if f != VETO_FLAG]
    if any(f in GATE_FLAGS for f in fl) or fog is None:
        return Decision(None, join_flags(fl))
    if n_tips >= veto_min_tips:
        return Decision(0, join_flags(fl + [VETO_FLAG]))
    return Decision(int(bool(fog) and confidence is not None and confidence >= threshold), join_flags(fl))


@dataclass
class FogDay:
    d: date
    fog_h: float
    fog_frames: int
    judged: int
    expected: int

    @property
    def coverage(self) -> float:
        return self.judged / self.expected if self.expected else 0.0

    @property
    def storable(self) -> bool:
        return self.expected > 0 and self.coverage >= MIN_COVERAGE

    @property
    def comment(self) -> str:
        return f"webcam LLM judge, {FRAME_MIN}-min frames dawn-{LAST_LOCAL_HOUR}:00; coverage {self.coverage:.0%}"


def rollup(d: date, values: Iterable[Optional[int]], expected: int, frame_min: int = FRAME_MIN) -> FogDay:
    vals = list(values)
    judged = [v for v in vals if v is not None]
    n_fog = sum(1 for v in judged if v == 1)
    return FogDay(d=d, fog_h=round(n_fog * frame_min / 60.0, 2),
                  fog_frames=n_fog, judged=len(judged), expected=max(expected, len(judged)))


def window_frames(d: date) -> List[datetime]:
    """Naive-UTC frame times (:00 and :30) for local day d, from the first with sun elevation >= MIN_ELEV_DEG
    up to (not including) LAST_LOCAL_HOUR:00 local. These are the frames the judge client should send."""
    from dateutil import tz
    from rwcwx.sun.solar import solar_pos
    zone = tz.gettz("America/Los_Angeles")
    utc = tz.UTC
    out = []
    t = datetime(d.year, d.month, d.day, 3, 0, tzinfo=zone)
    end = datetime(d.year, d.month, d.day, LAST_LOCAL_HOUR, 0, tzinfo=zone)
    started = False
    while t < end:
        tu = t.astimezone(utc).replace(tzinfo=None)
        if started or solar_pos(tu)[0] >= MIN_ELEV_DEG:
            started = True
            out.append(tu)
        t = (t.astimezone(utc) + timedelta(minutes=FRAME_MIN)).astimezone(zone)
    return out


def local_date_of(t_utc: datetime) -> date:
    from dateutil import tz
    return t_utc.replace(tzinfo=tz.UTC).astimezone(tz.gettz("America/Los_Angeles")).date()
