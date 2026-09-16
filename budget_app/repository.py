import json
import os
import tempfile
from pathlib import Path
from typing import Iterator

from .models import Budget, Category, Transaction


# JSONL 파일을 저장할 기본 디렉터리를 설정한다.
DEFAULT_DATA_DIR = Path("data")


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

    # JSONL 파일을 한 줄씩 읽어 JSON 데이터로 변환한다.
    def _stream_json(self, file_path: Path) -> Iterator[dict]:
        with file_path.open("r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()

                if not line:
                    continue

                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

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
                "month": budget.month,
                "amount": budget.amount,
            },
        )

    # 지정한 파일의 내용을 임시 파일에 작성한 후 원본 파일과 교체한다.
    def _atomic_replace(self, file_path: Path, lines: list[str]) -> None:
        fd, temp_path = tempfile.mkstemp(
            dir=self.data_dir,
            prefix=f"{file_path.stem}_",
            suffix=".tmp",
            text=True,
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