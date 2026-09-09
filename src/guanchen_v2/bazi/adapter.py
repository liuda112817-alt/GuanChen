from datetime import datetime
from importlib.metadata import version

from lunar_python import Solar

from guanchen_v2.bazi.exceptions import BaziAdapterError
from guanchen_v2.models.bazi import (
    BaziCalculationMethod,
    BaziChart,
    BirthProfile,
    DaYunPeriod,
    DaYunResult,
    EarthlyBranch,
    GanZhi,
    Gender,
    HeavenlyStem,
    HiddenStem,
    LuckDirection,
    LuckStartOffset,
    Pillar,
    TenGod,
)


class LunarPythonBaziAdapter:
    """lunar_python 官方排盘实现与 GuanChen 领域模型的防腐层映射器。"""

    def _get_library_version(self) -> str:
        return version("lunar_python")

    def _parse_gan_zhi(self, gz_str: str) -> GanZhi:
        if not gz_str or len(gz_str) != 2:
            raise ValueError(f"非法的干支字符串: '{gz_str}'")
        return GanZhi(
            stem=HeavenlyStem(gz_str[0]),
            branch=EarthlyBranch(gz_str[1]),
        )

    def _build_pillar(
        self,
        gan: str,
        zhi: str,
        stem_ten_god_str: str | None,
        hide_gans: list[str],
        hide_ten_god: list[str],
    ) -> Pillar:
        gz = GanZhi(stem=HeavenlyStem(gan), branch=EarthlyBranch(zhi))
        stem_ten_god = TenGod(stem_ten_god_str) if stem_ten_god_str else None

        hidden_stem = []
        # 使用 strict=True 确保藏干与十神数量严格一致，防止库隐式 API 漂移
        for hg, htg in zip(hide_gans, hide_ten_god, strict=True):
            hidden_stem.append(HiddenStem(stem=HeavenlyStem(hg), ten_god=TenGod(htg)))

        return Pillar(
            gan_zhi=gz,
            stem_ten_god=stem_ten_god,
            hidden_stems=hidden_stem,
        )

    def calculate(self, profile: BirthProfile) -> BaziChart:
        try:
            solar = Solar.fromYmdHms(
                profile.year, profile.month, profile.day, profile.hour, profile.minute, 0
            )
            lunar = solar.getLunar()
            eight_char = lunar.getEightChar()

            # 锁定晚子时配置
            eight_char.setSect(2)

            year_pillar = self._build_pillar(
                eight_char.getYearGan(),
                eight_char.getYearZhi(),
                eight_char.getYearShiShenGan(),
                eight_char.getYearHideGan(),
                eight_char.getYearShiShenZhi(),
            )

            month_pillar = self._build_pillar(
                eight_char.getMonthGan(),
                eight_char.getMonthZhi(),
                eight_char.getMonthShiShenGan(),
                eight_char.getMonthHideGan(),
                eight_char.getMonthShiShenZhi(),
            )

            day_pillar = self._build_pillar(
                eight_char.getDayGan(),
                eight_char.getDayZhi(),
                None,  # 明确规定日主不暴露十神关系
                eight_char.getDayHideGan(),
                eight_char.getDayShiShenZhi(),
            )

            hour_pillar = self._build_pillar(
                eight_char.getTimeGan(),
                eight_char.getTimeZhi(),
                eight_char.getTimeShiShenGan(),
                eight_char.getTimeHideGan(),
                eight_char.getTimeShiShenZhi(),
            )

            # 锁定性别映射与起运算法配置 (sect=1)
            gender_int = 1 if profile.gender == Gender.MALE else 0
            yun = eight_char.getYun(gender=gender_int, sect=1)

            start_solar = yun.getStartSolar()
            start_at = datetime(
                start_solar.getYear(),
                start_solar.getMonth(),
                start_solar.getDay(),
                start_solar.getHour(),
                start_solar.getMinute(),
                start_solar.getSecond(),
            )

            da_yuns = yun.getDaYun()
            periods = []
            for dy in da_yuns:
                # 过滤掉库实现细节中的 index=0 预备期
                if dy.getIndex() == 0:
                    continue
                periods.append(
                    DaYunPeriod(
                        index=dy.getIndex(),
                        start_year=dy.getStartYear(),
                        start_age=dy.getStartAge(),
                        gan_zhi=self._parse_gan_zhi(dy.getGanZhi()),
                    )
                )

            da_yun_result = DaYunResult(
                direction=LuckDirection.FORWARD if yun.isForward() else LuckDirection.BACKWARD,
                start_offset=LuckStartOffset(
                    years=yun.getStartYear(),
                    months=yun.getStartMonth(),
                    days=yun.getStartDay(),
                    hours=yun.getStartHour(),
                ),
                start_at=start_at,
                periods=periods,
            )

            method = BaziCalculationMethod(
                library_version=self._get_library_version(),
                late_zi_sect=2,
                yun_sect=1,
            )

            return BaziChart(
                year_pillar=year_pillar,
                month_pillar=month_pillar,
                day_pillar=day_pillar,
                hour_pillar=hour_pillar,
                da_yun=da_yun_result,
                calculation_method=method,
            )
        except Exception as exc:
            raise BaziAdapterError("lunar_python 排盘或字段映射失败。") from exc
