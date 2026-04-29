"""
Neo4j Knowledge Graph 기반 강사 검색 도구

Weaviate(벡터 검색)를 보완하는 구조적 관계 기반 검색을 제공합니다.
"""

from langchain_core.tools import tool
from src.kg.graph_store import GraphStore


def get_graph_tools() -> list:
    store = GraphStore()

    @tool
    def search_instructors_by_skill(skill: str) -> str:
        """
        특정 기술/전문분야를 보유한 강사 목록을 조회합니다.
        예: 'Python', '데이터분석', 'AI', 'LLM', '클라우드'
        """
        rows = store.run(
            """
            MATCH (i:Instructor)-[:HAS_SKILL]->(s:Skill)
            WHERE toLower(s.name) CONTAINS toLower($skill)
            RETURN i.name AS name, i.email AS email,
                   collect(s.name) AS skills
            ORDER BY i.name
            """,
            skill=skill,
        )
        if not rows:
            return f"'{skill}' 관련 기술을 보유한 강사를 찾지 못했습니다."

        lines = [f"'{skill}' 보유 강사 {len(rows)}명\n"]
        for r in rows:
            skills_str = ", ".join(r["skills"][:5])
            lines.append(f"- {r['name']} | {r['email']} | 전문분야: {skills_str}")
        return "\n".join(lines)

    @tool
    def search_instructors_by_org(organization: str) -> str:
        """
        특정 기관에서 강의하거나 근무한 경력이 있는 강사를 조회합니다.
        예: '삼성', 'LG', 'SK', '대학교', '아이코어'
        """
        rows = store.run(
            """
            MATCH (i:Instructor)-[r:TAUGHT_AT|WORKED_AT]->(o:Organization)
            WHERE toLower(o.name) CONTAINS toLower($org)
            WITH i, collect({
                rel_type: type(r),
                org: o.name,
                period: r.period
            }) AS roles
            RETURN i.name AS name, i.email AS email, roles
            ORDER BY i.name
            """,
            org=organization,
        )
        if not rows:
            return f"'{organization}' 관련 경력/강의 이력이 있는 강사를 찾지 못했습니다."

        lines = [f"'{organization}' 관련 강사 {len(rows)}명\n"]
        for r in rows:
            role_parts = []
            for role in r["roles"]:
                rel = "강의" if role["rel_type"] == "TAUGHT_AT" else "근무"
                role_parts.append(f"{role['org']} ({rel}, {role['period']})")
            lines.append(f"- {r['name']} | {' / '.join(role_parts)}")
        return "\n".join(lines)

    @tool
    def find_instructors_for_course(course_skills: str) -> str:
        """
        커리큘럼에 필요한 기술 키워드로 적합한 강사를 추천합니다.
        쉼표로 구분된 기술 키워드를 입력하세요.
        예: 'Python, 머신러닝, 딥러닝'
        """
        skills = [s.strip() for s in course_skills.split(",") if s.strip()]
        if not skills:
            return "기술 키워드를 입력해주세요."

        rows = store.run(
            """
            UNWIND $skills AS skill
            MATCH (i:Instructor)-[:HAS_SKILL]->(s:Skill)
            WHERE toLower(s.name) CONTAINS toLower(skill)
            WITH i, collect(DISTINCT s.name) AS matched_skills, count(DISTINCT s) AS match_count
            RETURN i.name AS name, i.email AS email,
                   matched_skills, match_count
            ORDER BY match_count DESC
            LIMIT 10
            """,
            skills=skills,
        )
        if not rows:
            return "해당 기술을 보유한 강사를 찾지 못했습니다."

        lines = [f"적합 강사 (매칭 기술 수 기준)\n"]
        for r in rows:
            matched = ", ".join(r["matched_skills"])
            lines.append(f"- {r['name']} | 매칭 기술 {r['match_count']}개: {matched}")
        return "\n".join(lines)

    @tool
    def get_instructor_graph_detail(instructor_name: str) -> str:
        """
        특정 강사의 전체 관계 정보를 그래프에서 조회합니다.
        기술, 경력, 강의이력, 자격증, 학력을 모두 반환합니다.
        """
        rows = store.run(
            """
            MATCH (i:Instructor {name: $name})
            OPTIONAL MATCH (i)-[:HAS_SKILL]->(s:Skill)
            OPTIONAL MATCH (i)-[w:WORKED_AT]->(org_w:Organization)
            OPTIONAL MATCH (i)-[t:TAUGHT_AT]->(org_t:Organization)
            OPTIONAL MATCH (i)-[c:HAS_CERT]->(cert:Certification)
            OPTIONAL MATCH (i)-[e:GRADUATED_FROM]->(school:School)
            RETURN
                i.name AS name, i.phone AS phone, i.email AS email,
                collect(DISTINCT s.name) AS skills,
                collect(DISTINCT {org: org_w.name, position: w.position, period: w.period}) AS careers,
                collect(DISTINCT {org: org_t.name, course: t.course, period: t.period}) AS teachings,
                collect(DISTINCT {name: cert.name, issuer: cert.issuer, date: c.date}) AS certs,
                collect(DISTINCT {school: school.name, major: e.major, degree: e.degree}) AS education
            """,
            name=instructor_name,
        )
        if not rows or not rows[0]["name"]:
            return f"'{instructor_name}' 강사를 그래프에서 찾지 못했습니다."

        r = rows[0]
        lines = [
            f"【{r['name']}】",
            f"연락처: {r['phone']} | 이메일: {r['email']}",
            f"\n전문분야: {', '.join(r['skills']) or '없음'}",
        ]

        careers = [c for c in r["careers"] if c.get("org")]
        if careers:
            lines.append("\n경력:")
            for c in careers:
                lines.append(f"  - {c['org']} | {c['position']} | {c['period']}")

        teachings = [t for t in r["teachings"] if t.get("org")]
        if teachings:
            lines.append("\n강의이력:")
            for t in teachings:
                lines.append(f"  - {t['org']} | {t['course']} | {t['period']}")

        certs = [c for c in r["certs"] if c.get("name")]
        if certs:
            lines.append("\n자격증:")
            for c in certs:
                lines.append(f"  - {c['name']} ({c['issuer']}, {c['date']})")

        edu = [e for e in r["education"] if e.get("school")]
        if edu:
            lines.append("\n학력:")
            for e in edu:
                lines.append(f"  - {e['school']} {e['major']} {e['degree']}")

        return "\n".join(lines)

    @tool
    def get_skill_overlap(instructor_a: str, instructor_b: str) -> str:
        """
        두 강사가 공통으로 보유한 기술과 각자 고유한 기술을 비교합니다.
        팀 강의 구성이나 대체 강사 검토 시 유용합니다.
        """
        rows = store.run(
            """
            MATCH (a:Instructor {name: $a})-[:HAS_SKILL]->(s:Skill)
            MATCH (b:Instructor {name: $b})-[:HAS_SKILL]->(s)
            RETURN collect(DISTINCT s.name) AS common
            """,
            a=instructor_a, b=instructor_b,
        )
        common = rows[0]["common"] if rows else []

        only_a = store.run(
            """
            MATCH (a:Instructor {name: $a})-[:HAS_SKILL]->(s:Skill)
            WHERE NOT (s)<-[:HAS_SKILL]-(:Instructor {name: $b})
            RETURN collect(s.name) AS skills
            """,
            a=instructor_a, b=instructor_b,
        )
        only_b = store.run(
            """
            MATCH (b:Instructor {name: $b})-[:HAS_SKILL]->(s:Skill)
            WHERE NOT (s)<-[:HAS_SKILL]-(:Instructor {name: $a})
            RETURN collect(s.name) AS skills
            """,
            a=instructor_a, b=instructor_b,
        )

        lines = [
            f"공통 기술 ({len(common)}개): {', '.join(common) or '없음'}",
            f"{instructor_a} 고유: {', '.join(only_a[0]['skills']) if only_a else '없음'}",
            f"{instructor_b} 고유: {', '.join(only_b[0]['skills']) if only_b else '없음'}",
        ]
        return "\n".join(lines)

    return [
        search_instructors_by_skill,
        search_instructors_by_org,
        find_instructors_for_course,
        get_instructor_graph_detail,
        get_skill_overlap,
    ]
