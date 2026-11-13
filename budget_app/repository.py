from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Iterator

from .models import Budget, Category, Transaction


# JSONL 파일을 저장할 기본 디렉터리를 설정한다.
DEFAULT_DATA_DIR = Path("data")

# 파일별로 한 줄(레코드)에 반드시 있어야 하는 키. 하나라도 빠지면 손상된 줄로 본다.
REQUIRED_KEYS = {
    "transactions.jsonl": ("id", "type", "date", "amount", "category"),
    "categories.jsonl": ("name",),
    "budgets.jsonl": ("month", "amount"),
}


# 저장 파일에 손상된 줄이 있어 쓰기를 중단할 때 사용하는 오류.
# ValueError 를 상속해 기존 명령 핸들러의 오류 출력 흐름을 그대로 탄다.
class CorruptedDataError(ValueError):
    pass


# 거래, 카테고리, 예산 데이터를 파일에 저장하고 조회하는 기능을 담당한다.
class FileRepository:
    # 데이터 저장 폴더를 설정하고 필요한 JSONL 파일을 준비한다.
    def __init__(self, data_dir: str | Path = DEFAULT_DATA_DIR):
        self.data_dir = Path(data_dir)

        self.transactions_file = self.data_dir / "transactions.jsonl"
        self.categories_file = self.data_dir / "categories.jsonl"
        self.budgets_file = self.data_dir / "budgets.jsonl"

        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._create_file_if_missing(self.transactions_file)
        self._create_file_if_missing(self.categories_file)
        self._create_file_if_missing(self.budgets_file)

    # 지정한 파일이 없으면 빈 JSONL 파일을 생성한다.
    def _create_file_if_missing(self, file_path: Path) -> None:
        if not file_path.exists():
            file_path.touch()

    # JSONL 파일에 하나의 데이터를 한 줄로 추가한다.
    def _append_json(self, file_path: Path, data: dict) -> None:
        with file_path.open("a", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False)
            file.write("\n")

    # 한 줄을 레코드로 해석한다. JSON 이 깨졌거나 필수 키·숫자 형식이 맞지 않으면 None 을 돌려준다.
    def _parse_record(self, file_path: Path, line: str) -> dict | None:
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return None

        if not isinstance(data, dict):
            return None

        if any(key not in data for key in REQUIRED_KEYS.get(file_path.name, ())):
            return None

        if "amount" in data:
            try:
                int(data["amount"])
            except (TypeError, ValueError):
                return None

        return data

    # JSONL 파일을 한 줄씩 읽어 JSON 데이터로 변환한다. (제너레이터: 파일 전체를 메모리에 올리지 않음)
    # 손상된 줄은 건너뛰되, 조용히 숨기지 않고 몇 번째 줄인지 경고를 남긴다.
    def _stream_json(self, file_path: Path) -> Iterator[dict]:
        with file_path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                line = line.strip()

                if not line:
                    continue

                data = self._parse_record(file_path, line)

                if data is None:
                    print(
                        f"[경고] {file_path.name} {line_number}번째 줄이 손상되어 건너뜁니다.",
                        file=sys.stderr,
                    )
                    continue

                yield data

    # 파일 안의 손상된 줄 번호를 모두 찾는다. (재작성 전에 검사해 손상 줄이 지워지는 것을 막기 위함)
    def _find_corrupted_lines(self, file_path: Path) -> list[int]:
        corrupted = []

        with file_path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                line = line.strip()

                if line and self._parse_record(file_path, line) is None:
                    corrupted.append(line_number)

        return corrupted

    # transactions.jsonl에서 거래 데이터를 한 건씩 읽어온다.
    def stream_transactions(self) -> Iterator[Transaction]:
        for data in self._stream_json(self.transactions_file):
            yield Transaction(
                id=data["id"],
                type=data["type"],
                date=data["date"],
                amount=int(data["amount"]),
                category=data["category"],
                memo=data.get("memo", ""),
                tags=data.get("tags", []),
            )

    # 새로운 거래를 transactions.jsonl에 저장한다.
    def add_transaction(self, transaction: Transaction) -> None:
        self._append_json(
            self.transactions_file,
            {
                "id": transaction.id,
                "type": transaction.type,
                "date": transaction.date,
                "amount": transaction.amount,
                "category": transaction.category,
                "memo": transaction.memo,
                "tags": transaction.tags,
            },
        )

    # categories.jsonl에서 등록된 카테고리를 한 건씩 읽어온다.
    def stream_categories(self) -> Iterator[Category]:
        for data in self._stream_json(self.categories_file):
            yield Category(name=data["name"])

    # 새로운 카테고리를 categories.jsonl에 저장한다.
    def add_category(self, category: Category) -> None:
        self._append_json(
            self.categories_file,
            {
                "name": category.name,
            },
        )

    # budgets.jsonl에서 등록된 예산을 한 건씩 읽어온다.
    def stream_budgets(self) -> Iterator[Budget]:
        for data in self._stream_json(self.budgets_file):
            yield Budget(
                month=data["month"],
                amount=int(data["amount"]),
            )

    # 새로운 월별 예산을 budgets.jsonl에 저장한다.
    def add_budget(self, budget: Budget) -> None:
        self._append_json(
            self.budgets_file,
            {
                "month": budget.month, "amount": budget.amount,
            },
        )

    # 지정한 파일의 내용을 임시 파일에 작성한 후 원본 파일과 교체한다.
    def _atomic_replace(self, file_path: Path, lines: list[str]) -> None:
        # 재작성은 '읽을 수 있었던 줄'만 다시 쓰므로, 손상된 줄이 있으면 그대로 영구 삭제된다.
        # → 손상 줄이 하나라도 있으면 쓰기를 중단하고 원본을 그대로 둔다.
        corrupted = self._find_corrupted_lines(file_path)

        if corrupted:
            numbers = ", ".join(str(n) for n in corrupted[:10])
            raise CorruptedDataError(
                f"{file_path.name}의 {numbers}번째 줄이 손상되어 있어 저장을 중단했습니다. "
                f"(원본은 변경되지 않았습니다)\n"
                f"힌트: 파일을 백업한 뒤 해당 줄을 고치거나 지우고 다시 실행하세요."
            )

        fd, temp_path = tempfile.mkstemp(
            dir=self.data_dir, prefix=f"{file_path.stem}_",
            suffix=".tmp", text=True,
        )

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                for line in lines:
                    file.write(line)
                    file.write("\n")

            os.replace(temp_path, file_path)

        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise

    # 모든 거래를 새 내용으로 다시 작성해 update/delete에 사용한다.
    def rewrite_transactions(
        self,
        transactions: Iterator[Transaction],
    ) -> None:
        lines = []

        for transaction in transactions:
            data = {
                "id": transaction.id,
                "type": transaction.type,
                "date": transaction.date,
                "amount": transaction.amount,
                "category": transaction.category,
                "memo": transaction.memo,
                "tags": transaction.tags,
            }

            lines.append(
                json.dumps(data, ensure_ascii=False)
            )

        self._atomic_replace(
            self.transactions_file,
            lines,
        )

    # 모든 카테고리를 새 내용으로 다시 작성해 카테고리 삭제에 사용한다.
    def rewrite_categories(
        self,
        categories: Iterator[Category],
    ) -> None:
        lines = []

        for category in categories:
            lines.append(
                json.dumps(
                    {"name": category.name},
                    ensure_ascii=False,
                )
            )

        self._atomic_replace(
            self.categories_file,
            lines,
        )

    # 모든 예산을 새 내용으로 다시 작성해 예산 수정에 사용한다.
    def rewrite_budgets(
        self,
        budgets: Iterator[Budget],
    ) -> None:
        lines = []

        for budget in budgets:
            lines.append(
                json.dumps(
                    {
                        "month": budget.month,
                        "amount": budget.amount,
                    },
                    ensure_ascii=False,
                )
            )

        self._atomic_replace(
            self.budgets_file,
            lines,
        )