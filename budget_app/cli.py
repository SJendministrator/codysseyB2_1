import argparse

from .commands import (
    handle_add,
    handle_budget_set,
    handle_category_add,
    handle_category_list,
    handle_category_remove,
    handle_delete,
    handle_export,
    handle_import,
    handle_list,
    handle_search,
    handle_summary,
    handle_update,
)


# 프로그램에서 사용할 최상위 명령어와 옵션을 구성한다.
def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="budget_app",
        description="Python 콘솔 가계부 프로그램",
    )

    parser.add_argument(
        "--data-dir",
        default="data",
        help="데이터 저장 폴더를 지정합니다. 기본값: data",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    # 거래 추가 명령어의 옵션을 구성한다.
    add_parser = subparsers.add_parser(
        "add",
        help="새로운 거래를 추가합니다.",
    )
    add_parser.set_defaults(func=handle_add)

    # 거래 목록 조회 명령어의 옵션을 구성한다.
    list_parser = subparsers.add_parser(
        "list",
        help="최근 거래를 조회합니다.",
    )
    list_parser.add_argument(
        "--limit",
        default=20,
        type=int,
        help="조회할 거래 수. 기본값: 20",
    )
    list_parser.set_defaults(func=handle_list)

    # 거래 검색 명령어의 옵션을 구성한다.
    search_parser = subparsers.add_parser(
        "search",
        help="조건에 맞는 거래를 검색합니다.",
    )
    search_parser.add_argument("--from", dest="from_date")
    search_parser.add_argument("--to", dest="to_date")
    search_parser.add_argument("--category")
    search_parser.add_argument(
        "--type",
        dest="transaction_type",
    )
    search_parser.add_argument(
        "--q",
        help="메모에서 검색할 키워드",
    )
    search_parser.add_argument(
        "--tag",
        help="검색할 태그",
    )
    search_parser.set_defaults(func=handle_search)

    # 월별 거래 요약 명령어의 옵션을 구성한다.
    summary_parser = subparsers.add_parser(
        "summary",
        help="월별 거래를 요약합니다.",
    )
    summary_parser.add_argument(
        "--month",
        required=True,
        help="조회할 월. 예: 2026-09",
    )
    summary_parser.add_argument(
        "--top",
        default=5,
        type=int,
        help="지출 상위 카테고리 수. 기본값: 5",
    )
    summary_parser.set_defaults(func=handle_summary)

    # 예산 설정 명령어의 옵션을 구성한다.
    budget_parser = subparsers.add_parser(
        "budget",
        help="월별 예산을 관리합니다.",
    )
    budget_subparsers = budget_parser.add_subparsers(
        dest="budget_command",
        required=True,
    )

    budget_set_parser = budget_subparsers.add_parser(
        "set",
        help="월별 예산을 설정합니다.",
    )
    budget_set_parser.add_argument(
        "--month",
        required=True,
    )
    budget_set_parser.add_argument(
        "--amount",
        required=True,
    )
    budget_set_parser.set_defaults(func=handle_budget_set)

    # 카테고리 관리 명령어를 구성한다.
    category_parser = subparsers.add_parser(
        "category",
        help="카테고리를 관리합니다.",
    )
    category_subparsers = category_parser.add_subparsers(
        dest="category_command",
        required=True,
    )

    category_add_parser = category_subparsers.add_parser(
        "add",
        help="카테고리를 추가합니다.",
    )
    category_add_parser.add_argument(
        "--name",
        required=True,
    )
    category_add_parser.set_defaults(func=handle_category_add)

    category_list_parser = category_subparsers.add_parser(
        "list",
        help="카테고리를 조회합니다.",
    )
    category_list_parser.set_defaults(func=handle_category_list)

    category_remove_parser = category_subparsers.add_parser(
        "remove",
        help="카테고리를 삭제합니다.",
    )
    category_remove_parser.add_argument(
        "--name",
        required=True,
    )
    category_remove_parser.set_defaults(func=handle_category_remove)

    # 거래 수정 명령어의 옵션을 구성한다.
    update_parser = subparsers.add_parser(
        "update",
        help="기존 거래를 수정합니다.",
    )
    update_parser.add_argument(
        "--id",
        required=True,
        help="수정할 거래 ID",
    )
    update_parser.add_argument("--date")
    update_parser.add_argument(
        "--type",
        dest="transaction_type",
    )
    update_parser.add_argument("--category")
    update_parser.add_argument("--amount")
    update_parser.add_argument("--memo")
    update_parser.add_argument(
        "--tags",
        help="쉼표로 구분한 태그",
    )
    update_parser.set_defaults(func=handle_update)

    # 거래 삭제 명령어의 옵션을 구성한다.
    delete_parser = subparsers.add_parser(
        "delete",
        help="거래를 삭제합니다.",
    )
    delete_parser.add_argument(
        "--id",
        required=True,
        help="삭제할 거래 ID",
    )
    delete_parser.set_defaults(func=handle_delete)

    # CSV 가져오기 명령어의 옵션을 구성한다.
    import_parser = subparsers.add_parser(
        "import",
        help="CSV 파일에서 거래를 가져옵니다.",
    )
    import_parser.add_argument(
        "--from",
        dest="csv_path",
        required=True,
        help="가져올 CSV 파일",
    )
    import_parser.set_defaults(func=handle_import)

    # CSV 내보내기 명령어의 옵션을 구성한다.
    export_parser = subparsers.add_parser(
        "export",
        help="거래를 CSV 파일로 내보냅니다.",
    )
    export_parser.add_argument(
        "--out",
        required=True,
        help="생성할 CSV 파일",
    )
    export_parser.add_argument(
        "--month",
        help="내보낼 월. 예: 2026-09",
    )
    export_parser.add_argument(
        "--from",
        dest="from_date",
        help="내보낼 시작일",
    )
    export_parser.add_argument(
        "--to",
        dest="to_date",
        help="내보낼 종료일",
    )
    export_parser.set_defaults(func=handle_export)

    return parser


# 명령행 인자를 분석하고 선택된 명령어 함수를 실행한다.
def run() -> int:
    parser = create_parser()
    args = parser.parse_args()

    return args.func(args)