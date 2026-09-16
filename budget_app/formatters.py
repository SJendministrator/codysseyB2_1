from .models import Category, Transaction


# 거래 한 건을 터미널에서 읽기 쉬운 문자열로 변환한다.
def format_transaction(transaction: Transaction) -> str:
    transaction_type = (
        "수입"
        if transaction.type == "income"
        else "지출"
    )

    tags = ", ".join(transaction.tags) if transaction.tags else "-"

    return (
        f"[{transaction.id}] "
        f"{transaction.date} | "
        f"{transaction_type} | "
        f"{transaction.category} | "
        f"{transaction.amount:,}원 | "
        f"{transaction.memo or '-'} | "
        f"태그: {tags}"
    )


# 카테고리 한 건을 터미널 출력용 문자열로 변환한다.
def format_category(category: Category) -> str:
    return f"- {category.name}"


# 월별 요약 결과를 터미널에서 읽기 쉬운 문자열로 변환한다.
def format_summary(summary: dict) -> str:
    lines = [
        f"===== {summary['month']} 월별 요약 =====",
        f"수입: {summary['income_total']:,}원",
        f"지출: {summary['expense_total']:,}원",
        f"잔액: {summary['balance']:,}원",
    ]

    budget = summary["budget"]

    if budget is not None:
        usage_percent = summary["usage_percent"]

        lines.append(
            f"예산: {budget.amount:,}원"
        )
        lines.append(
            f"예산 사용률: {usage_percent:.1f}%"
        )

        if summary["budget_exceeded"]:
            lines.append(
                "경고: 설정한 예산을 초과했습니다."
            )

    lines.append("")
    lines.append("지출 상위 카테고리:")

    top_categories = summary["top_categories"]

    if not top_categories:
        lines.append("- 데이터 없음")
    else:
        for rank, (category, amount) in enumerate(
            top_categories,
            start=1,
        ):
            lines.append(
                f"{rank}. {category}: {amount:,}원"
            )

    return "\n".join(lines)