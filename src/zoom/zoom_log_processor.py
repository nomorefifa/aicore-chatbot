"""
줌 출석 로그 CSV 처리 모듈

기능:
    - 줌 로그 CSV 파일 파싱 (줌 특유의 2-섹션 구조 처리)
    - 같은 학생이지만 이름이 다르게 찍힌 행 자동 병합
      ex) '당감초 안한비 (안 한비)' + '당감초 안한비 (iPhone)' → '당감초 안한비'
    - 학생별 총 참석 시간(분) 합산
    - 학생별 첫 입장시간 / 최종 퇴실시간 (원시 로그형 CSV만 가능, 집계형은 '-')
    - 미팅 메타데이터 (주제, 시작 시간, 종료 시간) 포함

병합 규칙:
    - 이름에 ' (' (공백+괄호)가 있으면 그 앞까지를 기준 이름으로 사용
    - 괄호가 없으면 이름 전체를 기준 이름으로 사용
    - 기준 이름이 같은 행끼리 시간 합산 / 입장시간은 min / 퇴실시간은 max

출력 컬럼:
    주제 | 시작 시간 | 종료 시간 | 학생이름 | 총 시간(분) | 첫 입장시간 | 최종 퇴실시간

지원 형식:
    - .csv 파일만 지원 (xlsx 불가)
    - 인코딩: utf-8-sig / utf-8 / euc-kr / cp949 자동 감지
    - 한국어/영어 컬럼명 모두 지원
    - 줌 CSV 두 가지 형식 지원:
        집계형:    이름, 이메일, 총 기간(분), 게스트
        원시로그형: 이름, 이메일, 참가 시간, 나간 시간, 기간(분), 게스트, 대기실에서
"""

import io
import json
import os
import re

import pandas as pd


def _extract_base_name(name: str) -> str:
    """
    괄호 패턴 제거로 기준 이름 추출.
    '당감초 안한비 (iPhone)' → '당감초 안한비'   # 뒤 괄호
    '(천안용소초)이은미'     → '이은미'           # 앞 괄호 (학교정보가 괄호 안에)
    '분포초_신은서'          → '분포초_신은서'
    """
    # 앞 괄호 패턴: (기관명)이름 형태
    leading = re.match(r"^\(.*?\)\s*", name)
    if leading:
        return name[leading.end():].strip()
    # 뒤 괄호 패턴: 이름 (부가정보) 형태
    match = re.search(r"\s+\(", name)
    if match:
        return name[: match.start()].strip()
    return name.strip()


def _normalize_name(name: str) -> str:
    """
    규칙 기반 이름 정규화.
    1. 연속 공백 정리
    2. 학교 약칭 확장: 초 → 초등학교 (단, 이미 초등학교인 경우 제외)
    3. 구분자 통일: 공백 / 하이픈 → 언더스코어
    4. 연속 언더스코어 정리
    """
    # 0. 보이지 않는 특수문자 제거 (소프트 하이픈, 영폭 공백 등)
    name = re.sub(r"[\u00ad\u200b-\u200f\u2028\u2029\ufeff]", "", name)
    # 1. 연속 공백 → 단일 공백
    name = re.sub(r" +", " ", name).strip()
    # 2. 약칭 확장: '초' 뒤에 '등'이 없는 경우 → '초등학교'
    name = re.sub(r"초(?!등)", "초등학교", name)
    # 3. 구분자 통일: 공백, 하이픈 → 언더스코어
    name = re.sub(r"[-\s]", "_", name)
    # 4. 연속 언더스코어 → 단일 언더스코어
    name = re.sub(r"_+", "_", name)
    return name.strip("_")


