from datetime import datetime
from enum import StrEnum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator


class Gender(StrEnum):
    MALE = "male"
    FEMALE = "female"


class HeavenlyStem(StrEnum):
    """天干"""

    JIA = "甲"
    YI = "乙"
    BING = "丙"
    DING = "丁"
    WU = "戊"
    JI = "己"
    GENG = "庚"
    XIN = "辛"
    REN = "壬"
    GUI = "癸"


class EarthlyBranch(StrEnum):
    """地支"""

    ZI = "子"
    CHOU = "丑"
    YIN = "寅"
    MAO = "卯"
    CHEN = "辰"
    SI = "巳"
    WU = "午"
    WEI = "未"
    SHEN = "申"
    YOU = "酉"
    XU = "戌"
    HAI = "亥"


class FiveElement(StrEnum):
    """五行"""

    METAL = "金"
    WOOD = "木"
    WATER = "水"
    FIRE = "火"
    EARTH = "土"


class TenGod(StrEnum):
    """十神"""

    BI_JIAN = "比肩"
    JIE_CAI = "劫财"
    SHI_SHEN = "食神"
    SHANG_GUAN = "伤官"
    PIAN_CAI = "偏财"
    ZHENG_CAI = "正财"
    QI_SHA = "七杀"
    ZHENG_GUAN = "正官"
    PIAN_YIN = "偏印"
    ZHENG_YIN = "正印"


class LuckDirection(StrEnum):
    FORWARD = "forward"
    BACKWARD = "backward"


# --- 领域五行映射（非自研算法，仅属固定映射） ---
STEM_ELEMENT_MAP: dict[HeavenlyStem, FiveElement] = {
    HeavenlyStem.JIA: FiveElement.WOOD,
    HeavenlyStem.YI: FiveElement.WOOD,
    HeavenlyStem.BING: FiveElement.FIRE,
    HeavenlyStem.DING: FiveElement.FIRE,
    HeavenlyStem.WU: FiveElement.EARTH,
    HeavenlyStem.JI: FiveElement.EARTH,
    HeavenlyStem.GENG: FiveElement.METAL,
    HeavenlyStem.XIN: FiveElement.METAL,
    HeavenlyStem.REN: FiveElement.WATER,
    HeavenlyStem.GUI: FiveElement.WATER,
}

BRANCH_ELEMENT_MAP: dict[EarthlyBranch, FiveElement] = {
    EarthlyBranch.ZI: FiveElement.WATER,
    EarthlyBranch.CHOU: FiveElement.EARTH,
    EarthlyBranch.YIN: FiveElement.WOOD,
    EarthlyBranch.MAO: FiveElement.WOOD,
    EarthlyBranch.CHEN: FiveElement.EARTH,
    EarthlyBranch.SI: FiveElement.FIRE,
    EarthlyBranch.WU: FiveElement.FIRE,
    EarthlyBranch.WEI: FiveElement.EARTH,
    EarthlyBranch.SHEN: FiveElement.METAL,
    EarthlyBranch.YOU: FiveElement.METAL,
    EarthlyBranch.XU: FiveElement.EARTH,
    EarthlyBranch.HAI: FiveElement.WATER,
}


