"""오류 처리 자동 검증 스크립트.

실행:  python3 scripts/check_errors.py      (프로젝트 루트에서)

하는 일
  - 임시 폴더에 테스트용 데이터를 만들고, 오류가 나야 하는 명령을 하나씩 실제로 실행한다.
  - 각 명령마다 아래 3가지를 자동으로 확인해 표로 보여준다.
      1) 종료 코드   : 오류 케이스는 0이 아니어야 하고, 정상 케이스는 0이어야 한다
      2) 스택트레이스: 출력에 'Traceback' 이 없어야 한다
      3) 메시지     : 원인을 알려주는 문구가 들어 있어야 한다
  - 하나라도 실패하면 이 스크립트 자체가 종료 코드 1로 끝난다.
  - 실제 data/ 폴더는 건드리지 않는다 (임시 폴더만 사용 후 삭제).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

# ====================================================================
# [1] 설정 — 프로젝트 위치와 실행 방법
# ====================================================================
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable  # 이 스크립트를 실행한 파이썬으로 그대로 실행


# ====================================================================
# [2] 검증 케이스 정의
# ====================================================================
@dataclass
class Case:
    name: str                 # 표에 보일 설명
    args: list[str]           # budget_app 뒤에 붙일 인자
    expect_ok: bool           # True = 종료 코드 0 기대 / False = 0이 아닌 값 기대
    expect_text: str          # 출력에 들어 있어야 하는 문구
    stdin: str = ""           # 대화형 입력이 필요할 때 넣을 값


def build_cases(data: Path, csv_dir: Path, bad_dir: str) -> list[Case]:
    d = ["--data-dir", str(data)]
    return [
        # --- 정상 동작 (종료 코드 0) ---
        Case("도움말 출력", ["--help"], True, "usage"),
        Case("데이터 없는 달 요약", d + ["summary", "--month", "2026-01"], True, "데이터 없음"),

        # --- 입력값 검증 오류 ---
        Case("날짜 형식 오류 (13월)", d + ["search", "--from", "2026-13-01"], False, "날짜 형식"),
        Case("월 형식 오류", d + ["summary", "--month", "2026-13"], False, "월 형식"),
        Case("음수 금액", d + ["budget", "set", "--month", "2026-09", "--amount", "-500"], False, "0보다 커야"),
        Case("0원 금액", d + ["budget", "set", "--month", "2026-09", "--amount", "0"], False, "0보다 커야"),
        Case("문자 금액", d + ["budget", "set", "--month", "2026-09", "--amount", "만원"], False, "정수"),
        Case("허용되지 않은 type", d + ["search", "--type", "spend"], False, "income 또는 expense"),
        Case("등록 안 된 카테고리", d + ["search", "--category", "없는거"], False, "등록되지 않은 카테고리"),
        Case("검색 기간 역전", d + ["search", "--from", "2026-09-30", "--to", "2026-09-01"], False, "늦습니다"),
        Case("limit 0", d + ["list", "--limit", "0"], False, "0보다 커야"),

        # --- 없는 데이터 처리 ---
        Case("없는 ID 삭제", d + ["delete", "--id", "nope"], False, "찾을 수 없습니다"),
        Case("없는 ID 수정", d + ["update", "--id", "nope", "--amount", "100"], False, "찾을 수 없습니다"),
        Case("없는 카테고리 삭제", d + ["category", "remove", "--name", "없는거"], False, "등록된 카테고리가 아닙니다"),
        Case("사용 중 카테고리 삭제", d + ["category", "remove", "--name", "식비"], False, "사용 중인 카테고리"),

        # --- CSV 가져오기 / 내보내기 ---
        Case("export 조건 없음", d + ["export", "--out", str(csv_dir / "x.csv")], False, "--month 또는 --from/--to"),
        Case("import 파일 없음", d + ["import", "--from", str(csv_dir / "nope.csv")], False, "찾을 수 없습니다"),
        Case("import 필수 컬럼 누락", d + ["import", "--from", str(csv_dir / "no_col.csv")], False, "필수 컬럼"),
        Case("import 잘못된 행", d + ["import", "--from", str(csv_dir / "bad_row.csv")], False, "3번째 행"),

        # --- 파일·환경 오류 (스택트레이스가 나기 쉬운 곳) ---
        Case("쓸 수 없는 data-dir", ["--data-dir", bad_dir, "list"], False, "[오류]"),
        Case("add 중 입력 중단(Ctrl+D)", d + ["add"], False, "취소", stdin=""),
        Case("없는 명령어", d + ["fly"], False, "invalid choice"),
    ]


# ====================================================================
# [3] 테스트 데이터 준비 — 임시 폴더에 거래 1건 + CSV 파일들
# ====================================================================
def prepare(tmp: Path) -> tuple[Path, Path, str]:
    data = tmp / "data"
    csv_dir = tmp / "csv"
    csv_dir.mkdir()

    # '식비' 카테고리를 사용하는 거래 1건 (사용 중 카테고리 삭제 거부 확인용)
    run(["--data-dir", str(data), "add"], stdin="2026-09-01\nexpense\n식비\n1000\n테스트\n\n")

    (csv_dir / "no_col.csv").write_text("date,type,amount\n2026-09-01,expense,1000\n", encoding="utf-8")
    (csv_dir / "bad_row.csv").write_text(
        "date,type,category,amount\n2026-09-01,expense,식비,1000\n2026-09-02,expense,식비,-5\n",
        encoding="utf-8",
    )

    # 파일 아래에 폴더를 만들려고 하면 어느 OS에서든 오류가 난다 → 쓸 수 없는 경로로 사용
    blocker = tmp / "i_am_a_file"
    blocker.write_text("x")
    return data, csv_dir, str(blocker / "sub")


# ====================================================================
# [4] 실행 함수 — 실제 CLI를 별도 프로세스로 실행
# ====================================================================
def run(args: list[str], stdin: str = "") -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, "-m", "budget_app", *args],
        cwd=PROJECT_ROOT,
        input=stdin,
        capture_output=True,
        text=True,
    )


# ====================================================================
# [5] 결과 출력 — 표 + 요약
# ====================================================================
def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="budget_check_"))
    failed = 0
    try:
        data, csv_dir, bad_dir = prepare(tmp)
        cases = build_cases(data, csv_dir, bad_dir)

        print(f"{'결과':<6}{'종료코드':<10}{'기대':<8}{'케이스'}")
        print("-" * 64)

        for case in cases:
            proc = run(case.args, case.stdin)
            output = proc.stdout + proc.stderr

            # --- 5-1. 세 가지 조건을 각각 검사 ---
            code_ok = (proc.returncode == 0) == case.expect_ok
            no_trace = "Traceback" not in output
            text_ok = case.expect_text in output
            passed = code_ok and no_trace and text_ok

            # --- 5-2. 한 줄 출력 (실패하면 이유도 같이) ---
            expect = "0" if case.expect_ok else "≠0"
            mark = "PASS" if passed else "FAIL"
            print(f"{mark:<6}{proc.returncode:<10}{expect:<8}{case.name}")
            if not passed:
                failed += 1
                reasons = []
                if not code_ok:
                    reasons.append("종료 코드가 기대와 다름")
                if not no_trace:
                    reasons.append("스택트레이스 노출")
                if not text_ok:
                    reasons.append(f"'{case.expect_text}' 문구 없음")
                print(f"      └ {', '.join(reasons)}")
                print("        출력: " + output.strip().splitlines()[-1][:80] if output.strip() else "        출력 없음")

        # --- 5-3. 요약 ---
        print("-" * 64)
        print(f"총 {len(cases)}건 중 통과 {len(cases) - failed}건, 실패 {failed}건")
        print("스택트레이스 노출: " + ("없음" if failed == 0 else "실패 항목 확인"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())