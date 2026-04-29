"""
parsed JSON (ResumeData / CurriculumData) → Neo4j 그래프 변환

노드:    Instructor, Skill, Organization, Certification, School, Course
관계:    HAS_SKILL, WORKED_AT, TAUGHT_AT, HAS_CERT, GRADUATED_FROM, COVERS
"""

import json
import logging
from pathlib import Path
from src.kg.graph_store import GraphStore

logger = logging.getLogger(__name__)


# ── 인덱스/제약 초기화 ────────────────────────────────────────────────────────

def init_constraints(store: GraphStore) -> None:
    constraints = [
        "CREATE CONSTRAINT instructor_name IF NOT EXISTS FOR (n:Instructor) REQUIRE n.name IS UNIQUE",
        "CREATE CONSTRAINT skill_name IF NOT EXISTS FOR (n:Skill) REQUIRE n.name IS UNIQUE",
        "CREATE CONSTRAINT org_name IF NOT EXISTS FOR (n:Organization) REQUIRE n.name IS UNIQUE",
        "CREATE CONSTRAINT school_name IF NOT EXISTS FOR (n:School) REQUIRE n.name IS UNIQUE",
        "CREATE CONSTRAINT cert_name IF NOT EXISTS FOR (n:Certification) REQUIRE n.name IS UNIQUE",
        "CREATE CONSTRAINT course_name IF NOT EXISTS FOR (n:Course) REQUIRE n.name IS UNIQUE",
    ]
    for c in constraints:
        store.run(c)
    logger.info("Neo4j 제약조건 초기화 완료")


# ── 이력서 → 그래프 ──────────────────────────────────────────────────────────

def build_resume_graph(data: dict, store: GraphStore) -> None:
    name = data.get("instructor_name", "").strip()
    if not name:
        return

    # Instructor 노드
    store.run(
        """
        MERGE (i:Instructor {name: $name})
        SET i.phone   = $phone,
            i.email   = $email,
            i.summary = $summary
        """,
        name=name,
        phone=data.get("phone") or "",
        email=data.get("email") or "",
        summary=data.get("summary") or "",
    )

    # 전문분야 → Skill
    for skill in data.get("expertise", []):
        skill = skill.strip()
        if not skill:
            continue
        store.run(
            """
            MERGE (s:Skill {name: $skill})
            WITH s
            MATCH (i:Instructor {name: $name})
            MERGE (i)-[:HAS_SKILL]->(s)
            """,
            skill=skill, name=name,
        )

    # 경력 → Organization (WORKED_AT)
    for career in data.get("career", []):
        org = (career.get("organization") or "").strip()
        if not org:
            continue
        store.run(
            """
            MERGE (o:Organization {name: $org})
            WITH o
            MATCH (i:Instructor {name: $name})
            MERGE (i)-[r:WORKED_AT {org: $org}]->(o)
            SET r.position = $position,
                r.period   = $period
            """,
            org=org, name=name,
            position=career.get("position") or "",
            period=career.get("period") or "",
        )

    # 강의이력 → Organization (TAUGHT_AT)
    for th in data.get("teaching_history", []):
        org = (th.get("organization") or "").strip()
        if not org:
            continue
        store.run(
            """
            MERGE (o:Organization {name: $org})
            WITH o
            MATCH (i:Instructor {name: $name})
            MERGE (i)-[r:TAUGHT_AT {org: $org, course: $course}]->(o)
            SET r.period = $period,
                r.hours  = $hours
            """,
            org=org, name=name,
            course=th.get("course_name") or "",
            period=th.get("period") or "",
            hours=th.get("hours") or "",
        )

    # 자격증 → Certification
    for cert in data.get("certifications", []):
        cert_name = (cert.get("name") or "").strip()
        if not cert_name:
            continue
        store.run(
            """
            MERGE (c:Certification {name: $cert_name})
            SET c.issuer = $issuer
            WITH c
            MATCH (i:Instructor {name: $name})
            MERGE (i)-[r:HAS_CERT {cert: $cert_name}]->(c)
            SET r.date = $date
            """,
            cert_name=cert_name, name=name,
            issuer=cert.get("issuer") or "",
            date=cert.get("date") or "",
        )

    # 학력 → School
    for edu in data.get("education", []):
        school = (edu.get("school") or "").strip()
        if not school:
            continue
        store.run(
            """
            MERGE (s:School {name: $school})
            WITH s
            MATCH (i:Instructor {name: $name})
            MERGE (i)-[r:GRADUATED_FROM {school: $school}]->(s)
            SET r.major = $major,
                r.degree = $degree,
                r.year   = $year
            """,
            school=school, name=name,
            major=edu.get("major") or "",
            degree=edu.get("degree") or "",
            year=edu.get("graduation_year") or "",
        )

    logger.info(f"  ✓ {name} 그래프 저장 완료")


