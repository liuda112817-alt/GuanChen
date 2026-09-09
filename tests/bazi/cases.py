from datetime import datetime
from typing import NamedTuple, Optional

from guanchen_v2.models.bazi import BirthProfile, Gender, LuckDirection


class BaziCase(NamedTuple):
    case_id: str
    rationale: str
    profile: BirthProfile
    expected_pillars: tuple[str, str, str, str]
    expected_day_master: str
    expected_direction: Optional[LuckDirection] = None
    expected_start_offset: Optional[tuple[int, int, int]] = None
    expected_start_at: Optional[datetime] = None


BAZI_GOLDEN_CASES = [
    BaziCase(
        case_id="F01",
        rationale="普通四柱 mapping，来源官方 Python Test",
        profile=BirthProfile(year=2005, month=12, day=23, hour=8, minute=37, gender=Gender.MALE),
        expected_pillars=("乙酉", "戊子", "辛巳", "壬辰"),
        expected_day_master="辛",
        expected_direction=LuckDirection.BACKWARD,
    ),
    BaziCase(
        case_id="F02",
        rationale="23:30 晚子时 sect=2，来源官方 Python Test",
        profile=BirthProfile(year=1988, month=2, day=15, hour=23, minute=30, gender=Gender.MALE),
        expected_pillars=("戊辰", "甲寅", "庚子", "戊子"),
        expected_day_master="庚",
    ),
    BaziCase(
        case_id="F03",
        rationale="22:30 晚子时前边界对照",
        profile=BirthProfile(year=1988, month=2, day=15, hour=22, minute=30, gender=Gender.MALE),
        expected_pillars=("戊辰", "甲寅", "庚子", "丁亥"),
        expected_day_master="庚",
    ),
    BaziCase(
        case_id="F04",
        rationale="女运与起运日期，来源官方 YunTest",
        profile=BirthProfile(year=1981, month=1, day=29, hour=23, minute=37, gender=Gender.FEMALE),
        expected_pillars=("庚申", "己丑", "丁未", "壬子"),
        expected_day_master="丁",
        expected_start_offset=(8, 0, 20),
        expected_start_at=datetime(1989, 2, 18, 23, 37),
        expected_direction=LuckDirection.BACKWARD,
    ),
    BaziCase(
        case_id="F05",
        rationale="男运 yun_sect=1，GuanChen baseline，官方断言起运日期",
        profile=BirthProfile(year=2022, month=3, day=9, hour=20, minute=51, gender=Gender.MALE),
        expected_pillars=("壬寅", "癸卯", "辛酉", "戊戌"),
        expected_day_master="辛",
        expected_start_offset=(8, 9, 10),
        expected_start_at=datetime(2030, 12, 19, 20, 51),
        expected_direction=LuckDirection.FORWARD,
    ),
    BaziCase(
        case_id="F06",
        rationale="男运：与 F07 对照，性别不污染四柱",
        profile=BirthProfile(year=2024, month=5, day=1, hour=12, minute=0, gender=Gender.MALE),
        expected_pillars=("甲辰", "戊辰", "乙丑", "壬午"),
        expected_day_master="乙",
        expected_direction=LuckDirection.FORWARD,
    ),
    BaziCase(
        case_id="F07",
        rationale="女运：与 F06 对照，性别不污染四柱",
        profile=BirthProfile(year=2024, month=5, day=1, hour=12, minute=0, gender=Gender.FEMALE),
        expected_pillars=("甲辰", "戊辰", "乙丑", "壬午"),
        expected_day_master="乙",
        expected_direction=LuckDirection.BACKWARD,
    ),
    BaziCase(
        case_id="F08",
        rationale="闰二月中段 regression fixture",
        profile=BirthProfile(year=2023, month=4, day=6, hour=10, minute=0, gender=Gender.MALE),
        expected_pillars=("癸卯", "丙辰", "甲午", "己巳"),
        expected_day_master="甲",
    ),
    BaziCase(
        case_id="F09",
        rationale="真正闰二月开始边界 (2023-03-22 闰二月初一)",
        profile=BirthProfile(year=2023, month=3, day=22, hour=10, minute=0, gender=Gender.MALE),
        expected_pillars=("癸卯", "乙卯", "己卯", "己巳"),
        expected_day_master="己",
    ),
]
