import secrets
from typing import Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict

from guanchen_v2.liuyao.iching_adapter import IChingPyAdapter
from guanchen_v2.models.liuyao import (
    CastingMethod,
    CoinFace,
    CoinToss,
    HexagramResult,
    LineValue,
)
from guanchen_v2.observability.decorators import trace

SixLineValues = tuple[LineValue, LineValue, LineValue, LineValue, LineValue, LineValue]


class ManualCastingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal[CastingMethod.MANUAL_SIX_LINES] = CastingMethod.MANUAL_SIX_LINES
    lines: SixLineValues


class CoinRandomSource(Protocol):
    def toss(self) -> CoinFace: ...


class SystemRandomCoinSource:
    def __init__(self) -> None:
        self._rng = secrets.SystemRandom()

    def toss(self) -> CoinFace:
        return CoinFace.HEAD if self._rng.choice([True, False]) else CoinFace.TAIL


class HexagramCastingService:
    def __init__(self, adapter: IChingPyAdapter, random_source: CoinRandomSource) -> None:
        self._adapter = adapter
        self._random = random_source

    @trace("cast_hexagram", "TOOL")
    def cast_manual(self, input_data: ManualCastingInput) -> HexagramResult:
        facts = self._adapter.resolve_facts(input_data.lines)
        return HexagramResult(
            casting_method=CastingMethod.MANUAL_SIX_LINES,
            lines=facts.lines,
            primary_hexagram=facts.primary_hexagram,
            changed_hexagram=facts.changed_hexagram,
            moving_line_positions=facts.moving_line_positions,
            coin_tosses=[],
        )

    @trace("cast_hexagram", "TOOL")
    def cast_random(self) -> HexagramResult:
        tosses = []
        line_values = []

        for pos in range(1, 7):
            coins = (self._random.toss(), self._random.toss(), self._random.toss())
            val_int = sum(3 if c == CoinFace.HEAD else 2 for c in coins)
            lv = LineValue(val_int)

            tosses.append(CoinToss(position=pos, coins=coins, line_value=lv))
            line_values.append(lv)

        canonical_lines = cast(SixLineValues, tuple(line_values))
        facts = self._adapter.resolve_facts(canonical_lines)

        return HexagramResult(
            casting_method=CastingMethod.SYSTEM_THREE_COIN,
            lines=facts.lines,
            primary_hexagram=facts.primary_hexagram,
            changed_hexagram=facts.changed_hexagram,
            moving_line_positions=facts.moving_line_positions,
            coin_tosses=tosses,
        )
