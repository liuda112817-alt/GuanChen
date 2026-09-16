from unittest.mock import patch

import pytest
from pydantic import ValidationError

from guanchen_v2.liuyao.casting import (
    HexagramCastingService,
    ManualCastingInput,
)
from guanchen_v2.liuyao.exceptions import HexagramCalculationError
from guanchen_v2.liuyao.iching_adapter import (
    IChingPyAdapter,
    VendorLineFacts,
)
from guanchen_v2.models.liuyao import (
    CastingMethod,
    CoinFace,
    HexagramIdentity,
    LineValue,
    YinYang,
)


class FakeCoinSource:
    def __init__(self, seq: list[CoinFace]):
        self._seq = seq
        self._idx = 0

    def toss(self) -> CoinFace:
        face = self._seq[self._idx]
        self._idx += 1
        return face


@pytest.fixture
def adapter():
    return IChingPyAdapter()


def make_vendor_line_facts() -> tuple[VendorLineFacts, ...]:
    """
    给不关心真实装卦内容的纯逻辑测试提供合法 vendor facts。
    """
    return tuple(
        VendorLineFacts(
            heavenly_stem="甲",
            earthly_branch="子",
            element="水",
            six_relative="兄弟",
        )
        for _ in range(6)
    )


# -------------------------------------------------------------------------
# 1. 验证手工输入边界
# -------------------------------------------------------------------------
def test_manual_input_validation():
    with pytest.raises(ValidationError):
        ManualCastingInput(lines=(LineValue.OLD_YIN, LineValue.OLD_YANG))

    with pytest.raises(ValidationError):
        ManualCastingInput(lines=(7, 7, 7, 7, 7, 5))

    valid = ManualCastingInput(lines=(6, 7, 8, 9, 6, 7))
    assert len(valid.lines) == 6


# -------------------------------------------------------------------------
# 2. 验证 6/7/8/9 到 阴阳与动静 的语义映射
# -------------------------------------------------------------------------
def test_line_semantics(adapter):
    service = HexagramCastingService(
        adapter,
        FakeCoinSource([]),
    )

    mock_identity = HexagramIdentity(
        name="Mock",
        upper_trigram="U",
        lower_trigram="L",
    )

    with patch.object(
        adapter,
        "_resolve_vendor_hexagram",
        return_value=(
            mock_identity,
            make_vendor_line_facts(),
        ),
    ):
        result = service.cast_manual(
            ManualCastingInput(
                lines=(6, 7, 8, 9, 8, 7),
            )
        )

        l6, l7, l8, l9, _, _ = result.lines

        assert l6.polarity == YinYang.YIN
        assert l6.moving is True

        assert l7.polarity == YinYang.YANG
        assert l7.moving is False

        assert l8.polarity == YinYang.YIN
        assert l8.moving is False

        assert l9.polarity == YinYang.YANG
        assert l9.moving is True


# -------------------------------------------------------------------------
# 3. 验证第三方异常被安全拦截并保留根因
# -------------------------------------------------------------------------
def test_adapter_exception_boundary():
    real_adapter = IChingPyAdapter()
    service = HexagramCastingService(real_adapter, FakeCoinSource([]))

    with patch.object(real_adapter, "_resolve_vendor_hexagram", side_effect=Exception("ichingpy 内部越界")):
        # 修正正则匹配字符串，与 adapter 中抛出的一致
        with pytest.raises(HexagramCalculationError, match="六爻卦象构造与装卦推演失败") as exc_info:
            service.cast_manual(ManualCastingInput(lines=(7, 7, 7, 7, 7, 7)))

    assert str(exc_info.value.__cause__) == "ichingpy 内部越界"