def _gemini_group_names(names: list[str]) -> dict[str, str]:
    """
    Gemini API를 사용해 같은 사람으로 보이는 이름들을 그룹화.
    반환값: {원본이름: 대표이름} 매핑 딕셔너리

    처리 예시:
        '도하초 박상욱', '도하초등학교 박상욱' → 둘 다 '도하초등학교 박상욱'으로 통일
        '안서초_이강민', '안서초-이강민', '안서초등학교_이강민' → '안서초등학교_이강민'으로 통일

    핵심 원칙: 사람 이름(성+이름)이 동일한 경우에만 병합. 사람 이름이 다르면 절대 병합 안 함.
    """
    try:
        from google import genai as google_genai
        client = google_genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

        names_str = "\n".join(f"- {n}" for n in names)
        prompt = f"""아래는 줌 화상회의 참석자 이름 목록입니다. 형식은 보통 "학교명_사람이름" 또는 "학교명 사람이름"입니다.

[병합 규칙 - 아래 조건을 모두 충족해야만 같은 사람으로 판단]
1. 사람 이름(성+이름)이 완전히 동일해야 합니다. 사람 이름이 조금이라도 다르면 다른 사람입니다.
2. 학교/기관명 약칭(도하초)과 전체명(도하초등학교)은 같은 학교로 봅니다.
3. 구분자 '_', '-', 공백은 같은 것으로 봅니다.
4. 학교/기관명에 한 글자 오타가 있어도(예: 나사렛새꿈학교 ↔ 나사렛새꿈힉교) 사람 이름이 동일하면 같은 사람으로 판단합니다.
5. 확실하지 않으면 병합하지 말고 별도 그룹으로 유지하세요.

[병합 예시]
- "도하초 박상욱"과 "도하초등학교 박상욱" → 사람이름 동일(박상욱) → 병합 O
- "안서초_이강민"과 "안서초등학교-이강민" → 사람이름 동일(이강민) → 병합 O
- "나사렛새꿈학교 송경자"와 "나사렛새꿈힉교 송경자" → 기관명 오타, 사람이름 동일(송경자) → 병합 O
- "천안청수초 배은주"와 "천안청수초 류병선" → 사람이름 다름 → 병합 X

참석자 이름 목록:
{names_str}

반드시 아래 JSON 형식으로만 답하세요. 설명 없이 JSON만 출력하세요.
대표이름은 반드시 포함이름 목록 중 하나를 그대로 선택하세요 (새로 만들지 마세요).
병합 대상이 없는 이름도 반드시 포함시키세요(포함이름에 자기 자신만 넣으면 됩니다):
{{"그룹": [{{"대표이름": "포함이름중하나", "포함이름": ["원본이름A", "원본이름B"]}}, ...]}}"""

        from google.genai import types as genai_types

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=0.0,
                thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
            ),
        )
        text = response.text.strip()

        # JSON 블록 추출
        if "```" in text:
            text = re.sub(r"```(?:json)?", "", text).replace("```", "").strip()

        data = json.loads(text)
        name_map = {}
        for group in data.get("그룹", []):
            # 그룹 내 가장 긴 이름을 대표로, 없으면 Gemini가 준 대표이름 사용
            candidates = group.get("포함이름", [])
            rep_raw = max(candidates, key=len) if candidates else group["대표이름"]
            rep = _normalize_name(rep_raw)
            for n in candidates:
                name_map[n] = rep
        return name_map

    except Exception:
        # Gemini 실패 시 원본 이름 그대로 사용
        return {n: n for n in names}


def _extract_meeting_meta(lines: list[str]) -> dict:
    """
    CSV 상단 미팅 정보 섹션에서 주제, 시작 시간, 종료 시간 추출.

    줌 CSV 상단 구조:
        1행: 주제, ID, 호스트, 기간(분), 시작 시간, 종료 시간, 참가자  ← 헤더
        2행: 실제 값
    """
    meta = {"주제": "-", "시작 시간": "-", "종료 시간": "-"}
    try:
        header_line = lines[0]
        value_line = lines[1]
        header_df = pd.read_csv(io.StringIO(header_line + "\n" + value_line))
        for col in header_df.columns:
            col_lower = col.lower()
            val = str(header_df[col].iloc[0]).strip()
            if "주제" in col or "topic" in col_lower:
                meta["주제"] = val
            elif ("시작" in col and "시간" in col) or "start" in col_lower:
                meta["시작 시간"] = val
            elif ("종료" in col and "시간" in col) or "end" in col_lower:
                meta["종료 시간"] = val
    except Exception:
        pass
    return meta


