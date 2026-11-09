from typing import Callable, TypeVar

from .repository import FileRepository
from .services import BudgetService
from .formatters import (
    format_category,
    format_summary,
    format_transaction,
)
from .validators import (
    validate_amount,
    validate_category,
    validate_date,
    validate_tags,
    validate_type,
)

T = TypeVar("T")


# 명령어에서 사용할 서비스 객체를 생성한다.
def _create_service(data_dir: str) -> BudgetService:
    repository = FileRepository(data_dir)
    return BudgetService(repository)


# ---------------------------------------------------------------------
# 대화형 입력 도우미
# ---------------------------------------------------------------------
# 한 항목을 입력받아 바로 검증한다. 틀리면 '그 항목만' 다시 묻는다.
#   (예전: 6개를 다 입력받은 뒤 한꺼번에 검증 → 빈칸도 일단 넘어가고, 틀리면 날짜부터 다시)
def _ask(prompt: str, validator: Callable[[str], T], hint: str = "") -> T:
    while True:
        value = input(prompt)
        try:
            return validator(value)
        except ValueError as error:
            print(f"[입력 오류] {error}")
            if hint:
                print(hint)


# ---------------------------------------------------------------------
# add: 사용자에게 거래 정보를 입력받아 새 거래를 추가한다.
# ---------------------------------------------------------------------
def handle_add(args) -> int:
    service = _create_service(args.data_dir)
    categories = service.category_names()

    # --- 필수 항목: 입력 즉시 검증, 통과할 때까지 같은 항목 재입력 ---
    date = _ask("날짜 (YYYY-MM-DD): ", validate_date)
    transaction_type = _ask("거래 타입 (income/expense): ", validate_type)
    category = _ask(
        f"카테고리 ({', '.join(categories)}): ",
        lambda value: validate_category(value, categories),
        hint="  → 목록에 없는 카테고리는 먼저 `category add --name 이름` 으로 등록하세요.",
    )
    amount = _ask("금액: ", validate_amount)

    # --- 선택 항목: 비워도 됨 ---
    memo = input("메모 (선택): ")
    tags = _ask("태그 (쉼표로 구분, 선택): ", lambda value: ",".join(validate_tags(value)))

    # --- 저장 (서비스에서 한 번 더 검증한 뒤 파일에 기록) ---
    transaction = service.add_transaction(
        date=date,
        transaction_type=transaction_type,
        category=category,
        amount=str(amount),
        memo=memo,
        tags=tags,
    )

    print("거래가 추가되었습니다.")
    print(f"생성된 ID: {transaction.id}")

    return 0


# 최근 거래를 최신순으로 출력한다.
def handle_list(args) -> int:
    service = _create_service(args.data_dir)

    try:
        transactions = service.stream_latest_transactions(
            args.limit
        )

        count = 0

        for transaction in transactions:
            print(format_transaction(transaction))
            count += 1

        if count == 0:
            print("데이터 없음")

        return 0

    except ValueError as error:
        print(f"[오류] {error}")
        return 1


# 검색 조건에 맞는 거래를 최신순으로 출력한다.
def handle_search(args) -> int:
    service = _create_service(args.data_dir)

    try:
        transactions = service.search_transactions(
            from_date=args.from_date,
            to_date=args.to_date,
            category=args.category,
            transaction_type=args.transaction_type,
            query=args.q,
            tag=args.tag,
        )

        count = 0

        for transaction in transactions:
            print(format_transaction(transaction))
            count += 1

        if count == 0:
            print("데이터 없음")

        return 0

    except ValueError as error:
        print(f"[검색 오류] {error}")
        return 1


# 지정한 월의 수입과 지출을 요약해서 출력한다.
def handle_summary(args) -> int:
    service = _create_service(args.data_dir)

    try:
        summary = service.get_summary(
            month=args.month,
            top=args.top,
        )

        if summary["transaction_count"] == 0:
            print(f"{args.month}: 데이터 없음")
            return 0

        print(format_summary(summary))

        return 0

    except ValueError as error:
        print(f"[요약 오류] {error}")
        return 1


# 특정 월의 예산을 설정한다.
def handle_budget_set(args) -> int:
    service = _create_service(args.data_dir)

    try:
        budget = service.set_budget(
            month=args.month,
            amount=args.amount,
        )

        print(
            f"{budget.month} 예산이 "
            f"{budget.amount:,}원으로 설정되었습니다."
        )

        return 0

    except ValueError as error:
        print(f"[예산 오류] {error}")
        return 1


# 새로운 카테고리를 추가한다.
def handle_category_add(args) -> int:
    service = _create_service(args.data_dir)

    try:
        category = service.add_category(args.name)

        print(
            f"카테고리가 추가되었습니다: "
            f"{category.name}"
        )

        return 0

    except ValueError as error:
        print(f"[카테고리 오류] {error}")
        return 1


# 등록된 카테고리를 출력한다.
def handle_category_list(args) -> int:
    service = _create_service(args.data_dir)

    categories = service.list_categories()

    if not categories:
        print("등록된 카테고리가 없습니다.")
        return 0

    for category in categories:
        print(format_category(category))

    return 0


# 카테고리를 삭제한다.
def handle_category_remove(args) -> int:
    service = _create_service(args.data_dir)

    try:
        service.remove_category(args.name)

        print(
            f"카테고리가 삭제되었습니다: "
            f"{args.name}"
        )

        return 0

    except ValueError as error:
        # 오류 원인(없는 카테고리 / 사용 중인 카테고리)은 서비스가 보낸 메시지에 이미 담겨 있다.
        print(f"[카테고리 오류] {error}")
        return 1


# 지정한 거래의 일부 항목을 수정한다.
def handle_update(args) -> int:
    service = _create_service(args.data_dir)

    try:
        transaction = service.update_transaction(
            transaction_id=args.id,
            date=args.date,
            transaction_type=args.transaction_type,
            category=args.category,
            amount=args.amount,
            memo=args.memo,
            tags=args.tags,
        )

        print("거래가 수정되었습니다.")
        print(format_transaction(transaction))

        return 0

    except ValueError as error:
        print(f"[수정 오류] {error}")
        return 1


# 지정한 거래를 삭제한다.
def handle_delete(args) -> int:
    service = _create_service(args.data_dir)

    try:
        service.delete_transaction(args.id)

        print(
            f"거래가 삭제되었습니다: {args.id}"
        )

        return 0

    except ValueError as error:
        print(f"[삭제 오류] {error}")
        return 1


# CSV 파일에서 거래를 가져온다.
def handle_import(args) -> int:
    service = _create_service(args.data_dir)

    try:
        count, skipped = service.import_csv(args.csv_path)

        print(
            f"CSV 가져오기가 완료되었습니다. "
            f"{count}건 추가"
            + (f", 이미 있는 거래 {skipped}건은 중복이라 건너뜀" if skipped else "")
        )

        return 0

    except (ValueError, OSError) as error:
        print(f"[가져오기 오류] {error}")
        return 1


# 조건에 맞는 거래를 CSV 파일로 내보낸다.
def handle_export(args) -> int:
    service = _create_service(args.data_dir)

    try:
        count = service.export_csv(
            csv_path=args.out,
            month=args.month,
            from_date=args.from_date,
            to_date=args.to_date,
        )

        print(
            f"CSV 내보내기가 완료되었습니다. "
            f"{count}건 저장"
        )

        return 0

    except (ValueError, OSError) as error:
        print(f"[내보내기 오류] {error}")
        return 1