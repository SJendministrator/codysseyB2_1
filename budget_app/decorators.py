import logging
import sys
import time
from functools import wraps
from typing import Any, Callable


# 프로그램 실행 기록을 저장할 로그 설정을 구성한다.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


# 함수가 실행될 때 시작과 종료 정보를 로그로 기록한다.
def log_execution(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        logging.info("실행 시작: %s", func.__name__)

        result = func(*args, **kwargs)

        logging.info("실행 완료: %s", func.__name__)

        return result

    return wrapper


# 프로그램 최상위에서 모든 예외를 잡아 스택트레이스 대신 '원인 + 해결 힌트'를 출력하고
# 종료 코드(0이 아닌 값)를 돌려준다. cli.run() 에 적용한다.
def handle_errors(func: Callable[..., int]) -> Callable[..., int]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> int:
        try:
            return func(*args, **kwargs)
        except (KeyboardInterrupt, EOFError):
            print("\n[취소] 입력이 취소되었습니다. 저장된 내용은 없습니다.", file=sys.stderr)
            return 130
        except ValueError as error:
            print(f"[오류] {error}", file=sys.stderr)
            return 1
        except FileNotFoundError as error:
            print(f"[오류] 파일 또는 폴더를 찾을 수 없습니다: {error.filename}", file=sys.stderr)
            print("힌트: --data-dir 경로나 CSV 파일 경로가 맞는지 확인하세요.", file=sys.stderr)
            return 1
        except PermissionError as error:
            print(f"[오류] 파일 접근 권한이 없습니다: {error.filename}", file=sys.stderr)
            print("힌트: 쓰기 가능한 폴더를 --data-dir 로 지정하세요.", file=sys.stderr)
            return 1
        except OSError as error:
            print(f"[오류] 파일 처리 중 문제가 발생했습니다: {error}", file=sys.stderr)
            print("힌트: 디스크 공간, 파일 상태와 권한을 확인하세요.", file=sys.stderr)
            return 1
        except Exception as error:  # 예상하지 못한 오류도 스택트레이스 없이 종료
            print(f"[오류] 예상하지 못한 오류가 발생했습니다: {type(error).__name__}: {error}",
                  file=sys.stderr)
            print("힌트: 저장 파일(data/*.jsonl) 내용이 올바른지 확인하세요.", file=sys.stderr)
            return 1

    return wrapper


# 함수가 실행되는 데 걸린 시간을 측정하고 로그로 기록한다.
def measure_time(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.perf_counter()

        result = func(*args, **kwargs)

        elapsed_time = time.perf_counter() - start_time

        logging.info(
            "실행 시간: %s %.6f초",
            func.__name__,
            elapsed_time,
        )

        return result

    return wrapper