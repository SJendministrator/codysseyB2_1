import logging
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


# 함수 실행 중 발생한 예외를 처리하고 사용자에게 전달할 수 있는 오류로 변환한다.
def handle_errors(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except ValueError:
            raise
        except FileNotFoundError:
            raise RuntimeError(
                "필요한 파일을 찾을 수 없습니다. 저장 경로를 확인하세요."
            )
        except OSError:
            raise RuntimeError(
                "파일 처리 중 오류가 발생했습니다. 파일 상태와 권한을 확인하세요."
            )

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