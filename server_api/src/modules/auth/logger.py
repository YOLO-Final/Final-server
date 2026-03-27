"""인증 모듈 전용 콘솔 로거.

로그인 성공/실패, Face ID 등록/삭제, 로그아웃 같은 인증 이벤트를
docker logs에서 빠르게 구분할 수 있도록 색상을 입힌다.
"""

import logging
 
# ANSI 색상 코드: 콘솔 출력 시 상태를 빠르게 구분하기 위한 색상 값
GREEN = "\033[92m"  # 성공 (로그인 성공, 등록)
RED = "\033[91m"    # 실패/경고 (로그인 실패, 삭제)
RESET = "\033[0m"   # 색상 초기화

class ColorConsoleHandler(logging.StreamHandler):
    """INFO는 초록색, 그 외(WARNING/ERROR)는 빨간색으로 출력한다."""
    def emit(self, record):
        # 같은 포맷 안에서도 성공/실패를 눈에 띄게 구분하기 위한 처리
        color = GREEN if record.levelno == logging.INFO else RED
        record.msg = f"{color}{record.msg}{RESET}"
        super().emit(record)

# 인증 모듈 전용 로거
# 이름을 고정해 두면 service/router 어디서 호출하더라도 같은 채널로 모인다.
auth_logger = logging.getLogger("auth")
auth_logger.setLevel(logging.INFO)
 
# 로그 출력 형식: [시간] 메시지
formatter = logging.Formatter(
    "[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# 콘솔 핸들러 등록
# 별도 파일 저장 없이 docker logs에서 바로 추적하는 전제다.
console_handler = ColorConsoleHandler()
console_handler.setFormatter(formatter)

auth_logger.addHandler(console_handler)