class BirthProfile(BaseModel):
    """出生输入事实契约，仅记录客观输入，不包含计算过程参数"""

    model_config = ConfigDict(extra="forbid")

    year: int = Field(ge=1, le=9999, description="公历出生年份")
    month: int = Field(ge=1, le=12, description="公历出生月份")
    day: int = Field(ge=1, le=31, description="公历出生日期")
    hour: int = Field(ge=0, le=23, description="当地民用时小时，0-23")
    minute: int = Field(ge=0, le=59, description="分钟，0-59")
    gender: Gender = Field(description="用于确定大运顺逆的性别参数")
    birth_place_text: Optional[str] = Field(
        default=None, description="可选出生地原始文本，v2.0 不参与排盘"
    )

    @field_validator("birth_place_text")
    @classmethod
    def clean_birth_place(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        return stripped if stripped else None

    @model_validator(mode="after")
    def validate_date_time(self) -> "BirthProfile":
        """验证组合后的年月日时分是否为真实存在日期（如闰年检查）"""
        try:
            datetime(self.year, self.month, self.day, self.hour, self.minute)
        except ValueError as e:
            raise ValueError(f"非法的日期时间组合: {e}")

        return self


class GanZhi(BaseModel):
    """干支组合值对象"""

    model_config = ConfigDict(extra="forbid")

    stem: HeavenlyStem
    branch: EarthlyBranch

    @computed_field
    @property
    def gan_zhi(self) -> str:
        """派生字段，自动拼接天干地支，避免重复存储与状态不一致"""
        return f"{self.stem.value}{self.branch.value}"


class HiddenStem(BaseModel):
    """藏干与地支十神绑定结构"""

    model_config = ConfigDict(extra="forbid")

    stem: HeavenlyStem
    ten_god: TenGod

    @computed_field
    @property
    def element(self) -> FiveElement:
        """天干所属五行是确定性映射，由模型派生，避免状态矛盾"""
        return STEM_ELEMENT_MAP[self.stem]


class Pillar(BaseModel):
    """四柱结构，整合干支、五行、十神及藏干"""

    model_config = ConfigDict(extra="forbid")

    gan_zhi: GanZhi
    # 日柱的天干自身即为日主，无相对于自身的“十神”概念，故可为 None
    stem_ten_god: Optional[TenGod]
    hidden_stems: list[HiddenStem] = Field(min_length=1)

    @computed_field
    @property
    def stem_element(self) -> FiveElement:
        return STEM_ELEMENT_MAP[self.gan_zhi.stem]

    @computed_field
    @property
    def branch_element(self) -> FiveElement:
        return BRANCH_ELEMENT_MAP[self.gan_zhi.branch]


class BaziCalculationMethod(BaseModel):
    """排盘溯源参数，描述本次排盘基于的底层库和流派规则"""

    model_config = ConfigDict(extra="forbid")

    library: Literal["lunar_python"] = "lunar_python"
    library_version: str = Field(min_length=1)

    """
    四柱晚子时规则
    sect = 2 → 晚子时日柱按当天
    sect = 1 → 晚子时日柱按明天
    """
    late_zi_sect: Literal[2] = 2
    """
    起运时间计算规则
    yun sect = 1 → 按天数和时辰数换算
    yun sect = 2 → 按分钟数换算
    """
    yun_sect: Literal[1] = 1

    time_basis: Literal["local_civil_time_as_provided"] = "local_civil_time_as_provided"

    true_solar_time: Literal[False] = False
    birth_place_affects_calculation: Literal[False] = False


class LuckStartOffset(BaseModel):
    """起运偏移量"""

    model_config = ConfigDict(extra="forbid")

    years: int
    months: int
    days: int
    hours: int


class DaYunPeriod(BaseModel):
    """单步大运"""

    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=1)
    start_year: int
    start_age: int = Field(ge=1)
    gan_zhi: GanZhi


class DaYunResult(BaseModel):
    """大运计算结果集合"""

    model_config = ConfigDict(extra="forbid")

    direction: LuckDirection
    start_offset: LuckStartOffset
    start_at: datetime
    periods: list[DaYunPeriod] = Field(min_length=1)


class BaziChart(BaseModel):
    """八字排盘顶层聚合根"""

    model_config = ConfigDict(extra="forbid")

    year_pillar: Pillar
    month_pillar: Pillar
    day_pillar: Pillar
    hour_pillar: Pillar
    da_yun: DaYunResult
    calculation_method: BaziCalculationMethod

    @computed_field
    @property
    def day_master(self) -> HeavenlyStem:
        """派生字段：日主，固定从日柱天干读取，防止数据冗余和不一致"""
        return self.day_pillar.gan_zhi.stem
