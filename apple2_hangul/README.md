# Apple II + PC SSC 한글 및 漢字(한자) 통합 입출력 시스템

AppleWin의 C++ 소스 코드를 전혀 수정하지 않고, 표준 **Super Serial Card (SSC, Slot 2)** 통신을 통해 PC에서 FreeType / TrueType 폰트를 래스터라이징하여 Apple II 고해상도 그래픽(HGR 280x192) 화면에 **한글 11,172자 및 한자(漢字)**를 출력하고, Applesoft BASIC 프로그램 작성 및 대화형 입력을 완벽하게 지원하는 통합 시스템입니다.

---

## 1. 주요 특징 및 해결된 핵심 원리

1. **Applesoft BASIC `&` (Ampersand) 문을 통한 한글/한자 출력**:
   - Apple II의 기본 40열 TEXT 화면은 하드웨어 문자 생성 롬(ROM)이 영문 전용(7비트 ASCII)이므로 한글 및 한자 글리프를 표시할 수 없습니다.
   - 따라서 모든 한글 및 한자는 고해상도 그래픽(HGR, 280x192) 화면에 14x16 픽셀 트루타입 폰트로 렌더링됩니다.
   - BASIC 프로그램 내에서 `10 & "\K한글과 漢字\N"` 형태로 문장을 작성하고 `RUN`하면 자동으로 HGR 화면으로 전환되어 아름다운 고품질 글꼴로 출력됩니다.

2. **BASIC 작성 중 특수키(`Ctrl+K`)를 통한 콘솔 직접 한글 / 漢字 입력**:
   - AppleWin 에뮬레이터에서 BASIC 코드를 작성하다가 한글이나 한자를 입력해야 할 때 **`Ctrl+K`** 키를 누릅니다.
   - `hangul_server` 콘솔 창에 `한글/漢字 입력 > ` 프롬프트가 나타나며, 콘솔창에서 바로 한글/한자를 타이핑하거나 복사한 긴 한자 텍스트를 붙여넣고 `Enter`를 누르면 Apple II의 현재 입력 행으로 자동 전달됩니다. (GUI 팝업을 원할 경우 `--popup` 옵션 제공)

3. **Caps Lock 및 BASIC 파서 충돌 방지 (Hex 안전 인코딩)**:
   - Apple II 키보드 루틴(`GETLN`) 및 Applesoft 파서(`PARSE`)는 8비트 코드를 BASIC 키워드 토큰($80~$EA)이나 줄바꿈/취소 제어문자($80~$9F)로 오인하여 `?SYNTAX ERROR`를 발생시켰습니다.
   - 본 시스템은 `Ctrl+K` 입력 시 안전한 Hex 기반 인코딩(`\K...\N`)으로 전달하여, 따옴표(`"`) 충돌, 제어문자 오작동, Caps Lock 대소문자 변환 문제 없이 100% 안전하게 저장하고 실행합니다.

4. **대화형 전체화면 터미널 모드**:
   - BASIC 프롬프트 `]`에서 단순 `&` 입력 후 Enter를 치면 전체화면 한글/한자 터미널 모드로 진입합니다.
   - 2벌식 실시간 자소 조합 타이핑(`Ctrl+K` 또는 `` ` `` 키로 한/영 전환)을 지원하며, `ESC` 키로 BASIC으로 복귀합니다.

---

## 2. 구성 파일

- `disk/hangul.dsk`: 부팅 가능한 통합 DOS 3.3 디스크 이미지 (`HANGUL` 드라이버 및 `DEMO` 프로그램 탑재).
- `driver/hangul_driver.s`: 단일 독립 6502 어셈블리 소스 (`xa hangul_driver.s -o HANGUL.BIN`으로 빌드 가능).
- `driver/HANGUL.BIN`: Apple II 상주 바이너리 드라이버 ($4000).
- `server/hangul_server.py`: PC 측 통신/폰트 서버 소스 코드.
- `server/requirements.txt`: Python 의존 라이브러리 목록 (`pip install -r requirements.txt`).

---

## 3. 사용 방법

### 1단계: PC 서버 실행
파이썬 패키지를 설치한 후 서버를 실행합니다:
```bash
pip install -r server/requirements.txt
python server/hangul_server.py
```

### 2단계: AppleWin 실행 및 디스크 부팅
1. `Release\AppleWin.exe`를 실행합니다. (Slot 2 SSC는 TCP 포트 1977로 자동 구성되어 있습니다.)
2. 드라이브 1에 `hangul.dsk`를 넣고 부팅(F2)합니다.
3. 부팅 안내 화면과 함께 `]` 프롬프트가 나타납니다.

---

## 4. 검증된 동작 테스트

### 테스트 A: 한글 및 漢字(한자) 내장 데모 실행
Apple II BASIC 프롬프트에서 다음을 입력합니다:
```basic
RUN DEMO
```
- 화면이 즉시 HGR 고해상도 그래픽 모드로 전환되며:
  1. `안녕하세요 Apple II!`
  2. `天地玄黃 宇宙洪荒`
  3. `한글과 漢字 출력 성공!`
  4. `1977 - 2026 RETRO COMPUTING`
  문장이 고품질 글리프로 깨끗하게 출력됩니다.

### 테스트 B: 사용자가 직접 BASIC 프로그램 입력
1. AppleWin에서 다음과 같이 타이핑합니다:
   ```basic
   10 & "
   ```
2. 여기서 **`Ctrl+K`** 키를 누릅니다.
3. PC 팝업창이 나타납니다. 한글이나 한자를 입력하고 Enter를 누릅니다:
   - 예: `안녕 漢字`
4. 따옴표와 Enter를 입력하여 행을 완성합니다:
   ```basic
   "
   ```
5. `RUN`을 입력하여 실행하면 HGR 화면에 한글과 한자가 완벽하게 출력됩니다.

### 테스트 C: 대화형 터미널 모드
BASIC 프롬프트 `]`에서 `&`만 입력하고 Enter를 누르면 전체화면 한글 그래픽 콘솔 모드로 진입합니다:
- `Ctrl+K` 또는 `` ` `` 키: 한글 2벌식 / 영문 전환
- `ESC` 키: BASIC 프롬프트로 복귀
