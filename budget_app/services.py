# [역할] CSV 파일 읽기/쓰기를 위한 표준 모듈을 임포트합니다.
import csv
# [역할] 전체를 메모리에 올리지 않고 상위 N개만 유지하며 고르기 위해 heapq를 임포트합니다.
import heapq
# [역할] 중복 없는 고유 거래 ID(hex)를 생성하기 위해 uuid 모듈을 임포트합니다.
import uuid
# [역할] 파일 시스템 경로를 객체 지향적으로 다루기 위해 Path를 임포트합니다.
from pathlib import Path
# [역할] 제너레이터 함수 반환 타입을 명시하기 위해 Iterator를 임포트합니다.
from typing import Iterator

# [역할] 메서드 실행 로그 및 실행 시간 측정을 위한 데코레이터를 임포트합니다.
from .decorators import log_execution, measure_time
# [역할] 데이터 모델(예산, 카테고리, 거래 내역) 클래스들을 임포트합니다.
from .models import Budget, Category, Transaction
# [역할] 파일 입출력을 전담하는 저장소 계층 클래스를 임포트합니다.
from .repository import FileRepository
# [역할] 각 필드값의 유효성을 검증하는 유효성 검사 함수들을 임포트합니다.
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
        # [역할] 전달받은 파일 저장소 객체를 인스턴스 변수에 바인딩합니다.
        # [사용 변수] self.repository: FileRepository 인스턴스
        self.repository = repository
        # [역할] 시스템 구동 시 기본 카테고리가 등록되어 있는지 확인하고 자동 생성합니다.
        self._ensure_default_categories()

    # 카테고리 파일이 비어 있으면 기본 카테고리를 자동으로 등록한다.
    def _ensure_default_categories(self) -> None:
        # [역할] 기존에 저장된 카테고리가 1개라도 존재하는지 확인합니다.
        # [상태 검사] self.repository.stream_categories()에 원소가 있으면 즉시 함수를 종료합니다.
        if any(self.repository.stream_categories()):
            return

        # [역할] 초기 등록용 기본 카테고리 명칭 목록을 정의합니다.
        # [사용 변수] default_categories: 기본 카테고리 문자열 리스트
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

        # [역할] 기본 카테고리 명칭들을 순회하며 저장소에 차례대로 추가합니다.
        for name in default_categories:
            # [상태 변화] Category 모델 객체를 생성하여 저장소 파일에 한 줄씩 기록합니다.
            self.repository.add_category(Category(name=name))

    # 현재 등록된 카테고리 이름들을 집합으로 반환한다.
    def _get_category_names(self) -> set[str]:
        # [역할] 저장소의 카테고리들을 순회하며 이름(name)만 추출해 중복 없는 set 집합으로 반환합니다.
        # [반환값] 등록된 카테고리명 set[str] (유효성 검사 시 빠른 O(1) 포함 여부 조회에 활용)
        return {
            category.name
            for category in self.repository.stream_categories()
        }

    # 거래 ID를 중복되지 않는 새로운 값으로 생성한다.
    def _generate_transaction_id(self) -> str:
        # [역할] 이미 파일에 저장되어 있는 모든 거래들의 고유 ID를 수집해 set 집합으로 만듭니다.
        # [사용 변수] existing_ids: 기존 거래 ID 문자열 집합
        existing_ids = {
            transaction.id
            for transaction in self.repository.stream_transactions()
        }

        # [역할] 중복되지 않는 고유 ID가 생성될 때까지 무한 반복 루프를 돕니다.
        while True:
            # [역할] 무작위 UUID v4를 생성하고 앞 12자리 16진수 문자열을 잘라냅니다.
            # [사용 변수] transaction_id: 12자리 hex 문자열
            transaction_id = uuid.uuid4().hex[:12]
            # [상태 검사] 기존 ID 목록에 존재하지 않는 순수 고유 ID라면 즉시 반환합니다.
            if transaction_id not in existing_ids:
                return transaction_id

    # 거래를 최신순으로 제한된 개수만 스트리밍해서 반환한다.
    def stream_latest_transactions(
        self,
        limit: int = 20,
    ) -> Iterator[Transaction]:
        # [역할] 문자열 또는 정수 형태로 들어온 개수 제한 인자를 유효성 검사하여 정수값으로 정제합니다.
        # [사용 변수] limit: 조회할 최대 거래 건수 (정수)
        limit = validate_limit(str(limit))

        # [역할] 파일을 한 줄씩 스트리밍하면서 날짜가 가장 최근인 limit개만 힙에 유지합니다.
        # [메모리] 파일 크기와 상관없이 항상 limit개만 메모리에 남습니다. (전체 적재 X)
        latest = heapq.nlargest(
            limit,
            self.repository.stream_transactions(),
            key=lambda transaction: transaction.date,
        )

        # [역할] 최신순으로 골라진 거래를 제너레이터로 차례대로 반환합니다.
        yield from latest

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
        # [역할] 입력된 날짜(YYYY-MM-DD) 형식을 검증하고 정제합니다.
        date = validate_date(date)
        # [역할] 거래 유형(income/expense) 형식을 검증합니다.
        transaction_type = validate_type(transaction_type)
        # [역할] 금액이 양의 정수 형식인지 검증하고 int 숫자로 변환합니다.
        amount_value = validate_amount(amount)

        # [역할] 현재 등록된 카테고리 목록을 가져와 해당 카테고리가 실존하는지 검증합니다.
        category_names = self._get_category_names()
        category = validate_category(category, category_names)

        # [역할] 쉼표로 구분된 태그 문자열을 정제된 태그 리스트로 분리/검증합니다.
        tag_list = validate_tags(tags)

        # [역할] 중복 없는 고유 ID와 검증 완료된 필드들을 바탕으로 새 Transaction 모델 인스턴스를 생성합니다.
        # [사용 변수] transaction: 새로 생성된 Transaction 객체
        transaction = Transaction(
            id=self._generate_transaction_id(),
            type=transaction_type,
            date=date,
            amount=amount_value,
            category=category,
            memo=memo.strip(),
            tags=tag_list,
        )

        # [역할] 저장소 파일에 새로운 거래 내역을 한 줄 추가 기록합니다.
        # [상태 변화] transactions 파일에 신규 데이터 영속화 완료
        self.repository.add_transaction(transaction)

        # [역할] 등록 완료된 Transaction 객체를 반환합니다.
        return transaction

    # 거래를 검색 조건에 맞춰 필터링하고 최신순으로 반환한다.
    def search_transactions(
        self,
        from_date: str | None = None,
        to_date: str | None = None,
        category: str | None = None,
        transaction_type: str | None = None,
        query: str | None = None,
        tag: str | None = None,
    ) -> Iterator[Transaction]:
        # [역할] 시작 날짜 조건이 있으면 YYYY-MM-DD 형식을 검증합니다.
        if from_date:
            from_date = validate_date(from_date)

        # [역할] 종료 날짜 조건이 있으면 YYYY-MM-DD 형식을 검증합니다.
        if to_date:
            to_date = validate_date(to_date)

        # [역할] 시작일이 종료일보다 뒤인 논리적 오류가 발생하면 예외를 던집니다.
        if from_date and to_date and from_date > to_date:
            raise ValueError(
                "검색 시작일이 종료일보다 늦습니다. 날짜 범위를 확인하세요."
            )

        # [역할] 거래 유형 조건이 있으면 유효성을 검증합니다.
        if transaction_type:
            transaction_type = validate_type(transaction_type)

        # [역할] 카테고리 조건이 있으면 실존 카테고리인지 검증합니다.
        if category:
            category_names = self._get_category_names()
            category = validate_category(category, category_names)

        # [역할] 필터링된 거래들을 정렬하기 전 임시로 담아둘 리스트 버퍼를 선언합니다.
        # [사용 변수] buffer: 필터 조건에 부합하는 Transaction 객체 리스트
        buffer: list[Transaction] = []

        # [역할] 저장소의 모든 거래를 스트리밍 순회하며 검색 조건을 하나씩 대조합니다.
        for transaction in self.repository.stream_transactions():
            # [조건 1] 거래 날짜가 시작일보다 이전이면 건너뜁니다.
            if from_date and transaction.date < from_date:
                continue

            # [조건 2] 거래 날짜가 종료일보다 이후이면 건너뜁니다.
            if to_date and transaction.date > to_date:
                continue

            # [조건 3] 지정된 카테고리와 일치하지 않으면 건너뜁니다.
            if category and transaction.category != category:
                continue

            # [조건 4] 지정된 거래 유형(수입/지출)과 일치하지 않으면 건너뜁니다.
            if (
                transaction_type
                and transaction.type != transaction_type
            ):
                continue

            # [조건 5] 검색 쿼리가 메모에 대소문자 무시 포함되어 있지 않으면 건너뜁니다.
            if query:
                if query.lower() not in transaction.memo.lower():
                    continue

            # [조건 6] 지정된 태그가 해당 거래의 태그 목록에 없으면 건너뜁니다.
            if tag and tag not in transaction.tags:
                continue

            # [역할] 모든 조건을 통과한 거래 객체만 임시 버퍼 리스트에 추가합니다.
            buffer.append(transaction)

        # [역할] 필터링된 거래들을 최신 날짜 우선(내림차순)으로 정렬합니다.
        buffer.sort(
            key=lambda transaction: transaction.date,
            reverse=True,
        )

        # [역할] 정렬된 버퍼의 거래 항목들을 제너레이터 형태로 순차 방출합니다.
        yield from buffer

    # 거래 ID로 거래 하나를 찾아 반환한다.
    def get_transaction(
        self,
        transaction_id: str,
    ) -> Transaction | None:
        # [역할] 저장소의 거래 내역을 하나씩 순회하며 대상 ID와 일치하는 거래를 탐색합니다.
        for transaction in self.repository.stream_transactions():
            # [역할] 일치하는 ID를 찾으면 해당 객체를 즉시 반환합니다.
            if transaction.id == transaction_id:
                return transaction

        # [역할] 전체를 뒤져도 일치하는 거래가 없으면 None을 반환합니다.
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
        # [역할] 전체 거래 목록을 갱신하기 위해 새롭게 구성할 리스트를 선언합니다.
        transactions = []
        # [역할] 수정 대상이 되는 거래 객체를 참조할 변수입니다.
        target = None

        # [역할] 카테고리 검증에 필요한 현재 등록된 카테고리 집합을 조회합니다.
        category_names = self._get_category_names()

        # [역할] 저장소의 거래 목록을 하나씩 순회합니다.
        for transaction in self.repository.stream_transactions():
            # [역할] 수정 대상 ID가 아니면 그대로 새 리스트에 넣고 다음으로 넘어갑니다.
            if transaction.id != transaction_id:
                transactions.append(transaction)
                continue

            # [역할] 수정 대상 거래 객체를 target 변수에 바인딩합니다.
            target = transaction

            # [값 갱신: date] 인자가 들어왔으면 유효성 검사 후 날짜를 수정합니다.
            if date is not None:
                date = validate_date(date)
                target.date = date

            # [값 갱신: type] 인자가 들어왔으면 수입/지출 유형을 검증 후 수정합니다.
            if transaction_type is not None:
                target.type = validate_type(transaction_type)

            # [값 갱신: category] 인자가 들어왔으면 실존 카테고리인지 검증 후 수정합니다.
            if category is not None:
                target.category = validate_category(
                    category,
                    category_names,
                )

            # [값 갱신: amount] 인자가 들어왔으면 금액을 검증하고 숫자로 수정합니다.
            if amount is not None:
                target.amount = validate_amount(amount)

            # [값 갱신: memo] 인자가 들어왔으면 양 끝 공백을 잘라내어 수정합니다.
            if memo is not None:
                target.memo = memo.strip()

            # [값 갱신: tags] 인자가 들어왔으면 태그 문자열을 리스트로 파싱하여 수정합니다.
            if tags is not None:
                target.tags = validate_tags(tags)

            # [역할] 수정이 완료된 대상 객체를 전체 리스트에 추가합니다.
            transactions.append(target)

        # [예외 검사] 전체를 순회했음에도 대상 ID를 찾지 못했으면 예외를 발생시킵니다.
        if target is None:
            raise ValueError(
                f"거래 ID를 찾을 수 없습니다: {transaction_id}"
            )

        # [역할] 갱신된 전체 거래 리스트를 파일 저장소에 덮어써서 영속화합니다.
        self.repository.rewrite_transactions(iter(transactions))

        # [역할] 최종 수정된 거래 객체를 반환합니다.
        return target

    # 거래 ID에 해당하는 거래를 삭제한다.
    @log_execution
    def delete_transaction(self, transaction_id: str) -> None:
        # [역할] 삭제 대상을 제외한 나머지 거래들을 보관할 리스트를 선언합니다.
        transactions = []
        # [역할] 삭제 대상이 실제로 발견되어 제거되었는지 여부를 추적하는 플래그입니다.
        deleted = False

        # [역할] 저장소의 전체 거래를 하나씩 순회합니다.
        for transaction in self.repository.stream_transactions():
            # [역할] 삭제 대상 거래를 만나면 deleted 플래그를 세우고 리스트에 추가하지 않습니다.
            if transaction.id == transaction_id:
                deleted = True
                continue

            # [역할] 삭제 대상이 아닌 거래들만 보존 리스트에 추가합니다.
            transactions.append(transaction)

        # [예외 검사] 삭제 대상 거래가 존재하지 않아 삭제가 이루어지지 않았다면 예외를 던집니다.
        if not deleted:
            raise ValueError(
                f"거래 ID를 찾을 수 없습니다: {transaction_id}"
            )

        # [역할] 삭제 대상이 제거된 새 리스트로 거래 파일 전체를 덮어씁니다.
        self.repository.rewrite_transactions(iter(transactions))

    # 월별 수입과 지출을 계산하고 예산 사용 현황을 반환한다.
    @log_execution
    @measure_time
    def get_summary(
        self,
        month: str,
        top: int = 5,
    ) -> dict:
        # [역할] 월(YYYY-MM) 형식을 검증합니다.
        month = validate_month(month)
        # [역할] 상위 지출 표시 개수(top) 인자를 정수로 검증합니다.
        top = validate_top(str(top))

        # [누적 변수] 해당 월 총 수입 금액 합산 변수
        income_total = 0
        # [누적 변수] 해당 월 총 지출 금액 합산 변수
        expense_total = 0
        # [누적 변수] 카테고리별 누적 지출 금액을 매핑할 딕셔너리
        expense_by_category: dict[str, int] = {}
        # [누적 변수] 해당 월 총 거래 건수 카운트 변수
        transaction_count = 0

        # [역할] 전체 거래를 순회하며 지정된 월에 해당하는 거래 데이터만 집계합니다.
        for transaction in self.repository.stream_transactions():
            # [필터링] 거래 날짜가 지정된 월(YYYY-MM)로 시작하지 않으면 건너뜁니다.
            if not transaction.date.startswith(month):
                continue

            # [카운트 증가] 해당 월 거래 건수를 1 올립니다.
            transaction_count += 1

            # [수입 집계] 거래 유형이 수입이면 총 수입액에 더합니다.
            if transaction.type == "income":
                income_total += transaction.amount
            # [지출 집계] 거래 유형이 지출이면 총 지출액 및 카테고리별 누적액에 더합니다.
            else:
                expense_total += transaction.amount
                expense_by_category[transaction.category] = (
                    expense_by_category.get(transaction.category, 0)
                    + transaction.amount
                )

        # [역할] 해당 월에 설정되어 있는 예산 객체를 가져옵니다.
        budget = self.get_budget(month)

        # [역할] 총 수입에서 총 지출을 뺀 잔액을 계산합니다.
        balance = income_total - expense_total

        # [역할] 카테고리별 지출액을 내림차순(금액 큰 순)으로 정렬하고 상위 top개만 잘라냅니다.
        top_categories = sorted(
            expense_by_category.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:top]

        # [역할] 예산 사용률 기본값을 None으로 초기화합니다.
        usage_percent = None
        # [역할] 예산 초과 여부 기본값을 False로 초기화합니다.
        budget_exceeded = False

        # [역할] 해당 월 예산이 등록되어 있는 경우 사용률(%)과 초과 여부를 계산합니다.
        if budget is not None:
            # [사용률 계산] (총 지출 / 예산 금액) * 100
            usage_percent = (
                expense_total / budget.amount
            ) * 100

            # [초과 여부] 총 지출이 예산 금액보다 큰지 판별
            budget_exceeded = expense_total > budget.amount

        # [역할] 계산된 모든 통계 데이터를 딕셔너리로 조립하여 반환합니다.
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
        # [역할] 대상 월(YYYY-MM) 형식을 검증합니다.
        month = validate_month(month)
        # [역할] 예산 금액이 양의 정수인지 검증하고 int로 변환합니다.
        amount_value = validate_amount(amount)

        # [역할] 파일에 새로 쓸 전체 예산 목록 리스트를 선언합니다.
        budgets = []
        # [역할] 새로 등록하거나 교체할 신규 Budget 인스턴스를 생성합니다.
        target = Budget(
            month=month,
            amount=amount_value,
        )
        # [역할] 기존 예산의 수정/교체가 발생했는지 추적하는 플래그입니다.
        replaced = False

        # [역할] 저장소의 기존 예산들을 순회합니다.
        for budget in self.repository.stream_budgets():
            # [역할] 동일한 월의 예산이 이미 있다면 새 Budget 객체(target)로 대체합니다.
            if budget.month == month:
                budgets.append(target)
                replaced = True
            # [역할] 다른 월의 예산은 그대로 리스트에 보존합니다.
            else:
                budgets.append(budget)

        # [역할] 순회가 끝났는데도 대체되지 않았다면 신규 등록이므로 끝에 추가합니다.
        if not replaced:
            budgets.append(target)

        # [역할] 구성된 예산 목록 전체를 저장소 파일에 덮어씁니다.
        self.repository.rewrite_budgets(iter(budgets))

        # [역할] 최종 저장된 Budget 인스턴스를 반환합니다.
        return target

    # 특정 월에 등록된 예산을 찾아 반환한다.
    def get_budget(self, month: str) -> Budget | None:
        # [역할] 조회할 대상 월(YYYY-MM) 형식을 검증합니다.
        month = validate_month(month)

        # [역할] 저장소의 예산 목록을 순회하며 일치하는 월을 찾습니다.
        for budget in self.repository.stream_budgets():
            # [역할] 해당 월의 Budget 객체를 찾으면 즉시 반환합니다.
            if budget.month == month:
                return budget

        # [역할] 해당 월에 등록된 예산이 없다면 None을 반환합니다.
        return None

    # 새로운 카테고리를 등록하고 등록된 카테고리를 반환한다.
    @log_execution
    def add_category(self, name: str) -> Category:
        # [역할] 카테고리 이름 규칙(공백 아님 등)을 검증합니다.
        name = validate_category_name(name)

        # [역할] 현재 등록된 카테고리명 목록을 가져옵니다.
        category_names = self._get_category_names()

        # [예외 검사] 동일한 이름의 카테고리가 이미 등록되어 있으면 예외를 발생시킵니다.
        if name in category_names:
            raise ValueError(
                f"이미 등록된 카테고리입니다: {name}"
            )

        # [역할] 새로운 Category 인스턴스를 생성하고 저장소 파일에 추가합니다.
        category = Category(name=name)
        self.repository.add_category(category)

        # [역할] 등록된 Category 객체를 반환합니다.
        return category

    # 현재 등록된 모든 카테고리를 이름순으로 반환한다.
    def list_categories(self) -> list[Category]:
        # [역할] 저장소의 모든 카테고리를 리스트로 수집합니다.
        categories = list(self.repository.stream_categories())
        # [역할] 카테고리 이름(name)을 기준으로 가나다순 오름차순 정렬합니다.
        categories.sort(key=lambda category: category.name)
        # [역할] 정렬된 카테고리 객체 리스트를 반환합니다.
        return categories

    # 사용 중이지 않은 카테고리만 삭제한다.
    @log_execution
    def remove_category(self, name: str) -> None:
        # [역할] 카테고리 이름 유효성을 검증합니다.
        name = validate_category_name(name)

        # [역할] 현재 등록된 카테고리 집합을 가져옵니다.
        category_names = self._get_category_names()

        # [예외 검사] 애초에 등록되어 있지 않은 카테고리라면 예외를 던집니다.
        if name not in category_names:
            raise ValueError(
                f"등록된 카테고리가 아닙니다: {name}"
            )

        # [예외 검사] 현재 저장된 거래 내역 중에 이 카테고리를 사용 중인 거래가 있는지 확인합니다.
        for transaction in self.repository.stream_transactions():
            # [역할] 1건이라도 사용 중인 거래가 발견되면 삭제를 금지하고 예외를 던집니다.
            if transaction.category == name:
                raise ValueError(
                    f"사용 중인 카테고리는 삭제할 수 없습니다: {name}"
                )

        # [역할] 삭제 대상을 제외한 나머지 카테고리들만 모아 새 리스트를 만듭니다.
        categories = [
            category
            for category in self.repository.stream_categories()
            if category.name != name
        ]

        # [역할] 필터링된 새 카테고리 목록으로 저장소 파일을 덮어씁니다.
        self.repository.rewrite_categories(iter(categories))

    # CSV 파일의 거래 데이터를 검증한 뒤 한꺼번에 저장한다.
    @log_execution
    @measure_time
    def import_csv(self, csv_path: str | Path) -> int:
        # [역할] 전달받은 경로를 Path 객체로 래핑합니다.
        csv_path = Path(csv_path)

        # [예외 검사] 지정된 경로에 CSV 파일이 실제로 존재하지 않으면 예외를 던집니다.
        if not csv_path.exists():
            raise ValueError(
                f"CSV 파일을 찾을 수 없습니다: {csv_path}"
            )

        # [역할] 카테고리 유효성 검증용 카테고리 집합을 조회합니다.
        category_names = self._get_category_names()
        # [역할] CSV에서 읽어 들여 유효성 검사를 통과한 거래 객체들을 임시 보관할 리스트입니다.
        imported_transactions: list[Transaction] = []

        # [역할] CSV 파일에 반드시 존재해야 하는 필수 헤더 컬럼명 세트입니다.
        # [명세] memo, tags는 선택 컬럼이므로 필수 검사에서 제외합니다.
        required_columns = {
            "date",
            "type",
            "category",
            "amount",
        }

        # [역할] UTF-8 BOM 인코딩을 고려하여 CSV 파일을 읽기 모드로 엽니다.
        with csv_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:
            # [역할] 헤더 기반 딕셔너리 리더를 생성합니다.
            reader = csv.DictReader(file)

            # [예외 검사] 파일이 완전히 비어있어 헤더(fieldnames)를 읽을 수 없는 경우 예외를 던집니다.
            if reader.fieldnames is None:
                raise ValueError(
                    "CSV 헤더가 없습니다. 지정된 CSV 형식을 확인하세요."
                )

            # [예외 검사] 필수 컬럼 중 누락된 컬럼이 있는지 확인합니다.
            missing_columns = required_columns - set(reader.fieldnames)

            # [역할] 누락된 컬럼이 있으면 누락된 컬럼명을 나열하며 예외를 던집니다.
            if missing_columns:
                raise ValueError(
                    "CSV 필수 컬럼이 없습니다: "
                    + ", ".join(sorted(missing_columns))
                )

            # [역할] 헤더 다음 행(2번째 줄)부터 한 줄씩 순회하며 행 단위 검증을 수행합니다.
            for row_number, row in enumerate(reader, start=2):
                try:
                    # [필드 검증] 날짜, 거래 유형, 금액, 카테고리, 태그 유효성을 검사합니다.
                    date = validate_date(row["date"])
                    transaction_type = validate_type(row["type"])
                    amount = validate_amount(row["amount"])
                    category = validate_category(
                        row["category"],
                        category_names,
                    )
                    # [선택 컬럼] 컬럼이 없거나 비어 있으면 빈 값으로 처리합니다.
                    tags = validate_tags(row.get("tags") or "")

                    # [객체 생성] 검증이 통과된 행을 Transaction 인스턴스로 변환하여 임시 리스트에 추가합니다.
                    imported_transactions.append(
                        Transaction(
                            id=self._generate_transaction_id(),
                            type=transaction_type,
                            date=date,
                            amount=amount,
                            category=category,
                            memo=(row.get("memo") or "").strip(),
                            tags=tags,
                        )
                    )

                # [예외 래핑] 중간 행에서 오류 발생 시 몇 번째 행에서 터졌는지 명시하여 다시 던집니다.
                except ValueError as error:
                    raise ValueError(
                        f"CSV {row_number}번째 행이 잘못되었습니다: {error}"
                    ) from error

        # [역할] 모든 행 검증이 무사히 완료되면 저장소에 순차적으로 한 건씩 영속화합니다.
        for transaction in imported_transactions:
            self.repository.add_transaction(transaction)

        # [역할] 성공적으로 등록된 총 거래 건수를 반환합니다.
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
        # [예외 검사] 월 지정 또는 날짜 범위 지정 중 하나도 주어지지 않으면 예외를 던집니다.
        if not month and not (from_date or to_date):
            raise ValueError(
                "CSV 내보내기에는 --month 또는 --from/--to 조건이 필요합니다."
            )

        # [역할] 월 조건이 전달되었으면 YYYY-MM 형식을 검증합니다.
        if month:
            month = validate_month(month)

        # [역할] 시작일 조건이 전달되었으면 YYYY-MM-DD 형식을 검증합니다.
        if from_date:
            from_date = validate_date(from_date)

        # [역할] 종료일 조건이 전달되었으면 YYYY-MM-DD 형식을 검증합니다.
        if to_date:
            to_date = validate_date(to_date)

        # [예외 검사] 시작일이 종료일보다 뒤인 논리적 오류가 발생하면 예외를 던집니다.
        if from_date and to_date and from_date > to_date:
            raise ValueError(
                "검색 시작일이 종료일보다 늦습니다. 날짜 범위를 확인하세요."
            )

        # [역할] 출력 파일 경로를 Path 객체로 래핑합니다.
        csv_path = Path(csv_path)

        # [카운터] CSV 파일에 성공적으로 기록된 행의 개수를 세는 변수입니다.
        count = 0

        # [역할] UTF-8 인코딩으로 지정 경로에 CSV 파일을 새로 생성(쓰기 모드)합니다.
        with csv_path.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as file:
            # [역할] 출력할 필드 순서를 정의하고 DictWriter를 초기화합니다.
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

            # [역할] CSV 맨 첫 줄에 헤더 컬럼명들을 출력합니다.
            writer.writeheader()

            # [역할] 저장소의 전체 거래를 하나씩 순회하며 필터링 후 파일에 기록합니다.
            for transaction in self.repository.stream_transactions():
                # [필터링 1] 특정 월 조건이 주어졌는데 일치하지 않으면 건너뜁니다.
                if month and not transaction.date.startswith(month):
                    continue

                # [필터링 2] 시작일 조건보다 앞선 날짜의 거래면 건너뜁니다.
                if from_date and transaction.date < from_date:
                    continue

                # [필터링 3] 종료일 조건보다 늦은 날짜의 거래면 건너뜁니다.
                if to_date and transaction.date > to_date:
                    continue

                # [역할] 조건을 통과한 거래 데이터를 CSV 형식으로 기록합니다.
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

                # [카운트 증가] 내보낸 거래 건수를 1 올립니다.
                count += 1

        # [역할] 최종 내보내기 완료된 거래 건수를 반환합니다.
        return count