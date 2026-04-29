"""
Knowledge Graph 빌드 실행 스크립트

로컬 모드:
  python src/kg/build_graph_exe.py --doc_type resume
  python src/kg/build_graph_exe.py --doc_type curriculum

GCS 모드:
  python src/kg/build_graph_exe.py --doc_type resume --gcs_bucket aicore-chatbot-public
  python src/kg/build_graph_exe.py --doc_type curriculum --gcs_bucket aicore-chatbot-public

전체:
  python src/kg/build_graph_exe.py --doc_type all --gcs_bucket aicore-chatbot-public
"""

import argparse
import logging
from dotenv import load_dotenv

load_dotenv(override=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from src.kg.graph_store import GraphStore
from src.kg.graph_builder import init_constraints, build_from_local, build_from_gcs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--doc_type", required=True, choices=["resume", "curriculum", "all"])
    parser.add_argument("--gcs_bucket", default=None, help="GCS 버킷명. 미지정 시 로컬 data/parsed/ 사용")
    args = parser.parse_args()

    doc_types = ["resume", "curriculum"] if args.doc_type == "all" else [args.doc_type]

    with GraphStore() as store:
        if not store.verify():
            print("Neo4j 연결 실패. NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD 환경변수를 확인하세요.")
            return

        init_constraints(store)

        for dt in doc_types:
            if args.gcs_bucket:
                build_from_gcs(dt, args.gcs_bucket, store)
            else:
                build_from_local(dt, store)


if __name__ == "__main__":
    main()
