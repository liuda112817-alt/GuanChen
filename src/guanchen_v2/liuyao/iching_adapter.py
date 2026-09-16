from pydantic import BaseModel, ConfigDict

from guanchen_v2.liuyao.exceptions import HexagramCalculationError
from guanchen_v2.models.liuyao import (
    HexagramIdentity,
    HexagramLine,
    LineValue,
    YinYang,
)


class VendorLineFacts(BaseModel):
    """
    从 ichingpy SixLinesDivinationEngine 标准化出的单爻事实。

    six_spirit 当前 ichingpy 0.1.10 未提供，因此保持 None。
    """

    model_config = ConfigDict(extra="forbid")

    heavenly_stem: str
    earthly_branch: str
    element: str
    six_relative: str

    six_spirit: str | None = None

    is_shi: bool = False
    is_ying: bool = False


class HexagramFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lines: tuple[HexagramLine, ...]
    primary_hexagram: HexagramIdentity
    changed_hexagram: HexagramIdentity | None
    moving_line_positions: list[int]


class IChingPyAdapter:
    """
    GuanChen 与 ichingpy 之间的唯一适配边界。

    项目内部只使用：
        LineValue(6/7/8/9)
        HexagramResult / HexagramLine

    ichingpy 的对象结构不会泄漏到业务层。
    """

    def _resolve_vendor_hexagram(
        self,
        line_values: tuple[LineValue, ...],
    ) -> tuple[HexagramIdentity, tuple[VendorLineFacts, ...]]:
        """
        唯一正式 vendor path：

        LineValue
        -> ichingpy.LineStatus
        -> Line / Trigram / Hexagram
        -> SixLinesDivinationEngine.execute()
        -> hexagram.interpretation.lines
        -> GuanChen normalized facts
        """
        import ichingpy
        from ichingpy.enum.role import HexagramRole

        if len(line_values) != 6:
            raise HexagramCalculationError("ichingpy 六爻构造输入必须正好包含 6 爻")

        status_map = {
            LineValue.OLD_YIN: ichingpy.LineStatus.CHANGING_YIN,
            LineValue.YOUNG_YANG: ichingpy.LineStatus.STATIC_YANG,
            LineValue.YOUNG_YIN: ichingpy.LineStatus.STATIC_YIN,
            LineValue.OLD_YANG: ichingpy.LineStatus.CHANGING_YANG,
        }

        # -----------------------------------------------------
        # 1. 构造真实 ichingpy Hexagram
        # 顺序保持 bottom -> top：
        # lines[:3] = 初、二、三爻（内卦）
        # lines[3:] = 四、五、上爻（外卦）
        # -----------------------------------------------------
        vendor_lines = [ichingpy.Line(status=status_map[value]) for value in line_values]

        hexagram = ichingpy.Hexagram(
            inner=ichingpy.Trigram(lines=vendor_lines[:3]),
            outer=ichingpy.Trigram(lines=vendor_lines[3:]),
        )

        # -----------------------------------------------------
        # 2. 六爻装卦 / 纳甲 / 六亲 / 世应
        # -----------------------------------------------------
        engine = ichingpy.SixLinesDivinationEngine()
        engine.execute(hexagram)

        interpretation = hexagram.interpretation
        if interpretation is None:
            raise HexagramCalculationError("ichingpy 未生成六爻装卦结果")

        interpreted_lines = list(interpretation.lines)

        if len(interpreted_lines) != 6:
            raise HexagramCalculationError(f"ichingpy 装卦结果异常：预期 6 爻，实际返回 {len(interpreted_lines)} 爻")

        # -----------------------------------------------------
        # 3. 卦象 Identity
        #
        # ichingpy Trigram 有正式 name，例如：
        # 乾 / 兑 / 离 / 震 / 巽 / 坎 / 艮 / 坤
        #
        # SixLinesDivinationEngine 本身不提供稳定的完整六十四卦名，
        # 所以 name 保持 None，不制造伪卦名。
        # -----------------------------------------------------
        identity = HexagramIdentity(
            name=None,
            upper_trigram=hexagram.outer.name,
            lower_trigram=hexagram.inner.name,
        )

        # -----------------------------------------------------
        # 4. 从 SixLineLineInterp 提取真实装卦字段
        #
        # 注意：
        # 数据在 hexagram.interpretation.lines，
        # 不在原始 hexagram.inner.lines / outer.lines 上。
        # -----------------------------------------------------
        normalized_lines: list[VendorLineFacts] = []

        for line_interp in interpreted_lines:
            stem = line_interp.stem
            branch = line_interp.branch
            relative = line_interp.relative
            role = line_interp.role

            normalized_lines.append(
                VendorLineFacts(
                    heavenly_stem=stem.label,
                    earthly_branch=branch.label,
                    element=branch.phase.label,
                    six_relative=relative.label,
                    # ichingpy 0.1.10 当前没有六神数据
                    six_spirit=None,
                    is_shi=role == HexagramRole.SUBJECT,
                    is_ying=role == HexagramRole.OBJECT,
                )
            )

        return identity, tuple(normalized_lines)

    @staticmethod
    def _to_changed_line_value(value: LineValue) -> LineValue:
        """
        动爻变换的 canonical 规则。

        老阴 6 -> 少阳 7
        老阳 9 -> 少阴 8
        静爻保持不变
        """
        if value == LineValue.OLD_YIN:
            return LineValue.YOUNG_YANG

        if value == LineValue.OLD_YANG:
            return LineValue.YOUNG_YIN

        return value

    def resolve_facts(
        self,
        line_values: tuple[LineValue, ...],
    ) -> HexagramFacts:
        try:
            if len(line_values) != 6:
                raise HexagramCalculationError("六爻输入必须正好包含 6 爻")

            # -------------------------------------------------
            # 1. 本卦 + 装卦事实
            # -------------------------------------------------
            primary_identity, primary_line_facts = self._resolve_vendor_hexagram(line_values)

            hexagram_lines: list[HexagramLine] = []
            moving_positions: list[int] = []

            for position, (value, vendor_fact) in enumerate(
                zip(
                    line_values,
                    primary_line_facts,
                    strict=True,
                ),
                start=1,
            ):
                moving = value in {
                    LineValue.OLD_YIN,
                    LineValue.OLD_YANG,
                }

                polarity = (
                    YinYang.YIN
                    if value
                    in {
                        LineValue.OLD_YIN,
                        LineValue.YOUNG_YIN,
                    }
                    else YinYang.YANG
                )

                if moving:
                    moving_positions.append(position)

                hexagram_lines.append(
                    HexagramLine(
                        position=position,
                        value=value,
                        polarity=polarity,
                        moving=moving,
                        heavenly_stem=vendor_fact.heavenly_stem,
                        earthly_branch=vendor_fact.earthly_branch,
                        element=vendor_fact.element,
                        six_relative=vendor_fact.six_relative,
                        six_spirit=vendor_fact.six_spirit,
                        is_shi=vendor_fact.is_shi,
                        is_ying=vendor_fact.is_ying,
                    )
                )

            # -------------------------------------------------
            # 2. 变卦
            #
            # 仅执行最小 canonical line transformation，
            # 然后重新交给同一个 ichingpy path 构造卦象。
            # 不维护任何六十四卦映射表。
            # -------------------------------------------------
            changed_identity: HexagramIdentity | None = None

            if moving_positions:
                changed_line_values = tuple(self._to_changed_line_value(value) for value in line_values)

                changed_identity, _ = self._resolve_vendor_hexagram(changed_line_values)

            return HexagramFacts(
                lines=tuple(hexagram_lines),
                primary_hexagram=primary_identity,
                changed_hexagram=changed_identity,
                moving_line_positions=moving_positions,
            )

        except HexagramCalculationError:
            raise

        except Exception as exc:
            raise HexagramCalculationError("六爻卦象构造与装卦推演失败") from exc
