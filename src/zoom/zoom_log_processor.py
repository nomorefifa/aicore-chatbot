"""
줌 출석 로그 CSV 처리 모듈

기능:
    - 줌 로그 CSV 파일 파싱 (줌 특유의 2-섹션 구조 처리)
    - 같은 학생이지만 이름이 다르게 찍힌 행 자동 병합
      ex) '당감초 안한비 (안 한비)' + '당감초 안한비 (iPhone)' → '당감초 안한비'
      ex) '환서초등학교_박정희 (Samsung SM-S911N)' + '환서초등학교_박정희' -> '환서초등학교_박정희'
    - 학생별 총 참석 시간(분) 합산
    - 결과를 CSV 바이트로 반환 (Gradio 다운로드용)

병합 규칙:
    - 이름에 ' (' (공백+괄호)가 있으면 그 앞까지를 기준 이름으로 사용
    - 괄호가 없으면 이름 전체를 기준 이름으로 사용
    - 기준 이름이 같은 행끼리 시간 합산
"""

import io
import re

import pandas as pd


def _extract_base_name(name: str) -> str:
    """
    ' (' 패턴을 기준으로 기준 이름 추출.
    '당감초 안한비 (iPhone)' → '당감초 안한비'
    '분포초_신은서' → '분포초_신은서'
    """
    match = re.search(r"\s+\(", name)
    if match:
        return name[: match.start()].strip()
    return name.strip()


def process_zoom_log(file_bytes: bytes) -> tuple[pd.DataFrame, bytes]:
    """
    줌 로그 CSV 바이트를 받아 학생별 총 참석 시간 DataFrame과 CSV 바이트 반환.

    줌 CSV 구조:
        1행: 미팅 헤더 (주제, ID, 호스트, ...)
        2행: 미팅 정보
        3행: 빈 행
        4행: 참가자 헤더 (이름(원래 이름), 이메일, 총 기간(분), 게스트)
        5행~: 참가자 데이터

    Returns:
        (result_df, csv_bytes)
        - result_df: 학생이름 | 총 시간(분) DataFrame
        - csv_bytes: 다운로드용 UTF-8 BOM CSV 바이트
    """
    # 인코딩 자동 감지 (utf-8-sig → utf-8 순서)
    raw = None
    for enc in ("utf-8-sig", "utf-8", "euc-kr", "cp949"):
        try:
            raw = file_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue

    if raw is None:
        raise ValueError("CSV 파일 인코딩을 인식할 수 없습니다.")

    lines = raw.splitlines()

    # 참가자 섹션 시작 위치 탐색 (한국어: "이름"으로 시작 / 영어: "Name"으로 시작)
    participant_header_idx = None
    for i, line in enumerate(lines):
        if line.startswith("이름") or line.lower().startswith("name"):
            participant_header_idx = i
            break

    if participant_header_idx is None:
        raise ValueError("참가자 데이터를 찾을 수 없습니다. 줌 로그 CSV 형식인지 확인하세요.")

    participant_csv = "\n".join(lines[participant_header_idx:])
    df = pd.read_csv(io.StringIO(participant_csv))

    # 컬럼명 정규화 (한국어/영어 줌 CSV 모두 지원)
    # 영어 예시: Name (Original Name), Email, Duration (Minutes), Total Duration (Minutes), Guest
    col_map = {}
    for col in df.columns:
        col_lower = col.lower()
        if "이름" in col or "name" in col_lower:
            col_map[col] = "이름"
        elif (
            ("기간" in col or "duration" in col_lower)
            and "참가" not in col
            and "나간" not in col
            and "join" not in col_lower
            and "leave" not in col_lower
        ):
            col_map[col] = "시간(분)"
        elif "게스트" in col or "guest" in col_lower:
            col_map[col] = "게스트"
        elif "이메일" in col or "email" in col_lower:
            col_map[col] = "이메일"
    df = df.rename(columns=col_map)

    # 필요한 컬럼 존재 확인
    if "이름" not in df.columns or "시간(분)" not in df.columns:
        raise ValueError(f"필수 컬럼(이름, 시간)을 찾을 수 없습니다. 컬럼 목록: {df.columns.tolist()}")

    # 유효한 참가자 행만 필터 (이름/시간이 있는 행)
    df = df[df["이름"].notna() & df["시간(분)"].notna()].copy()
    df["시간(분)"] = pd.to_numeric(df["시간(분)"], errors="coerce")
    df = df[df["시간(분)"].notna()].copy()

    # 호스트/운영자 제외 (이메일이 있으면서 게스트=아니요인 경우)
    if "이메일" in df.columns and "게스트" in df.columns:
        is_operator = df["이메일"].notna() & (df["게스트"] == "아니요")
        df = df[~is_operator].copy()

    # 기준 이름 추출 및 그룹 합산
    df["학생이름"] = df["이름"].apply(_extract_base_name)
    result = (
        df.groupby("학생이름", sort=False)["시간(분)"]
        .sum()
        .astype(int)
        .reset_index()
        .rename(columns={"시간(분)": "총 시간(분)"})
        .sort_values("총 시간(분)", ascending=False)
        .reset_index(drop=True)
    )

    # CSV 바이트 생성 (Excel 호환 UTF-8 BOM)
    buf = io.BytesIO()
    result.to_csv(buf, index=False, encoding="utf-8-sig")
    csv_bytes = buf.getvalue()

    return result, csv_bytes
