# Apple II Unicode Bridge (`apple2-unicode-bridge`)

[English Documentation](README.md) | [한국어 문서](README_HANGUL.md)

AppleWin 또는 실물 Apple II의 C++ 소스 코드 및 롬(ROM)을 전혀 수정하지 않고, 표준 **Super Serial Card (SSC, Slot 2)** 통신을 통해 PC에서 FreeType / TrueType 폰트를 래스터라이징하여 Apple II 고해상도 그래픽(HGR 280x192) 화면에 **한글 11,172자, 漢字(한자), CJK 및 전 세계 유니코드 다국어 문자**를 출력하고, Applesoft BASIC 프로그램 작성 및 대화형 입력을 지원하는 유니코드 폰트 브리지 시스템입니다.

---

## 📺 실제 동작 화면: 祭亡妹歌 (제망매가) 한자 및 한글 혼용 출력

신라 향가 월명사의 *제망매가(祭亡妹歌)* 원문(한자/향찰)과 한글 풀이를 Apple II 고해상도 그래픽(HGR 280×192) 화면에 동적으로 렌더링한 실제 화면입니다:

![Apple II 제망매가 실행 화면](docs/images/jemangmaega_demo.png)

### Applesoft BASIC 프로그램 예제

Applesoft BASIC 프롬프트에서 `&` 명령어를 사용하여 한글과 한자를 손쉽게 출력할 수 있습니다:

```basic
10 REM ====================================================
20 REM  祭亡妹歌 (제망매가) - 月明師 (월명사)
30 REM  Apple II HGR 한자 및 한글 출력 데모
40 REM ====================================================
50 & "\K[ 祭亡妹歌 (제망매가) ]\N"
60 & "\K  - 月明師 (월명사) -\N"
70 & "\K生死路隱 此矣有阿米\N"
80 & "\K생사 길은 이에 있으매\N"
90 & "\K吾隱去內如辭叱都\N"
100 & "\K나는 간다는 말도\N"
110 & "\K毛如云遣去奴隱尼\N"
120 & "\K못 다 이르고 갔는가\N"
130 & "\K於內秋察早隱風未\N"
140 & "\K어느 가을 이른 바람에\N"
150 & "\K阿也 彌陀刹良逢乎吾\N"
160 & "\K아아 彌陀刹에서 만날나\N"
```

#### AppleWin에서 한글/한자 입력 방법:
1. AppleWin에서 `50 & "` 까지 타이핑합니다.
2. **`Ctrl+K`** 키를 누릅니다.
3. PC 화면에 나타나는 팝업 또는 콘솔 입력창에 `[ 祭亡妹歌 (제망매가) ]`를 입력하고 `Enter`를 누릅니다.
4. Apple II에 안전한 헥사 인코딩(`\K...\N`) 문자열이 자동 입력됩니다.
5. 끝에 따옴표(`"`)를 닫고 `Enter`를 칩니다.
6. `RUN`을 입력하면 화면이 HGR 그래픽으로 전환되며 고품질 글리프가 출력됩니다.

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

## 2. 생성 및 구성 파일

