"""Optik testleri için ortak fixture'lar."""
import json

import cv2
import numpy as np
import pytest
from django.conf import settings as dj_settings
from django.contrib.auth.models import User


@pytest.fixture(autouse=True)
def optik_media(settings, tmp_path):
    """Yüklenen dosyalar geçici MEDIA_ROOT'a yazılsın."""
    media = tmp_path / "media"
    media.mkdir()
    settings.MEDIA_ROOT = str(media)
    return media


@pytest.fixture
def user(db):
    return User.objects.create_user(username="optikci", password="x",
                                     first_name="Şükrü", last_name="Işık")


@pytest.fixture
def bubble_map():
    with open(dj_settings.OPTIK_BUBBLE_MAP_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def make_form_image(bubble_map, tmp_path):
    """
    Sentetik (ideal) optik form üretir: 2480×3508 beyaz sayfa, 4 siyah hizalama
    dairesi, gri boş balon çerçeveleri ve istenen öğrenci no / kitapçık /
    cevap balonları dolu. PNG yolunu döndürür.
    """
    m = bubble_map
    counter = {"n": 0}

    def _make(student_no: str, booklet: str, answers, name: str = None) -> str:
        img = np.full((m["page"]["height_px"], m["page"]["width_px"], 3), 255, np.uint8)
        for p in m["alignment"]["points"]:
            cv2.circle(img, (int(round(p["x"])), int(round(p["y"]))), 55, (0, 0, 0), -1)

        def bubble(x, y, filled):
            center = (int(round(x)), int(round(y)))
            if filled:
                cv2.circle(img, center, 18, (30, 30, 30), -1)
            else:
                cv2.circle(img, center, 19, (150, 150, 150), 2)

        sn = m["student_no"]
        for col in range(sn["cols"]):
            for row in range(sn["rows"]):
                bubble(sn["anchor"]["x"] + col * sn["dx"], sn["anchor"]["y"] + row * sn["dy"],
                       col < len(student_no) and int(student_no[col]) == sn["row_labels"][row])

        bk = m["booklet"]
        for i, label in enumerate(bk["labels"]):
            bubble(bk["anchor"]["x"] + i * bk["dx"], bk["anchor"]["y"], label == booklet)

        an = m["answers"]
        for q in range(an["rows"]):
            for c, label in enumerate(an["col_labels"]):
                bubble(an["anchor"]["x"] + c * an["dx"], an["anchor"]["y"] + q * an["dy"],
                       q < len(answers) and answers[q] == label)

        counter["n"] += 1
        path = tmp_path / (name or f"form_{counter['n']}.png")
        assert cv2.imwrite(str(path), img)
        return str(path)

    return _make
