import csv
import uuid
from collections import deque
from pathlib import Path
from typing import Iterator

from .decorators import log_execution, measure_time
from .models import Budget, Category, Transaction
from .repository import FileRepository
from .validators import (
    validate_amount,
    validate_category,
    validate_category_name,
    validate_date,
    validate_limit,
    validate_month,
    validate_tags,
    validate_top,
    validate_type,
)


# 거래와 카테고리, 예산의 실제 업무 처리를 담당하는 서비스 클래스이다.
class BudgetService:
    # 저장소를 받아 서비스에서 사용할 기본 설정을 초기화한다.
    def __init__(self, repository: FileRepository):
        self.repository = repository
        self._ensure_default_categories()

    # 카테고리 파일이 비어 있으면 기본 카테고리를 자동으로 등록한다.
    def _ensure_default_categories(self) -> None:
        if any(self.repository.stream_categories()):
            return

        default_categories = [
            "식비",
            "교통",
            "주거",
            "쇼핑",
            "의료",
            "문화",
            "급여",
            "기타",
        ]

        for name in default_categories:
            self.repository.add_category(Category(name=name))

    # 현재 등록된 카테고리 이름들을 집합으로 반환한다.
    def _get_category_names(self) -> set[str]:
        return {
            category.name
            for category in self.repository.stream_categories()
        }

    # 거래 ID를 중복되지 않는 새로운 값으로 생성한다.
    def _generate_transaction_id(self) -> str:
        existing_ids = {
            transaction.id
            for transaction in self.repository.stream_transactions()
        }

        while True:
            transaction_id = uuid.uuid4().hex[:12]
            if transaction_id not in existing_ids:
                return transaction_id

    # 새로운 거래를 검증하고 저장한 뒤 생성된 거래를 반환한다.
    @log_execution
    @measure_time
    def add_transaction(
        self,
        date: str,
        transaction_type: str,
        category: str,
        amount: str,
        memo: str = "",
        tags: str = "",
    ) -> Transaction:
        date = validate_date(date)
        transaction_type = validate_type(transaction_type)
        amount_value = validate_amount(amount)

        category_names = self._get_category_names()
        category = validate_category(category, category_names)

        tag_list = validate_tags(tags)

        transaction = Transaction(
            id=self._generate_transaction_id(),
            type=transaction_type,
            date=date,
            amount=amount_value,
            category=category,
            memo=memo.strip(),
            tags=tag_list,
        )

        self.repository.add_transaction(transaction)

        return transaction

    # 거래를 최신순으로 제한된 개수만 스트리밍해서 반환한다.
    def stream_latest_transactions(
        self,
        limit: int = 20,
    ) -> Iterator[Transaction]:
        limit = validate_limit(str(limit))

        buffer: deque[Transaction] = deque(maxlen=limit)

        for transaction in self.repository.stream_transactions():
            buffer.append(transaction)

        for transaction in reversed(buffer):
            yield transaction

    # 조건에 맞는 거래를 최신순으로 스트리밍해서 반환한다.
    def search_transactions(
        self,
        from_date: str | None = None,
        to_date: str | None = None,
        category: str | None = None,
        transaction_type: str | None = None,
        query: str | None = None,
        tag: str | None = None,
    ) -> Iterator[Transaction]:
        if from_date:
            from_date = validate_date(from_date)

        if to_date:
            to_date = validate_date(to_date)

        if from_date and to_date and from_date > to_date:
            raise ValueError(
                "검색 시작일이 종료일보다 늦습니다. 날짜 범위를 확인하세요."
            )

        if transaction_type:
            transaction_type = validate_type(transaction_type)

        if category:
            category_names = self._get_category_names()
            category = validate_category(category, category_names)

        buffer: list[Transaction] = []

        for transaction in self.repository.stream_transactions():
            if from_date and transaction.date < from_date:
                continue

            if to_date and transaction.date > to_date:
                continue

            if category and transaction.category != category:
                continue

            if (
                transaction_type
                and transaction.type != transaction_type
            ):
                continue

            if query:
                if query.lower() not in transaction.memo.lower():
                    continue

            if tag and tag not in transaction.tags:
                continue

            buffer.append(transaction)

        for transaction in reversed(buffer):
            yield transaction

    # 거래 ID로 거래 하나를 찾아 반환한다.
    def get_transaction(
        self,
        transaction_id: str,
    ) -> Transaction | None:
        for transaction in self.repository.stream_transactions():
            if transaction.id == transaction_id:
                return transaction

        return None

    # 기존 거래를 수정할 수 있는 값만 변경해서 저장한다.
    @log_execution
    @measure_time
    def update_transaction(
        self,
        transaction_id: str,
        date: str | None = None,
        transaction_type: str | None = None,
        category: str | None = None,
        amount: str | None = None,
        memo: str | None = None,
        tags: str | None = None,
    ) -> Transaction:
        transactions = []
        target = None

        category_names = self._get_category_names()

        for transaction in self.repository.stream_transactions():
            if transaction.id != transaction_id:
                transactions.append(transaction)
                continue

            target = transaction

            if date is not None:
                date = validate_date(date)
                target.date = date

            if transaction_type is not None:
                target.type = validate_type(transaction_type)

            if category is not None:
                target.category = validate_category(
                    category,
                    category_names,
                )

            if amount is not None:
                target.amount = validate_amount(amount)

            if memo is not None:
                target.memo = memo.strip()

            if tags is not None:
                target.tags = validate_tags(tags)

            transactions.append(target)

        if target is None:
            raise ValueError(
                f"거래 ID를 찾을 수 없습니다: {transaction_id}"
            )

        self.repository.rewrite_transactions(iter(transactions))

        return target

    # 거래 ID에 해당하는 거래를 삭제한다.
    @log_execution
    def delete_transaction(self, transaction_id: str) -> None:
        transactions = []
        deleted = False

        for transaction in self.repository.stream_transactions():
            if transaction.id == transaction_id:
                deleted = True
                continue

            transactions.append(transaction)

        if not deleted:
            raise ValueError(
                f"거래 ID를 찾을 수 없습니다: {transaction_id}"
            )

        self.repository.rewrite_transactions(iter(transactions))

    # 월별 수입과 지출을 계산하고 예산 사용 현황을 반환한다.
    @log_execution
    @measure_time
    def get_summary(
        self,
        month: str,
        top: int = 5,
    ) -> dict:
        month = validate_month(month)
        top = validate_top(str(top))

        income_total = 0
        expense_total = 0
        expense_by_category: dict[str, int] = {}
        transaction_count = 0

        for transaction in self.repository.stream_transactions():
            if not transaction.date.startswith(month):
                continue

            transaction_count += 1

            if transaction.type == "income":
                income_total += transaction.amount
            else:
                expense_total += transaction.amount
                expense_by_category[transaction.category] = (
                    expense_by_category.get(transaction.category, 0)
                    + transaction.amount
                )

        budget = self.get_budget(month)

        balance = income_total - expense_total

        top_categories = sorted(
            expense_by_category.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:top]

        usage_percent = None
        budget_exceeded = False

        if budget is not None:
            usage_percent = (
                expense_total / budget.amount
            ) * 100

            budget_exceeded = expense_total > budget.amount

        return {
            "month": month,
            "transaction_count": transaction_count,
            "income_total": income_total,
            "expense_total": expense_total,
            "balance": balance,
            "top_categories": top_categories,
            "budget": budget,
            "usage_percent": usage_percent,
            "budget_exceeded": budget_exceeded,
        }

    # 특정 월의 예산을 등록하거나 기존 예산을 수정한다.
    @log_execution
    def set_budget(
        self,
        month: str,
        amount: str,
    ) -> Budget:
        month = validate_month(month)
        amount_value = validate_amount(amount)

        budgets = []
        target = Budget(
            month=month,
            amount=amount_value,
        )
        replaced = False

        for budget in self.repository.stream_budgets():
            if budget.month == month:
                budgets.append(target)
                replaced = True
            else:
                budgets.append(budget)

        if not replaced:
            budgets.append(target)

        self.repository.rewrite_budgets(iter(budgets))

        return target

    # 특정 월에 등록된 예산을 찾아 반환한다.
    def get_budget(self, month: str) -> Budget | None:
        month = validate_month(month)

        for budget in self.repository.stream_budgets():
            if budget.month == month:
                return budget

        return None

    # 새로운 카테고리를 등록하고 등록된 카테고리를 반환한다.
    @log_execution
    def add_category(self, name: str) -> Category:
        name = validate_category_name(name)

        category_names = self._get_category_names()

        if name in category_names:
            raise ValueError(
                f"이미 등록된 카테고리입니다: {name}"
            )

        category = Category(name=name)
        self.repository.add_category(category)

        return category

    # 현재 등록된 모든 카테고리를 이름순으로 반환한다.
    def list_categories(self) -> list[Category]:
        categories = list(self.repository.stream_categories())
        categories.sort(key=lambda category: category.name)
        return categories

    # 사용 중이지 않은 카테고리만 삭제한다.
    @log_execution
    def remove_category(self, name: str) -> None:
        name = validate_category_name(name)

        category_names = self._get_category_names()

        if name not in category_names:
            raise ValueError(
                f"등록된 카테고리가 아닙니다: {name}"
            )

        for transaction in self.repository.stream_transactions():
            if transaction.category == name:
                raise ValueError(
                    f"사용 중인 카테고리는 삭제할 수 없습니다: {name}"
                )

        categories = [
            category
            for category in self.repository.stream_categories()
            if category.name != name
        ]

        self.repository.rewrite_categories(iter(categories))

    # CSV 파일의 거래 데이터를 검증한 뒤 한꺼번에 저장한다.
    @log_execution
    @measure_time
    def import_csv(self, csv_path: str | Path) -> int:
        csv_path = Path(csv_path)

        if not csv_path.exists():
            raise ValueError(
                f"CSV 파일을 찾을 수 없습니다: {csv_path}"
            )

        category_names = self._get_category_names()
        imported_transactions: list[Transaction] = []

        required_columns = {
            "date",
            "type",
            "category",
            "amount",
            "memo",
            "tags",
        }

        with csv_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:
            reader = csv.DictReader(file)

            if reader.fieldnames is None:
                raise ValueError(
                    "CSV 헤더가 없습니다. 지정된 CSV 형식을 확인하세요."
                )

            missing_columns = required_columns - set(reader.fieldnames)

            if missing_columns:
                raise ValueError(
                    "CSV 필수 컬럼이 없습니다: "
                    + ", ".join(sorted(missing_columns))
                )

            for row_number, row in enumerate(reader, start=2):
                try:
                    date = validate_date(row["date"])
                    transaction_type = validate_type(row["type"])
                    amount = validate_amount(row["amount"])
                    category = validate_category(
                        row["category"],
                        category_names,
                    )

                    tags = validate_tags(row.get("tags", ""))

                    imported_transactions.append(
                        Transaction(
                            id=self._generate_transaction_id(),
                            type=transaction_type,
                            date=date,
                            amount=amount,
                            category=category,
                            memo=row.get("memo", "").strip(),
                            tags=tags,
                        )
                    )

                except ValueError as error:
                    raise ValueError(
                        f"CSV {row_number}번째 행이 잘못되었습니다: {error}"
                    ) from error

        for transaction in imported_transactions:
            self.repository.add_transaction(transaction)

        return len(imported_transactions)

    # 지정한 조건에 맞는 거래를 CSV 파일로 저장하고 건수를 반환한다.
    @log_execution
    @measure_time
    def export_csv(
        self,
        csv_path: str | Path,
        month: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> int:
        if not month and not (from_date or to_date):
            raise ValueError(
                "CSV 내보내기에는 --month 또는 --from/--to 조건이 필요합니다."
            )

        if month:
            month = validate_month(month)

        if from_date:
            from_date = validate_date(from_date)

        if to_date:
            to_date = validate_date(to_date)

        if from_date and to_date and from_date > to_date:
            raise ValueError(
                "검색 시작일이 종료일보다 늦습니다. 날짜 범위를 확인하세요."
            )

        csv_path = Path(csv_path)

        count = 0

        with csv_path.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "date",
                    "type",
                    "category",
                    "amount",
                    "memo",
                    "tags",
                ],
            )

            writer.writeheader()

            for transaction in self.repository.stream_transactions():
                if month and not transaction.date.startswith(month):
                    continue

                if from_date and transaction.date < from_date:
                    continue

                if to_date and transaction.date > to_date:
                    continue

                writer.writerow(
                    {
                        "date": transaction.date,
                        "type": transaction.type,
                        "category": transaction.category,
                        "amount": transaction.amount,
                        "memo": transaction.memo,
                        "tags": ",".join(transaction.tags),
                    }
                )

                count += 1

        return count