- [unicode.dsk](file:///D:/msys64/home/milds/AppleWin/unicode.dsk): 부팅 가능한 통합 DOS 3.3 디스크 이미지 (`UNICODE.BIN` 드라이버, 독립 실행용 `FONT` 파일 및 `DEMO`/`JEMANG` 프로그램 탑재).
- [build_font_dsk.py](file:///D:/msys64/home/milds/AppleWin/build_font_dsk.py): BASIC 프로그램에서 사용된 글자만 추출하여 DSK 내 `FONT` 파일로 자동 베이킹하는 서브셋 빌더.
- [unicode_server.exe](file:///D:/msys64/home/milds/AppleWin/unicode_server.exe): 독립 실행 가능한 단일 PC 서버 실행 파일 (`NotoSerifCJK16.ttf` 폰트 내장).
- [unicode_server.py](file:///D:/msys64/home/milds/AppleWin/unicode_server.py): PC 측 범용 유니코드 통신/폰트 서버 소스 코드.
- [unicode_driver.s](file:///D:/msys64/home/milds/AppleWin/unicode_driver.s): 6502 어셈블리 드라이버 소스.
- [UNICODE.BIN](file:///D:/msys64/home/milds/AppleWin/UNICODE.BIN): Apple II 상주 바이너리 드라이버 ($4000).

---

## 3. 사용 방법

### 1단계: PC 서버 실행
명령 프롬프트 또는 파워셸에서 `unicode_server.exe` (또는 `python unicode_server.py`)를 실행합니다:
```bash
./unicode_server.exe
```

### 2단계: AppleWin 실행 및 디스크 부팅
1. `Release\AppleWin.exe`를 실행합니다. (Slot 2 SSC는 TCP 포트 1977로 자동 구성되어 있습니다.)
2. 드라이브 1에 `unicode.dsk`를 넣고 부팅(F2)합니다.
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

---

## 5. 독립 실행형(Standalone / 오프라인) 폰트 서브셋 빌더 및 폰트 재사용

PC 폰트 서버(Super Serial 연결) 없이 **Apple II 단독으로 DSK 디스크만 부팅하여 한글/한자를 출력**하고 싶을 때 사용합니다. 프로그램 문장에 실제로 사용된 글리프(14×16 비트맵)만 추출하여 디스크 내에 `FONT` ($6000) 파일로 저장(Baking)합니다.

### 5.1 폰트 서브셋(경량화) 재사용 원리
- **140KB 디스크 용량 한계 극복**: 유니코드 한글 11,172자(약 357KB)나 수만 자의 漢字를 140KB 플로피 디스크에 전부 담는 것은 불가능합니다.
- **문장 사용 글자만 추출**: 예를 들어 *제망매가*와 `DEMO` 전체에 사용된 서로 다른 77자의 한글과 漢字 글꼴만 추출하면 **단 2.7 KB** (디스크 섹터 단 12개)에 불과합니다.
- **메모리 상주 및 고속 렌더링**: 부팅 시 `HELLO` 프로그램이 `BLOAD FONT`를 실행하여 `$6000` 메모리에 폰트 테이블을 상주시키며, 드라이버가 통신 대기 없이 로컬 메모리에서 즉시 고속으로 HGR 화면에 글자를 렌더링합니다.

### 5.2 폰트 서브셋 빌드 및 디스크 주입 명령어
새로운 한글/한자 BASIC 프로그램을 작성하거나 기존 프로그램을 수정한 후 아래 명령을 실행합니다:

```bash
# unicode.dsk 내의 모든 BASIC 프로그램을 스캔하여 FONT 파일 자동 생성 및 주입
python build_font_dsk.py --dsk unicode.dsk

# 특정 BASIC 프로그램(예: DEMO, JEMANG)만 지정하여 폰트 추출
python build_font_dsk.py --dsk unicode.dsk --programs DEMO,JEMANG
```

- **동작 단계**:
  1. DSK 내의 BASIC 프로그램(`DEMO`, `JEMANG` 등)을 스캔하여 사용된 유니코드 한글/한자를 자동 추출합니다.
  2. PC의 고품질 TrueType 글꼴을 통해 해당 글자들만의 14×16 비트맵 테이블(`FONT`, 2~3KB)을 생성합니다.
  3. `AppleCommander`를 통해 DSK에 `FONT` 바이너리($6000)로 주입하고 `HELLO` 부팅 스크립트에 `BLOAD FONT`를 추가합니다.
  4. 부팅 시 폰트가 메모리(`$6000`)에 상주하므로, PC 폰트 서버 연결 없이도 `RUN DEMO`나 `RUN JEMANG`을 즉시 독립 실행할 수 있습니다.

### 5.3 BASIC 프로그램 작성 도구 (`inject_basic.py`) 연동
PC에서 새 BASIC 프로그램을 작성하여 디스크에 넣을 때, `inject_basic.py`를 사용하면 프로그램 주입과 동시에 폰트 서브셋도 DSK의 `FONT` 파일에 자동으로 갱신됩니다:

```bash
python inject_basic.py
```

### 5.4 폰트 바이너리 렌더링 무결성 검증 (`verify_dsk_font.py`)
DSK 디스크 이미지에 주입된 `FONT` 바이너리 데이터를 직접 역추출하여 글리프가 왜곡이나 깨짐 없이 정상 렌더링되는지 검증할 수 있습니다:

```bash
python verify_dsk_font.py
```
- 실행 시 DSK 내 `FONT` 바이너리를 직접 읽어 `verified_standalone_jemang.png` 및 `verified_standalone_demo.png` 화면 캡처 이미지를 생성합니다.

---

## 6. 라이선스 (License)

- **소스 코드 및 문서**: [MIT License](LICENSE) (Copyright (c) 2026 mildstorm)
- **번들 폰트**: `NotoSerifCJK16.ttf`는 [SIL Open Font License 1.1](https://scripts.sil.org/OFL)에 따라 배포됩니다.

