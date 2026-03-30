"""
한컴오피스 COM 자동화로 .hwp → .docx 일괄 변환
한컴오피스가 설치되어 있어야 동작합니다.
실행: python test/hwp_to_docx.py
"""

import os
import win32com.client as win32
from pathlib import Path

# 변환할 .hwp 파일이 있는 폴더
INPUT_DIR = r"C:\Users\cccjj\aicore\agent-data\강사서류(이력서)정리"

# 변환된 .docx 저장 폴더
OUTPUT_DIR = r"C:\Users\cccjj\aicore\agent-dev\data\raw"

Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

hwp = win32.gencache.EnsureDispatch("HWPFrame.HwpObject")
hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")

hwp_files = [f for f in os.listdir(INPUT_DIR) if f.endswith(".hwp")]
print(f"변환 대상: {len(hwp_files)}개 파일")

for filename in hwp_files:
    hwp_path = os.path.join(INPUT_DIR, filename)
    docx_name = filename.replace(".hwp", ".docx")
    docx_path = os.path.join(OUTPUT_DIR, docx_name)

    try:
        hwp.Open(hwp_path, "HWP", "forceopen:true")

        # HWP COM은 HSet.SetItem으로 파라미터 설정 후 저장
        param = hwp.HParameterSet.HFileSaveAs
        hwp.HAction.GetDefault("FileSaveAs", param.HSet)
        param.HSet.SetItem("FileName", docx_path)
        param.HSet.SetItem("Format", "MSWordXML")
        param.HSet.SetItem("Protection", 0)
        hwp.HAction.Execute("FileSaveAs", param.HSet)

        hwp.Clear(1)

        if os.path.exists(docx_path):
            print(f"완료: {filename} → {docx_name}")
        else:
            print(f"저장 실패 (파일 없음): {docx_path}")
    except Exception as e:
        print(f"실패: {filename} → {e}")

hwp.Quit()
print("전체 변환 완료")
