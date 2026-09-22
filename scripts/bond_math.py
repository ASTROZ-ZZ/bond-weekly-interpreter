#!/usr/bin/env python3
"""计算普通固定息到期一次还本债券的价格及中心差分 DV01。"""

from __future__ import annotations

import argparse
import csv
import json
from io import StringIO
from pathlib import Path


def bond_price(face: float, coupon_rate: float, yield_rate: float, years: float, frequency: int) -> float:
    periods_float = years * frequency
    periods = round(periods_float)
    if abs(periods_float - periods) > 1e-9:
        raise ValueError("剩余年限乘以每年付息次数必须为整数期数")
    if face <= 0 or years <= 0 or frequency <= 0:
        raise ValueError("面值、剩余年限和每年付息次数必须为正数")
    if 1 + yield_rate / frequency <= 0:
        raise ValueError("该收益率会导致折现基数小于或等于零")

    coupon = face * coupon_rate / frequency
    discount_base = 1 + yield_rate / frequency
    return sum(coupon / discount_base**period for period in range(1, periods + 1)) + face / discount_base**periods


def calculate(face: float, coupon_rate_decimal: float, yield_rate_decimal: float, years: float, frequency: int, position_face: float) -> dict[str, float]:
    bump = 0.0001
    price = bond_price(face, coupon_rate_decimal, yield_rate_decimal, years, frequency)
    price_minus_1bp = bond_price(face, coupon_rate_decimal, yield_rate_decimal - bump, years, frequency)
    price_plus_1bp = bond_price(face, coupon_rate_decimal, yield_rate_decimal + bump, years, frequency)
    dv01_per_face = (price_minus_1bp - price_plus_1bp) / 2
    scale = position_face / face
    return {
        "price_per_input_face": price,
        "price_yield_minus_1bp": price_minus_1bp,
        "price_yield_plus_1bp": price_plus_1bp,
        "dv01_per_input_face": dv01_per_face,
        "position_market_value": price * scale,
        "position_dv01": dv01_per_face * scale,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--face", type=float, default=100.0, help="报价面值，默认 100")
    parser.add_argument("--coupon", type=float, required=True, help="年票面利率，单位为百分比")
    parser.add_argument("--yield-rate", type=float, required=True, help="年化到期收益率，单位为百分比")
    parser.add_argument("--years", type=float, required=True, help="剩余期限，单位为年")
    parser.add_argument("--frequency", type=int, default=2, help="每年付息次数，默认 2")
    parser.add_argument("--position-face", type=float, help="头寸面值；默认等于 --face")
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    parser.add_argument("--output", type=Path, help="可选输出文件；省略时输出到终端")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    position_face = args.position_face if args.position_face is not None else args.face
    inputs = {
        "face": args.face,
        "coupon_rate_decimal": args.coupon / 100,
        "yield_rate_decimal": args.yield_rate / 100,
        "years": args.years,
        "frequency": args.frequency,
        "position_face": position_face,
    }
    results = calculate(**inputs)
    payload = {
        "inputs": inputs,
        "results": results,
        "notes": [
            "普通固定息到期一次还本债券；估值日与付息日对齐。",
            "名义年收益率按付息频率复利。",
            "DV01 使用收益率上下各 1 个基点的对称重估，并以正数表示局部价格敏感度。",
            "未计入应计利息、税收、期权、违约、流动性和交易成本。",
        ],
    }

    if args.format == "json":
        rendered = json.dumps(payload, indent=2)
    else:
        rows = [("input", key, value) for key, value in inputs.items()]
        rows += [("result", key, value) for key, value in results.items()]
        rows += [("note", f"note_{index}", value) for index, value in enumerate(payload["notes"], 1)]
        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(("类别", "字段", "数值"))
        writer.writerows(rows)
        rendered = buffer.getvalue()

    if args.output:
        args.output.write_text(rendered + ("" if rendered.endswith("\n") else "\n"), encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