# ── 커리큘럼 → 그래프 ────────────────────────────────────────────────────────

def build_curriculum_graph(data: dict, store: GraphStore) -> None:
    course_name = data.get("course_name", "").strip()
    if not course_name:
        return

    store.run(
        """
        MERGE (c:Course {name: $name})
        SET c.level       = $level,
            c.total_hours = $total_hours,
            c.domain      = $domain,
            c.objectives  = $objectives
        """,
        name=course_name,
        level=data.get("level") or "",
        total_hours=data.get("total_hours") or 0,
        domain=", ".join(data.get("domain", [])),
        objectives=data.get("objectives") or "",
    )

    for skill in data.get("skills_covered", []):
        skill = skill.strip()
        if not skill:
            continue
        store.run(
            """
            MERGE (s:Skill {name: $skill})
            WITH s
            MATCH (c:Course {name: $name})
            MERGE (c)-[:COVERS]->(s)
            """,
            skill=skill, name=course_name,
        )

    logger.info(f"  ✓ [{course_name}] 커리큘럼 그래프 저장 완료")


# ── 로컬 파일 일괄 처리 ──────────────────────────────────────────────────────

def build_from_local(doc_type: str, store: GraphStore) -> None:
    base = Path("data/parsed") / doc_type / "done"
    files = list(base.glob("*.json"))
    if not files:
        logger.warning(f"{base} 에 JSON 파일이 없습니다.")
        return

    logger.info(f"{doc_type} JSON {len(files)}개 처리 시작")
    ok, fail = 0, 0
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if doc_type == "resume":
                build_resume_graph(data, store)
            elif doc_type == "curriculum":
                build_curriculum_graph(data, store)
            ok += 1
        except Exception as e:
            logger.error(f"  ✗ {f.name}: {e}")
            fail += 1

    logger.info(f"{doc_type} 완료: 성공 {ok}개 / 실패 {fail}개")


# ── GCS 파일 일괄 처리 ───────────────────────────────────────────────────────

def build_from_gcs(doc_type: str, gcs_bucket: str, store: GraphStore) -> None:
    from google.cloud import storage

    client = storage.Client()
    bucket = client.bucket(gcs_bucket)
    prefix = f"parsed/{doc_type}/done/"
    blobs = [b for b in bucket.list_blobs(prefix=prefix) if b.name.endswith(".json")]

    if not blobs:
        logger.warning(f"gs://{gcs_bucket}/{prefix} 에 JSON 파일이 없습니다.")
        return

    logger.info(f"GCS {doc_type} JSON {len(blobs)}개 처리 시작")
    ok, fail = 0, 0
    for blob in blobs:
        try:
            data = json.loads(blob.download_as_text(encoding="utf-8"))
            if doc_type == "resume":
                build_resume_graph(data, store)
            elif doc_type == "curriculum":
                build_curriculum_graph(data, store)
            ok += 1
        except Exception as e:
            logger.error(f"  ✗ {blob.name}: {e}")
            fail += 1

    logger.info(f"{doc_type} GCS 완료: 성공 {ok}개 / 실패 {fail}개")