def process_zoom_log(file_bytes: bytes) -> tuple[pd.DataFrame, bytes]:
    """
    줌 로그 CSV 바이트를 받아 학생별 집계 DataFrame과 CSV 바이트 반환.

    Returns:
        (result_df, csv_bytes)
        - result_df: 주제|시작 시간|종료 시간|학생이름|총 시간(분)|첫 입장시간|최종 퇴실시간
        - csv_bytes: 다운로드용 UTF-8 BOM CSV 바이트
    """
    # 인코딩 자동 감지
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

    # 미팅 메타데이터 추출 (상단 섹션)
    meta = _extract_meeting_meta(lines)

    # 참가자 섹션 시작 위치 탐색 (한국어: "이름" / 영어: "Name"으로 시작하는 행)
    participant_header_idx = None
    for i, line in enumerate(lines):
        if line.startswith("이름") or line.lower().startswith("name"):
            participant_header_idx = i
            break

    if participant_header_idx is None:
        raise ValueError("참가자 데이터를 찾을 수 없습니다. 줌 로그 CSV 형식인지 확인하세요.")

    # 참가자 섹션 파싱
    participant_csv = "\n".join(lines[participant_header_idx:])
    df = pd.read_csv(io.StringIO(participant_csv))

    # 컬럼명 정규화 (한국어/영어 모두 지원)
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
        elif ("참가" in col and "시간" in col) or "join time" in col_lower:
            col_map[col] = "참가 시간"
        elif ("나간" in col and "시간" in col) or "leave time" in col_lower:
            col_map[col] = "나간 시간"
        elif "게스트" in col or "guest" in col_lower:
            col_map[col] = "게스트"
        elif "이메일" in col or "email" in col_lower:
            col_map[col] = "이메일"
    df = df.rename(columns=col_map)

    # 필수 컬럼 확인
    if "이름" not in df.columns or "시간(분)" not in df.columns:
        raise ValueError(f"필수 컬럼(이름, 시간)을 찾을 수 없습니다. 컬럼 목록: {df.columns.tolist()}")

    # 유효한 참가자 행만 필터 (이름/시간이 있는 행)
    df = df[df["이름"].notna() & df["시간(분)"].notna()].copy()
    df["시간(분)"] = pd.to_numeric(df["시간(분)"], errors="coerce")
    df = df[df["시간(분)"].notna()].copy()

    # 1단계: 괄호 제거로 기준 이름 추출 (규칙 기반)
    df["학생이름"] = df["이름"].apply(_extract_base_name)

    # 2단계: Gemini로 약칭/구분자 차이 등 추가 병합
    unique_names = df["학생이름"].unique().tolist()
    name_map = _gemini_group_names(unique_names)
    df["학생이름"] = df["학생이름"].map(name_map).fillna(df["학생이름"])

    # 총 시간 합산
    time_agg = (
        df.groupby("학생이름", sort=False)["시간(분)"]
        .sum()
        .astype(int)
        .reset_index()
        .rename(columns={"시간(분)": "총 시간(분)"})
    )

    # 첫 입장시간 / 최종 퇴실시간
    # 원시 로그형(참가 시간 + 나간 시간 컬럼 있음): min/max 계산
    # 집계형(해당 컬럼 없음): '-' 표시
    has_times = "참가 시간" in df.columns and "나간 시간" in df.columns
    if has_times:
        df["참가 시간"] = pd.to_datetime(df["참가 시간"], errors="coerce")
        df["나간 시간"] = pd.to_datetime(df["나간 시간"], errors="coerce")
        time_range = (
            df.groupby("학생이름", sort=False)
            .agg(첫_입장=("참가 시간", "min"), 최종_퇴실=("나간 시간", "max"))
            .reset_index()
        )
        time_range["첫 입장시간"] = time_range["첫_입장"].dt.strftime("%Y-%m-%d %H:%M")
        time_range["최종 퇴실시간"] = time_range["최종_퇴실"].dt.strftime("%Y-%m-%d %H:%M")
        time_range = time_range[["학생이름", "첫 입장시간", "최종 퇴실시간"]]
        result = time_agg.merge(time_range, on="학생이름", how="left")
    else:
        result = time_agg.copy()
        result["첫 입장시간"] = "-"
        result["최종 퇴실시간"] = "-"

    # 총 시간 기준 내림차순 정렬
    result = result.sort_values("총 시간(분)", ascending=False).reset_index(drop=True)

    # 미팅 메타데이터 컬럼 앞에 삽입
    result.insert(0, "주제", meta["주제"])
    result.insert(1, "시작 시간", meta["시작 시간"])
    result.insert(2, "종료 시간", meta["종료 시간"])

    # CSV 바이트 생성 (Excel 호환 UTF-8 BOM)
    # 구조:
    #   주제,{값}
    #   시작 시간,{값}
    #   종료 시간,{값}
    #   (빈 행)
    #   학생이름,총 시간(분),첫 입장시간,최종 퇴실시간
    #   {학생 데이터 rows...}
    student_cols = ["학생이름", "총 시간(분)", "첫 입장시간", "최종 퇴실시간"]
    lines_out = [
        f"주제,{meta['주제']}",
        f"시작 시간,{meta['시작 시간']}",
        f"종료 시간,{meta['종료 시간']}",
        "",
        ",".join(student_cols),
    ]
    for _, row in result.iterrows():
        lines_out.append(
            f"{row['학생이름']},{row['총 시간(분)']},{row['첫 입장시간']},{row['최종 퇴실시간']}"
        )

    csv_str = "\n".join(lines_out)
    csv_bytes = ("\ufeff" + csv_str).encode("utf-8")  # UTF-8 BOM

    return result[student_cols], csv_bytes
