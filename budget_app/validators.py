from datetime import datetime
from typing import Iterable


# 거래에서 사용할 수 있는 타입을 정의한다.
VALID_TYPES = {"income", "expense"}


# 입력받은 날짜가 YYYY-MM-DD 형식인지 확인한다.
def validate_date(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise ValueError(
            "날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식으로 입력하세요."
        )

    return value


# 입력받은 월이 YYYY-MM 형식인지 확인한다.
def validate_month(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m")
    except ValueError:
        raise ValueError(
            "월 형식이 올바르지 않습니다. YYYY-MM 형식으로 입력하세요."
        )

    return value


# 입력받은 금액이 0보다 큰 정수인지 확인한다.
def validate_amount(value: str) -> int:
    try:
        amount = int(value)
    except ValueError:
        raise ValueError("금액은 정수로 입력하세요.")

    if amount <= 0:
        raise ValueError("금액은 0보다 커야 합니다.")

    return amount


# 거래 타입이 income 또는 expense인지 확인한다.
def validate_type(value: str) -> str:
    value = value.lower()

    if value not in VALID_TYPES:
        raise ValueError(
            "거래 타입은 income 또는 expense 중 하나로 입력하세요."
        )

    return value


# 입력받은 카테고리가 현재 등록된 카테고리인지 확인한다.
def validate_category(
    value: str,
    categories: Iterable[str],
) -> str:
    value = value.strip()

    if not value:
        raise ValueError("카테고리를 입력하세요.")

    if value not in categories:
        raise ValueError(
            f"등록되지 않은 카테고리입니다: {value}"
        )

    return value


# 새로 등록할 카테고리 이름이 비어 있지 않은지 확인한다.
def validate_category_name(value: str) -> str:
    value = value.strip()

    if not value:
        raise ValueError("카테고리 이름을 입력하세요.")

    return value


# 목록 조회에 사용할 limit 값이 양의 정수인지 확인한다.
def validate_limit(value: str) -> int:
    try:
        limit = int(value)
    except ValueError:
        raise ValueError("limit은 정수로 입력하세요.")

    if limit <= 0:
        raise ValueError("limit은 0보다 커야 합니다.")

    return limit


# 요약에서 사용할 TOP N 값이 양의 정수인지 확인한다.
def validate_top(value: str) -> int:
    try:
        top = int(value)
    except ValueError:
        raise ValueError("top은 정수로 입력하세요.")

    if top <= 0:
        raise ValueError("top은 0보다 커야 합니다.")

    return top


# 쉼표로 입력된 태그 문자열을 태그 목록으로 변환한다.
def validate_tags(value: str) -> list[str]:
    if not value.strip():
        return []

    return [
        tag.strip()
        for tag in value.split(",")
        if tag.strip()
    ]