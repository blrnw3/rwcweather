"""scripts/cam_save.sh fallback freshness and scripts/cam_archive.sh skip rules (frozen / stale / empty sources)."""
import os
import shutil
import subprocess
import time

import pytest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SAVE = os.path.join(ROOT, "scripts", "cam_save.sh")
ARCHIVE = os.path.join(ROOT, "scripts", "cam_archive.sh")

pytestmark = pytest.mark.skipif(not (shutil.which("bash") and shutil.which("find") and shutil.which("md5sum")),
                                reason="needs bash, GNU find and md5sum")


def write(path, data, age_s=0):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    t = time.time() - age_s
    os.utime(path, (t, t))


def pick(cum):
    r = subprocess.run(["bash", "-c", f'source "{SAVE}"; pick'], env=dict(os.environ, RWC_CUM=str(cum)),
                       capture_output=True, text=True, check=True)
    return r.stdout


def test_pick_ignores_stale_wxcam_fallback(tmp_path):
    os.makedirs(tmp_path / "camftp")
    write(tmp_path / "wxcam_raw_08.jpg", b"a", age_s=4 * 86400)   # stopped uploader, days old
    write(tmp_path / "wxcam_raw_09.jpg", b"b", age_s=4 * 86400)
    assert pick(tmp_path) == ""                                     # nothing fresh: leave outputs alone
    write(tmp_path / "wxcam_raw_10.jpg", b"c", age_s=10 * 60)       # older than 3 min: still stale
    assert pick(tmp_path) == ""


def test_pick_uses_fresh_wxcam_second_newest(tmp_path):
    os.makedirs(tmp_path / "camftp")
    write(tmp_path / "wxcam_raw_00.jpg", b"old", age_s=86400)
    write(tmp_path / "wxcam_raw_01.jpg", b"x", age_s=60)
    write(tmp_path / "wxcam_raw_02.jpg", b"y", age_s=5)             # newest may be mid-upload
    assert pick(tmp_path) == str(tmp_path / "wxcam_raw_01.jpg")


def test_pick_prefers_camera_ftp(tmp_path):
    write(tmp_path / "wxcam_raw_01.jpg", b"x", age_s=5)
    d = tmp_path / "camftp" / "cam" / "2026-10-21" / "001" / "jpg" / "13" / "50"
    write(d / "01.jpg", b"1", age_s=20)
    write(d / "04.jpg", b"2", age_s=2)
    assert pick(tmp_path) == str(d / "01.jpg")


def run_archive(cum, state, ts):
    env = dict(os.environ, RWC_CUM=str(cum), CAM_ARCHIVE_STATE=str(state), CAM_ARCHIVE_TS=ts)
    subprocess.run(["bash", ARCHIVE], env=env, check=True, capture_output=True)


def archived(cum, size):
    return sorted(os.listdir(cum / "camdump" / size))


@pytest.fixture
def cum(tmp_path):
    c = tmp_path / "cumulus"
    for s in ("sky_sm", "sky_lg", "sky_xl"):
        os.makedirs(c / "camdump" / s)
    os.makedirs(c / "camftp")
    return c


def set_outputs(cum, tag, age_s=0):
    for name in ("skycam_raw.jpg", "skycam_large.jpg", "skycam_small.jpg"):
        write(cum / name, f"{name}:{tag}".encode(), age_s=age_s)


def test_archive_skips_repeats_stale_and_empty(cum, tmp_path):
    st = tmp_path / "state"
    set_outputs(cum, "1")
    run_archive(cum, st, "20261021_2000")
    assert archived(cum, "sky_lg") == ["20261021_2000.jpg"]
    run_archive(cum, st, "20261021_2001")                          # same image (frozen camera): skipped
    assert archived(cum, "sky_lg") == ["20261021_2000.jpg"]
    set_outputs(cum, "2")
    run_archive(cum, st, "20261021_2002")                          # new image: archived
    assert archived(cum, "sky_lg") == ["20261021_2000.jpg", "20261021_2002.jpg"]
    set_outputs(cum, "3", age_s=10 * 60)                            # changed, but not updated for > 3 min
    run_archive(cum, st, "20261021_2003")
    assert archived(cum, "sky_xl") == ["20261021_2000.jpg", "20261021_2002.jpg"]
    for name in ("skycam_raw.jpg", "skycam_large.jpg", "skycam_small.jpg"):
        write(cum / name, b"")                                     # empty source never archived
    run_archive(cum, st, "20261021_2004")
    for s in ("sky_sm", "sky_lg", "sky_xl"):
        assert archived(cum, s) == ["20261021_2000.jpg", "20261021_2002.jpg"]
    assert not [f for f in os.listdir(cum / "camdump" / "sky_lg") if f.startswith(".")]   # no temp left behind


def test_archive_missing_source_is_not_an_error(cum, tmp_path):
    run_archive(cum, tmp_path / "state", "20261021_2000")
    assert archived(cum, "sky_lg") == []
