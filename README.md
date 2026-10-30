# APPLE

Apple II 에뮬레이션, 하드웨어 연동, 한글/한자 시스템 및 유틸리티 개발 저장소입니다.

---

## 프로젝트 목록

### 1. [apple2_hangul](./apple2_hangul)
Apple II와 PC(Super Serial Card, Slot 2) 통신을 이용한 **한글 11,172자 및 漢字(한자) 통합 입출력 시스템**입니다.
* **Applesoft BASIC `&` 연동**: `10 & "\K한글과 漢字\N"` 형태로 BASIC 코드 내에서 한글/한자를 직접 출력
* **콘솔 직접 입력**: AppleWin에서 `Ctrl+K` 입력 시 PC 콘솔에서 한글/한자를 타이핑하거나 붙여넣어 Apple II로 즉시 전달
* **동적 폰트 래스터라이징**: PC에서 FreeType / TrueType(Gulim, NotoSerifCJK 등) 폰트를 14x16 비트맵으로 래스터라이즈하여 Apple II HGR(280x192) 화면에 스트리밍 전송
* **이체자 자동 정규화**: 웹/위키 복사 텍스트의 신자체(예: `隠`)를 정체자(`隱`)로 자동 매핑 지원
* **폴더 구조**:
  * `driver/`: 6502 어셈블리 드라이버 소스 (`hangul_driver.s`, `HANGUL.BIN` 등)
  * `disk/`: 부팅 가능한 DOS 3.3 디스크 이미지 (`hangul.dsk`)
  * `server/`: Python 폰트 래스터라이저 및 터미널 서버 (`hangul_server.py`)
  * `tools/`: DOS 3.3 디스크 이미지 분석 및 BASIC 인젝션 도구 (`inject_basic.py`)

---

## 향후 추가 예정 프로젝트
* 다양한 Apple II 관련 하드웨어/소프트웨어 연동 소스 및 유틸리티가 독립적인 하위 폴더로 추가될 예정입니다.