# -------------------------------------------------------------------------
# 4. 验证 CoinTrace 数学溯源的一致性防篡改
# -------------------------------------------------------------------------
def test_deterministic_fake_coin_sequence(adapter):
    seq = [
        CoinFace.HEAD,
        CoinFace.TAIL,
        CoinFace.TAIL,
    ] * 6

    mock_primary = HexagramIdentity(
        name="Mock",
        upper_trigram="U",
        lower_trigram="L",
    )

    with patch.object(
        adapter,
        "_resolve_vendor_hexagram",
        return_value=(
            mock_primary,
            make_vendor_line_facts(),
        ),
    ):
        service = HexagramCastingService(
            adapter,
            FakeCoinSource(seq),
        )

        result = service.cast_random()

        assert result.casting_method == CastingMethod.SYSTEM_THREE_COIN
        assert len(result.coin_tosses) == 6

        assert result.coin_tosses[0].position == 1
        assert result.coin_tosses[0].line_value == LineValue.YOUNG_YANG
        assert result.lines[0].value == LineValue.YOUNG_YANG

        assert result.moving_line_positions == []


# =========================================================================
# 真实 Fixtures 验证：不再瞎猜，打印后人工核查并填入硬编码断言！
# =========================================================================


def test_fixed_real_ichingpy_fixture_no_moving_lines(adapter):
    """
    固定六爻输入 -> 真实 ichingpy -> 稳定乾卦装卦事实。
    """
    service = HexagramCastingService(
        adapter,
        FakeCoinSource([]),
    )

    result = service.cast_manual(
        ManualCastingInput(
            lines=(7, 7, 7, 7, 7, 7),
        )
    )

    assert result.casting_method == CastingMethod.MANUAL_SIX_LINES
    assert result.moving_line_positions == []
    assert result.changed_hexagram is None

    # SixLinesDivinationEngine 没有提供稳定完整六十四卦名，
    # 不自行制造 name。
    assert result.primary_hexagram.name is None
    assert result.primary_hexagram.upper_trigram == "乾"
    assert result.primary_hexagram.lower_trigram == "乾"

    # ---------------------------------------------------------
    # 真实纳甲 / 五行 / 六亲
    # bottom -> top
    # ---------------------------------------------------------
    expected = [
        ("甲", "子", "水", "子孙"),
        ("甲", "寅", "木", "妻财"),
        ("甲", "辰", "土", "父母"),
        ("壬", "午", "火", "官鬼"),
        ("壬", "申", "金", "兄弟"),
        ("壬", "戌", "土", "父母"),
    ]

    for line, (
        expected_stem,
        expected_branch,
        expected_element,
        expected_relative,
    ) in zip(result.lines, expected, strict=True):
        assert line.heavenly_stem == expected_stem
        assert line.earthly_branch == expected_branch
        assert line.element == expected_element
        assert line.six_relative == expected_relative

        # ichingpy 0.1.10 当前没有六神
        assert line.six_spirit is None

    # 乾为八纯卦：
    # 上爻为世，三爻为应。
    assert result.lines[5].is_shi is True
    assert result.lines[2].is_ying is True

    assert sum(line.is_shi for line in result.lines) == 1
    assert sum(line.is_ying for line in result.lines) == 1


def test_fixed_real_ichingpy_fixture_with_moving_lines(adapter):
    """
    固定动爻：
    (6, 7, 7, 9, 7, 7)

    初爻老阴、四爻老阳。
    """
    service = HexagramCastingService(
        adapter,
        FakeCoinSource([]),
    )

    result = service.cast_manual(
        ManualCastingInput(
            lines=(6, 7, 7, 9, 7, 7),
        )
    )

    assert result.moving_line_positions == [1, 4]

    # 本卦：上乾，下巽
    assert result.primary_hexagram.name is None
    assert result.primary_hexagram.upper_trigram == "乾"
    assert result.primary_hexagram.lower_trigram == "巽"

    # 变卦必须真实存在
    assert result.changed_hexagram is not None

    # 6 -> 7
    # 9 -> 8
    #
    # 变后：
    # 下乾，上巽
    assert result.changed_hexagram.name is None
    assert result.changed_hexagram.upper_trigram == "巽"
    assert result.changed_hexagram.lower_trigram == "乾"
