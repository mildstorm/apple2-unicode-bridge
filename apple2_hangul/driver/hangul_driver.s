/* UNICODE_DRIVER.S - Universal Apple II Unicode Multilingual Font Bridge */

    * = $4000

KSW_LO          = $38
KSW_HI          = $39
DOS_KSW_LO      = $AA55
DOS_KSW_HI      = $AA56
AMP_VECTOR      = $03F5

CHRGET          = $00B1
TXTPTR_LO       = $B8
TXTPTR_HI       = $B9

KBD             = $C000
KBDSTRB         = $C010
TXTCLR          = $C050
TXTSET          = $C051
MIXCLR          = $C052
MIXSET          = $C053
PAGE1           = $C054
HIRES           = $C057

ACIA_DATA       = $C0A8
ACIA_STAT       = $C0A9
ACIA_CMD        = $C0AA
ACIA_CTRL       = $C0AB


PTR_LO          = $06
PTR_HI          = $07
COL_OFFSET      = $08
START_Y         = $09
SRC_LO          = $0A
SRC_HI          = $0B
CACHE_PTR_LO    = $0C
CACHE_PTR_HI    = $0D
SEARCH_CNT      = $0E
TEMP_BYTE       = $0F
RAW_B0          = $10
RAW_B1          = $11
EXP_B0          = $12
EXP_B1          = $13
TEMP_B0         = $14
TEMP_B1         = $15
KEY_0           = $19
KEY_1           = $1A
KEY_2           = $1B
CUR_COL         = $1C
CUR_ROW         = $1D
DRAW_MODE       = $1E
CUR_COLOR       = $1F
HCOLOR_FLG      = $E4
HGR_HAS_DRAWN   = $F9

; ProDOS (BASIC.SYSTEM) entry points
MLI             = $BF00
VECTIN_LO       = $BE32         ; input routine of BASIC.SYSTEM
VECTIN_HI       = $BE33
MLI_ON_LINE     = $C5
MLI_GET_PREFIX  = $C7
MLI_OPEN        = $C8
DEVNUM          = $BF30         ; last device ProDOS used
MLI_READ        = $CA
MLI_CLOSE       = $CC
MLI_SET_MARK    = $CE
GETBUFR         = $BEF5         ; BASIC.SYSTEM - A pages of buffer below HIMEM

; Fixed addresses for BASIC. CALL 16384 still initialises the driver.
    JMP INIT
; $4003 (16387) is 1 to draw & strings from the font file on a ProDOS disk.
; INIT sets it when the file opens. POKE 16387,0 sends them to the server.
HD_FONT     .byte 0
; $4004 (16388) is its pathname, a length byte then up to 63 characters
HD_PATH     .byte 5
            .asc "UFONT"
            .dsb 58, 0
; $4044 (16452) is the ProDOS error of the last failed font file call, 0 if none
HD_ERR      .byte 0
; $4045 (16453) chooses what Ctrl+K types with. 0 composes on the Apple II
; (2-Bul-Sik and Hanja, needs the font file). 1 uses the PC server over the
; SSC (also kana, Russian, Greek). Without the font file it is the server.
IME_SSC     .byte 0

INIT
    LDA #$00
    STA ACIA_STAT
    LDA #$1E
    STA ACIA_CTRL
    LDA #$0B
    STA ACIA_CMD

    LDA #$00
    STA BUF_HEAD
    STA BUF_TAIL
    STA CUR_COL
    STA CUR_ROW
    STA DRAW_MODE
    STA HGR_HAS_DRAWN
    LDA #$03
    STA CUR_COLOR
    LDA #$7F
    STA HCOLOR_FLG

    LDA #$4C
    STA AMP_VECTOR
    LDA #<AMPERSAND_HANDLER
    STA AMP_VECTOR+1
    LDA #>AMPERSAND_HANDLER
    STA AMP_VECTOR+2

    ; Under ProDOS the $3D0 JMP of BASIC.SYSTEM goes to $BExx, under DOS 3.3
    ; to $9Dxx. BASIC.SYSTEM keeps KSW for itself and takes the input
    ; routine in VECTIN. $AA55 is inside BASIC.SYSTEM, so the DOS 3.3 vector
    ; must not be written there.
    LDA #$00
    STA HD_FONT
    LDA $03D2
    CMP #$BE
    BNE INIT_DOS33

    LDA #<MY_KEYIN
    STA VECTIN_LO
    LDA #>MY_KEYIN
    STA VECTIN_HI
    ; The 1K file buffer for the font file, from BASIC.SYSTEM (once, a second
    ; CALL 16384 keeps it)
    LDA HD_OPEN_PARMS+4
    BNE INIT_HAVE_BUF
    LDA #4
    JSR GETBUFR
    BCS INIT_HOOKED
    STA HD_OPEN_PARMS+4
    LDA #$00
    STA HD_OPEN_PARMS+3
INIT_HAVE_BUF
    ; Use the font file if it opens
    JSR HD_FULL_PATH
    JSR HD_OPEN
    BCS INIT_HOOKED
    JSR HD_CLOSE
    LDA #$01
    STA HD_FONT
    JMP INIT_HOOKED

INIT_DOS33
    LDA #<MY_KEYIN
    STA KSW_LO
    STA DOS_KSW_LO
    LDA #>MY_KEYIN
    STA KSW_HI
    STA DOS_KSW_HI

INIT_HOOKED
    JSR CLEAR_HGR
    LDA #$00
    STA HGR_HAS_DRAWN
    RTS

; Applesoft calls this with TXTPTR on the character after the & and that
; character in A. A string follows, or (& on its own) terminal mode.
AMPERSAND_HANDLER
    CMP #'"'
    BEQ RUN_AMP_STRING
    JMP RUN_TERMINAL_MODE

RUN_AMP_STRING
    ; & "/TAPE" loads the font cache from the cassette input, with or
    ; without a server, and stays on the text screen meanwhile
    LDY #1
    LDA (TXTPTR_LO),Y
    CMP #'/'
    BNE AMP_DRAW
    INY
    LDA (TXTPTR_LO),Y
    ORA #$20
    CMP #'t'
    BNE AMP_DRAW
    JSR TAPE_LOAD
    INC TXTPTR_LO
    BNE AMP_TAPE_END
    INC TXTPTR_HI
AMP_TAPE_END
    JMP SKIP_SLASH_TO_END

AMP_DRAW
    STA TXTCLR
    STA HIRES
    STA PAGE1
    STA MIXSET

    ; Sync CUR_COLOR from Applesoft HCOLOR ($E4) if user called HCOLOR=
    JSR SYNC_HCOLOR

    ; Draw on the Apple II itself when the $6000 cache ('H','G') is loaded
    ; or the font file is on, otherwise ask the server
    LDA #$00
    STA CACHE_OK
    LDA $6000
    CMP #'H'
    BNE AMP_CHECK_HD
    LDA $6001
    CMP #'G'
    BNE AMP_CHECK_HD
    INC CACHE_OK
AMP_CHECK_HD
    LDA HD_FONT
    STA HD_ON
    ORA CACHE_OK
    BEQ NO_LOCAL_CACHE
    JSR RUN_OFFLINE_STRING
    JMP HD_CLOSE        ; the file is opened by the first glyph read

NO_LOCAL_CACHE
    LDA #$87
    JSR SEND_BYTE

SEND_STR_LOOP
    INC TXTPTR_LO
    BNE FETCH_STR_CHAR
    INC TXTPTR_HI
FETCH_STR_CHAR
    LDY #$00
    LDA (TXTPTR_LO),Y
    BEQ SEND_STR_END
    CMP #'"'
    BEQ SEND_STR_END
    JSR SEND_BYTE
    JMP SEND_STR_LOOP

SEND_STR_END
    PHA
    LDA #$00
    JSR SEND_BYTE

    JSR PROCESS_PC_DRAWING

    PLA
    CMP #'"'
    BNE AMP_RTS
    JSR CHRGET

AMP_RTS
    RTS

SYNC_HCOLOR
    LDY HCOLOR_FLG
    LDX #7
SYNC_HCOL_LOOP
    LDA COLOR_MASK_0,X
    CMP HCOLOR_FLG
    BEQ SYNC_HCOL_FOUND
    DEX
    BPL SYNC_HCOL_LOOP
    RTS
SYNC_HCOL_FOUND
    STX CUR_COLOR
    RTS

; --- Offline Cache Renderer ---

GOTO_OFFLINE_DONE
    JMP OFFLINE_DONE

GOTO_HEX_MODE_END
    JMP HEX_MODE_END

GOTO_OFFLINE_LOOP
    JMP OFFLINE_LOOP

GOTO_HANDLE_ESCAPE
    JMP HANDLE_ESCAPE

RUN_OFFLINE_STRING
    ; Check if string starts with '/' command
    LDY #1
    LDA (TXTPTR_LO),Y
    CMP #'/'
    BNE OFFLINE_CHECK_INIT_CLR
    JMP HANDLE_SLASH_CMD

OFFLINE_CHECK_INIT_CLR
    LDA HGR_HAS_DRAWN
    BNE OFFLINE_LOOP
    INC HGR_HAS_DRAWN
    LDA DRAW_MODE
    BNE OFFLINE_LOOP
    JSR CLEAR_HGR

OFFLINE_LOOP
    INC TXTPTR_LO
    BNE FETCH_OFFLINE
    INC TXTPTR_HI
FETCH_OFFLINE
    LDY #0
    LDA (TXTPTR_LO),Y
    BEQ GOTO_OFFLINE_DONE
    CMP #'"'
    BEQ GOTO_OFFLINE_DONE
    CMP #'\\'
    BEQ GOTO_HANDLE_ESCAPE
    CMP #'['
    BEQ HANDLE_BRACKET_TAG

    ; Normal ASCII character (Space or Latin)
    CMP #$20
    BNE OFFLINE_ASCII
    ; In Replace mode (DRAW_MODE == 0), clear 14x16 space cell
    LDA DRAW_MODE
    BNE SPACE_ADV_ONLY
    JSR CLEAR_CELL_14X16
SPACE_ADV_ONLY
    LDA CUR_COL
    CLC
    ADC #2
    STA CUR_COL
    CMP #40
    BCC OFFLINE_LOOP
    LDA #0
    STA CUR_COL
    INC CUR_ROW
    LDA CUR_ROW
    CMP #12
    BCC OFFLINE_LOOP
    DEC CUR_ROW
    JSR SCROLL_HGR
SKIP_CHAR
    JMP OFFLINE_LOOP

OFFLINE_ASCII
    ; Other ASCII outside \K is drawn from the font file when it is on (the
    ; $6000 cache has no ASCII), and skipped otherwise as before
    LDX HD_ON
    BEQ SKIP_CHAR
    STA KEY_0
    LDA #$00
    STA KEY_1
    STA KEY_2
    JSR DRAW_CACHED_GLYPH
    JSR ADVANCE_CELL
    JMP OFFLINE_LOOP

; Move the cursor one 14x16 cell on, wrapping and scrolling at the edges.
ADVANCE_CELL
    LDA CUR_COL
    CLC
    ADC #2
    STA CUR_COL
    CMP #40
    BCC AC_RET
    LDA #0
    STA CUR_COL
    INC CUR_ROW
    LDA CUR_ROW
    CMP #12
    BCC AC_RET
    DEC CUR_ROW
    JSR SCROLL_HGR
AC_RET
    RTS

HANDLE_BRACKET_TAG
    ; Inspect inside [...] for [C-tag], [M-tag], [F-tag], etc.
    INC TXTPTR_LO
    BNE BRK_ADV_1
    INC TXTPTR_HI
BRK_ADV_1
    LDY #0
    LDA (TXTPTR_LO),Y
    BEQ GOTO_OFFLINE_DONE_2
    CMP #'"'
    BEQ GOTO_OFFLINE_DONE_2
    ORA #$20            ; lowercase
    CMP #'c'
    BEQ PARSE_TAG_COLOR
    CMP #'m'
    BEQ PARSE_TAG_MODE
SKIP_TO_BRACKET_END
    LDY #0
    LDA (TXTPTR_LO),Y
    BEQ GOTO_OFFLINE_DONE_2
    CMP #'"'
    BEQ GOTO_OFFLINE_DONE_2
    CMP #']'
    BEQ GOTO_OFFLINE_LOOP_2
    INC TXTPTR_LO
    BNE SKIP_TO_BRACKET_END
    INC TXTPTR_HI
    JMP SKIP_TO_BRACKET_END

GOTO_OFFLINE_DONE_2
    JMP OFFLINE_DONE

GOTO_OFFLINE_LOOP_2
    JMP OFFLINE_LOOP

PARSE_TAG_COLOR
    ; Advance until colon
FIND_COL_COLON
    INC TXTPTR_LO
    BNE FCC_1
    INC TXTPTR_HI
FCC_1
    LDY #0
    LDA (TXTPTR_LO),Y
    BEQ GOTO_OFFLINE_DONE_2
    CMP #'"'
    BEQ GOTO_OFFLINE_DONE_2
    CMP #']'
    BEQ GOTO_OFFLINE_LOOP_2
    CMP #58
    BNE FIND_COL_COLON
    ; Next char is color name or digit 0..7
    INC TXTPTR_LO
    BNE FCC_2
    INC TXTPTR_HI
FCC_2
    LDY #0
    LDA (TXTPTR_LO),Y
    JSR PARSE_COLOR_CHAR
    JMP SKIP_TO_BRACKET_END

PARSE_TAG_MODE
    ; Advance until colon
FIND_MOD_COLON
    INC TXTPTR_LO
    BNE FMC_1
    INC TXTPTR_HI
FMC_1
    LDY #0
    LDA (TXTPTR_LO),Y
    BEQ GOTO_OFFLINE_DONE_2
    CMP #'"'
    BEQ GOTO_OFFLINE_DONE_2
    CMP #']'
    BEQ GOTO_OFFLINE_LOOP_2
    CMP #58
    BNE FIND_MOD_COLON
    INC TXTPTR_LO
    BNE FMC_2
    INC TXTPTR_HI
FMC_2
    LDY #0
    LDA (TXTPTR_LO),Y
    JSR PARSE_MODE_CHAR
    JMP SKIP_TO_BRACKET_END

PARSE_COLOR_CHAR
    CMP #'0'
    BCC PCC_NAME
    CMP #'8'
    BCS PCC_NAME
    SEC
    SBC #'0'
    JMP SET_CUR_COLOR_A
PCC_NAME
    ORA #$20
    CMP #'g'            ; green (1)
    BNE PCC_N1
    LDA #1
    JMP SET_CUR_COLOR_A
PCC_N1
    CMP #'v'            ; violet / purple (2)
    BEQ PCC_VIO
    CMP #'p'            ; purple / magenta (2)
    BNE PCC_N2
PCC_VIO
    LDA #2
    JMP SET_CUR_COLOR_A
PCC_N2
    CMP #'w'            ; white (3)
    BNE PCC_N3
    LDA #3
    JMP SET_CUR_COLOR_A
PCC_N3
    CMP #'o'            ; orange / red (5)
    BEQ PCC_ORG
    CMP #'r'            ; red (5)
    BNE PCC_N4
PCC_ORG
    LDA #5
    JMP SET_CUR_COLOR_A
PCC_N4
    CMP #'b'            ; blue / cyan (6)
    BNE PCC_N5
    LDY #1
    LDA (TXTPTR_LO),Y
    ORA #$20
    CMP #'l'            ; bl... check 3rd char 'a' (black) vs 'u' (blue)
    BNE PCC_BLU
    INY
    LDA (TXTPTR_LO),Y
    ORA #$20
    CMP #'a'
    BNE PCC_BLU
    LDA #0              ; black (0)
    JMP SET_CUR_COLOR_A
PCC_BLU
    LDA #6              ; blue (6)
    JMP SET_CUR_COLOR_A
PCC_N5
    CMP #'c'            ; cyan (6)
    BNE PCC_RET
    LDA #6
SET_CUR_COLOR_A
    AND #$07
    STA CUR_COLOR
    TAX
    LDA COLOR_MASK_0,X
    STA HCOLOR_FLG
PCC_RET
    RTS

PARSE_MODE_CHAR
    CMP #'0'
    BNE PMC_1
    LDA #0
    STA DRAW_MODE
    RTS
PMC_1
    CMP #'1'
    BNE PMC_2
    LDA #1
    STA DRAW_MODE
    RTS
PMC_2
    CMP #'2'
    BNE PMC_NAME
    LDA #2
    STA DRAW_MODE
    RTS
PMC_NAME
    ORA #$20
    CMP #'r'            ; replace
    BNE PMC_N1
    LDA #0
    STA DRAW_MODE
    RTS
PMC_N1
    CMP #'o'            ; overlay / or
    BNE PMC_N2
    LDA #1
    STA DRAW_MODE
    RTS
PMC_N2
    CMP #'x'            ; xor
    BNE PMC_RET
    LDA #2
    STA DRAW_MODE
PMC_RET
    RTS

HANDLE_SLASH_CMD
    ; Advance past '/'
    INC TXTPTR_LO
    BNE HSC_1
    INC TXTPTR_HI
HSC_1
    INC TXTPTR_LO
    BNE HSC_2
    INC TXTPTR_HI
HSC_2
    LDY #0
    LDA (TXTPTR_LO),Y
    ORA #$20
    CMP #'c'            ; /clear or /color or /pos?
    BNE HSC_CHECK_M
    INY
    LDA (TXTPTR_LO),Y
    ORA #$20
    CMP #'l'            ; /clear
    BNE HSC_COLOR
    JSR CLEAR_HGR
    JMP SKIP_SLASH_TO_END
HSC_COLOR
    ; /color <arg> or /c <arg>
    JSR ADVANCE_TO_SPACE_ARG
    BCC SKIP_SLASH_TO_END
    JSR PARSE_COLOR_CHAR
    JMP SKIP_SLASH_TO_END

HSC_CHECK_M
    CMP #'m'            ; /mode <arg>
    BNE HSC_CHECK_O
    JSR ADVANCE_TO_SPACE_ARG
    BCC SKIP_SLASH_TO_END
    JSR PARSE_MODE_CHAR
    JMP SKIP_SLASH_TO_END

HSC_CHECK_O
    CMP #'o'            ; /overlay
    BNE HSC_CHECK_R
    LDA #1
    STA DRAW_MODE
    JMP SKIP_SLASH_TO_END

HSC_CHECK_R
    CMP #'r'            ; /replace
    BNE HSC_CHECK_X
    LDA #0
    STA DRAW_MODE
    JMP SKIP_SLASH_TO_END

HSC_CHECK_X
    CMP #'x'            ; /xor
    BNE HSC_CHECK_P
    LDA #2
    STA DRAW_MODE
    JMP SKIP_SLASH_TO_END

HSC_CHECK_P
    CMP #'p'            ; /pos col row
    BNE SKIP_SLASH_TO_END
    JSR ADVANCE_TO_SPACE_ARG
    BCC SKIP_SLASH_TO_END
    JSR PARSE_DEC_NUM
    ASL                 ; col (0..19) * 2 -> byte col (0..38)
    STA CUR_COL
    JSR ADVANCE_TO_SPACE_ARG
    BCC SKIP_SLASH_TO_END
    JSR PARSE_DEC_NUM
    STA CUR_ROW
    JMP SKIP_SLASH_TO_END

SKIP_SLASH_TO_END
    LDY #0
    LDA (TXTPTR_LO),Y
    BEQ SLASH_CMD_RTS
    CMP #'"'
    BEQ SLASH_CMD_END_Q
    INC TXTPTR_LO
    BNE SKIP_SLASH_TO_END
    INC TXTPTR_HI
    JMP SKIP_SLASH_TO_END
SLASH_CMD_END_Q
    JSR CHRGET
SLASH_CMD_RTS
    RTS

ADVANCE_TO_SPACE_ARG
    LDY #0
    LDA (TXTPTR_LO),Y
    BEQ ATSA_NONE
    CMP #'"'
    BEQ ATSA_NONE
    CMP #' '
    BEQ ATSA_SKIP_SPACES
    INC TXTPTR_LO
    BNE ADVANCE_TO_SPACE_ARG
    INC TXTPTR_HI
    JMP ADVANCE_TO_SPACE_ARG
ATSA_SKIP_SPACES
    INC TXTPTR_LO
    BNE ATSA_SS1
    INC TXTPTR_HI
ATSA_SS1
    LDY #0
    LDA (TXTPTR_LO),Y
    BEQ ATSA_NONE
    CMP #'"'
    BEQ ATSA_NONE
    CMP #' '
    BEQ ATSA_SKIP_SPACES
    SEC
    RTS
ATSA_NONE
    CLC
    RTS

PARSE_DEC_NUM
    LDA #0
    STA TEMP_BYTE
PDN_LOOP
    LDY #0
    LDA (TXTPTR_LO),Y
    CMP #'0'
    BCC PDN_DONE
    CMP #'9'+1
    BCS PDN_DONE
    SEC
    SBC #'0'
    PHA
    LDA TEMP_BYTE
    ASL
    STA SEARCH_CNT
    ASL
    ASL
    CLC
    ADC SEARCH_CNT
    STA TEMP_BYTE
    PLA
    CLC
    ADC TEMP_BYTE
    STA TEMP_BYTE
    INC TXTPTR_LO
    BNE PDN_LOOP
    INC TXTPTR_HI
    JMP PDN_LOOP
PDN_DONE
    LDA TEMP_BYTE
    RTS

CLEAR_CELL_14X16
    LDA CUR_ROW
    ASL
    ASL
    ASL
    ASL
    STA START_Y
    LDX #0
CC14_LOOP
    TXA
    CLC
    ADC START_Y
    TAY
    LDA HGR_LO,Y
    CLC
    ADC CUR_COL
    STA PTR_LO
    LDA HGR_HI,Y
    ADC #0
    STA PTR_HI
    LDA #0
    LDY #0
    STA (PTR_LO),Y
    INY
    STA (PTR_LO),Y
    INX
    CPX #16
    BNE CC14_LOOP
    RTS

HANDLE_ESCAPE
    INC TXTPTR_LO
    BNE ESC_ADV_1
    INC TXTPTR_HI
ESC_ADV_1
    LDY #0
    LDA (TXTPTR_LO),Y
    CMP #'K'
    BEQ HEX_MODE_START
    CMP #'C'
    BEQ ESC_COLOR_TAG
    CMP #'M'
    BEQ ESC_MODE_TAG
    JMP OFFLINE_LOOP

ESC_COLOR_TAG
    INC TXTPTR_LO
    BNE ECT_1
    INC TXTPTR_HI
ECT_1
    LDY #0
    LDA (TXTPTR_LO),Y
    CMP #58
    BNE ECT_PARSE
    INC TXTPTR_LO
    BNE ECT_2
    INC TXTPTR_HI
ECT_2
    LDY #0
    LDA (TXTPTR_LO),Y
ECT_PARSE
    JSR PARSE_COLOR_CHAR
    JMP SKIP_TO_BACKSLASH

ESC_MODE_TAG
    INC TXTPTR_LO
    BNE EMT_1
    INC TXTPTR_HI
EMT_1
    LDY #0
    LDA (TXTPTR_LO),Y
    CMP #58
    BNE EMT_PARSE
    INC TXTPTR_LO
    BNE EMT_2
    INC TXTPTR_HI
EMT_2
    LDY #0
    LDA (TXTPTR_LO),Y
EMT_PARSE
    JSR PARSE_MODE_CHAR
SKIP_TO_BACKSLASH
    LDY #0
    LDA (TXTPTR_LO),Y
    BEQ GOTO_OFFLINE_DONE_3
    CMP #'"'
    BEQ GOTO_OFFLINE_DONE_3
    CMP #'\\'
    BEQ ESC_TAG_DONE
    INC TXTPTR_LO
    BNE SKIP_TO_BACKSLASH
    INC TXTPTR_HI
    JMP SKIP_TO_BACKSLASH
ESC_TAG_DONE
    JMP OFFLINE_LOOP

GOTO_OFFLINE_DONE_3
    JMP OFFLINE_DONE

GOTO_HEX_MODE_END_3
    JMP HEX_MODE_END

HEX_MODE_START
HEX_CHAR_LOOP
    INC TXTPTR_LO
    BNE HEX_ADV_1
    INC TXTPTR_HI
HEX_ADV_1
    LDY #0
    LDA (TXTPTR_LO),Y
    BEQ GOTO_OFFLINE_DONE_3
    CMP #'"'
    BEQ GOTO_OFFLINE_DONE_3
    CMP #'\\'
    BEQ GOTO_HEX_MODE_END_3

    ; Parse Byte 0
    JSR CHAR_TO_NIBBLE
    ASL
    ASL
    ASL
    ASL
    STA TEMP_BYTE
    INC TXTPTR_LO
    BNE HEX_ADV_2
    INC TXTPTR_HI
HEX_ADV_2
    LDY #0
    LDA (TXTPTR_LO),Y
    JSR CHAR_TO_NIBBLE
    ORA TEMP_BYTE
    STA KEY_0

    CMP #$20
    BNE NOT_HEX_SPACE
    ; Space character inside hex stream
    LDA DRAW_MODE
    BNE HEX_SP_ADV
    JSR CLEAR_CELL_14X16
HEX_SP_ADV
    LDA CUR_COL
    CLC
    ADC #2
    STA CUR_COL
    CMP #40
    BCC HEX_SP_OK
    LDA #0
    STA CUR_COL
    INC CUR_ROW
    LDA CUR_ROW
    CMP #12
    BCC HEX_SP_OK
    DEC CUR_ROW
    JSR SCROLL_HGR
HEX_SP_OK
    JMP HEX_CHAR_LOOP

NOT_HEX_SPACE
    ; The rest of the UTF-8 sequence. 1 byte for ASCII, 2 for Latin, Greek
    ; and Cyrillic, 3 for Hangul, kana and Hanja. KEY_1 and KEY_2 stay 0
    ; past its end.
    LDA #$00
    STA KEY_1
    STA KEY_2
    LDA KEY_0
    BPL HEX_DRAW
    JSR HEX_BYTE
    STA KEY_1
    LDA KEY_0
    CMP #$E0
    BCC HEX_DRAW
    JSR HEX_BYTE
    STA KEY_2
    LDA KEY_0
    CMP #$F0
    BCC HEX_DRAW
    JSR HEX_BYTE        ; 4 bytes are outside the BMP, the cell stays as it is
    JMP HEX_ADVANCE

HEX_DRAW
    ; Draw glyph from cache or font file
    JSR DRAW_CACHED_GLYPH
HEX_ADVANCE

    ; Advance cursor
    LDA CUR_COL
    CLC
    ADC #2
    STA CUR_COL
    CMP #40
    BCC ADV_COL_OK
    LDA #0
    STA CUR_COL
    INC CUR_ROW
    LDA CUR_ROW
    CMP #12
    BCC ADV_COL_OK
    DEC CUR_ROW
    JSR SCROLL_HGR
ADV_COL_OK
    JMP HEX_CHAR_LOOP

HEX_MODE_END
    INC TXTPTR_LO
    BNE HEX_ADV_7
    INC TXTPTR_HI
HEX_ADV_7
    JMP OFFLINE_LOOP

OFFLINE_DONE
    LDA #0
    STA CUR_COL
    INC CUR_ROW
    LDA CUR_ROW
    CMP #12
    BCC DONE_ROW_OK
    DEC CUR_ROW
    JSR SCROLL_HGR
DONE_ROW_OK
    LDY #0
    LDA (TXTPTR_LO),Y
    CMP #'"'
    BNE OFFLINE_RTS
    JSR CHRGET
OFFLINE_RTS
    RTS

; Next two hex digits of the string as a byte.
HEX_BYTE
    INC TXTPTR_LO
    BNE HB_1
    INC TXTPTR_HI
HB_1
    LDY #0
    LDA (TXTPTR_LO),Y
    JSR CHAR_TO_NIBBLE
    ASL
    ASL
    ASL
    ASL
    STA TEMP_BYTE
    INC TXTPTR_LO
    BNE HB_2
    INC TXTPTR_HI
HB_2
    LDY #0
    LDA (TXTPTR_LO),Y
    JSR CHAR_TO_NIBBLE
    ORA TEMP_BYTE
    RTS

CHAR_TO_NIBBLE
    CMP #'0'
    BCC NIBBLE_ZERO
    CMP #'9'+1
    BCC NIBBLE_DEC
    CMP #'A'
    BCC NIBBLE_ZERO
    CMP #'F'+1
    BCS NIBBLE_ZERO
    SEC
    SBC #55
    RTS
NIBBLE_DEC
    SEC
    SBC #'0'
    RTS
NIBBLE_ZERO
    LDA #0
    RTS

; Draws the character in KEY_0..2 (UTF-8, unused bytes 0) at the cursor,
; from the $6000 cache when it has it, else from the font file when that
; is on. With neither, the cell is left as it is.
DRAW_CACHED_GLYPH
    LDA CACHE_OK
    BEQ DCG_TRY_HD
    LDA $6002
    BEQ DCG_TRY_HD
    STA SEARCH_CNT

    LDA #<$6004
    STA CACHE_PTR_LO
    LDA #>$6004
    STA CACHE_PTR_HI

SEARCH_CACHE_LOOP
    LDY #0
    LDA (CACHE_PTR_LO),Y
    CMP KEY_0
    BNE NEXT_CACHE_SLOT
    INY
    LDA (CACHE_PTR_LO),Y
    CMP KEY_1
    BNE NEXT_CACHE_SLOT
    INY
    LDA (CACHE_PTR_LO),Y
    CMP KEY_2
    BEQ FOUND_CACHE_SLOT

NEXT_CACHE_SLOT
    LDA CACHE_PTR_LO
    CLC
    ADC #36
    STA CACHE_PTR_LO
    BCC CACHE_ADV_OK
    INC CACHE_PTR_HI
CACHE_ADV_OK
    DEC SEARCH_CNT
    BNE SEARCH_CACHE_LOOP
DCG_TRY_HD
    LDA HD_ON
    BEQ DCG_RET
    JSR HD_READ_GLYPH
    BCS DCG_RET
    LDA #<HD_GLYPH
    STA SRC_LO
    LDA #>HD_GLYPH
    STA SRC_HI
    JMP RENDER_FROM_SRC
DCG_RET
    RTS

FOUND_CACHE_SLOT
    LDA CACHE_PTR_LO
    CLC
    ADC #4
    STA SRC_LO
    LDA CACHE_PTR_HI
    ADC #0
    STA SRC_HI

RENDER_FROM_SRC
    LDA CUR_ROW
    ASL
    ASL
    ASL
    ASL
    STA START_Y

    LDX #0
RENDER_CACHE_ROWS
    TXA
    CLC
    ADC START_Y
    TAY
    LDA HGR_LO,Y
    CLC
    ADC CUR_COL
    STA PTR_LO
    LDA HGR_HI,Y
    ADC #0
    STA PTR_HI

    TXA
    ASL
    TAY
    LDA (SRC_LO),Y
    STA RAW_B0
    INY
    LDA (SRC_LO),Y
    STA RAW_B1

    ; Check if color is White (3 or 7)
    LDA CUR_COLOR
    CMP #3
    BEQ DO_WHITE_GLYPH
    CMP #7
    BEQ DO_WHITE_GLYPH
    CMP #0
    BEQ DO_BLACK_GLYPH
    CMP #4
    BEQ DO_BLACK_GLYPH

    ; Smart phase-aligned color (no 3-pixel bloating, preserves 1-pixel strokes)
    LDY CUR_COLOR
    LDA COLOR_MASK_0,Y
    STA TEMP_BYTE       ; phase mask for B0
    LDA RAW_B0
    AND TEMP_BYTE
    STA EXP_B0          ; matching bits in B0
    LDA TEMP_BYTE
    EOR #$7F            ; wrong phase mask
    AND RAW_B0          ; wrong phase bits
    ASL                 ; shift 1 pixel left to match phase
    AND TEMP_BYTE
    ORA EXP_B0
    AND #$7F
    ORA COLOR_HB,Y
    STA TEMP_B0

    ; Check boundary bit 6 of RAW_B0 if it had wrong phase
    LDA RAW_B0
    AND #$40
    BEQ NO_B0_OVERFLOW
    LDA TEMP_BYTE
    AND #$40
    BNE NO_B0_OVERFLOW  ; bit 6 was already matching phase
    LDA #$01
    ORA RAW_B1
    STA RAW_B1
NO_B0_OVERFLOW

    LDA COLOR_MASK_1,Y
    STA TEMP_BYTE       ; phase mask for B1
    LDA RAW_B1
    AND TEMP_BYTE
    STA EXP_B1          ; matching bits in B1
    LDA TEMP_BYTE
    EOR #$7F            ; wrong phase mask
    AND RAW_B1          ; wrong phase bits
    ASL                 ; shift 1 pixel left to match phase
    AND TEMP_BYTE
    ORA EXP_B1
    AND #$7F
    ORA COLOR_HB,Y
    STA TEMP_B1
    JMP DO_DRAW_CELL

DO_WHITE_GLYPH
    LDY CUR_COLOR
    LDA RAW_B0
    AND #$7F
    ORA COLOR_HB,Y
    STA TEMP_B0
    LDA RAW_B1
    AND #$7F
    ORA COLOR_HB,Y
    STA TEMP_B1
    JMP DO_DRAW_CELL

DO_BLACK_GLYPH
    LDY CUR_COLOR
    LDA COLOR_HB,Y
    STA TEMP_B0
    STA TEMP_B1

DO_DRAW_CELL
    ; Draw Byte 0
    LDY #0
    LDA DRAW_MODE
    BEQ DRAW_STORE_B0
    CMP #1
    BEQ DRAW_OR_B0
    ; XOR mode (DRAW_MODE == 2). Palette bit as in overlay mode, a byte
    ; without glyph dots left as it is. XOR in the colour of a colour area
    ; cuts black text out of it.
    LDA TEMP_B0
    AND #$7F
    BEQ DRAW_DO_B1
    EOR (PTR_LO),Y
    BIT TEMP_B0
    BPL DRAW_XOR_B0_ST
    ORA #$80
DRAW_XOR_B0_ST
    STA (PTR_LO),Y
    JMP DRAW_DO_B1
DRAW_OR_B0
    ; Overlay mode. A byte without glyph dots is left as it is, palette bit
    ; and all. Otherwise the glyph dots and palette bit are ORed in, so white
    ; text keeps a coloured background palette and orange or blue text keeps
    ; its own on black.
    LDA TEMP_B0
    AND #$7F
    BEQ DRAW_DO_B1
    LDA (PTR_LO),Y
    ORA TEMP_B0
    STA (PTR_LO),Y
    JMP DRAW_DO_B1
DRAW_STORE_B0
    ; Replace mode (DRAW_MODE == 0)
    LDA TEMP_B0
    STA (PTR_LO),Y

DRAW_DO_B1
    ; Draw Byte 1
    LDY #1
    LDA DRAW_MODE
    BEQ DRAW_STORE_B1
    CMP #1
    BEQ DRAW_OR_B1
    ; XOR mode (DRAW_MODE == 2), as for byte 0
    LDA TEMP_B1
    AND #$7F
    BEQ CACHE_NEXT_ROW
    EOR (PTR_LO),Y
    BIT TEMP_B1
    BPL DRAW_XOR_B1_ST
    ORA #$80
DRAW_XOR_B1_ST
    STA (PTR_LO),Y
    JMP CACHE_NEXT_ROW
DRAW_OR_B1
    ; Overlay mode, as DRAW_OR_B0
    LDA TEMP_B1
    AND #$7F
    BEQ CACHE_NEXT_ROW
    LDA (PTR_LO),Y
    ORA TEMP_B1
    STA (PTR_LO),Y
    JMP CACHE_NEXT_ROW
DRAW_STORE_B1
    ; Replace mode (DRAW_MODE == 0)
    LDA TEMP_B1
    STA (PTR_LO),Y

CACHE_NEXT_ROW
    INX
    CPX #16
    BEQ DRAW_GLYPH_RET
    JMP RENDER_CACHE_ROWS

DRAW_GLYPH_RET
    RTS

; --- Font file on a ProDOS disk ---
; The file (UFONT) holds the 14x16 glyph of every BMP code point, 32 bytes
; as in the cache, at offset code point * 32. ProDOS reads blocks that were
; never written in a sparse file as zeros, so the file takes only as much
; disk as the glyphs in it. It is opened by the first glyph an & statement
; draws from it and closed at the end of the statement, so a CLOSE in BASIC
; never finds it open.

; HD_FPATH = HD_PATH made absolute. BASIC.SYSTEM resolves partial names
; itself and leaves the ProDOS prefix empty, and then the MLI refuses a
; partial name (error $40). So it goes after the prefix if there is one,
; else after the volume of the last device used, the disk the driver was
; just loaded from.
HD_FULL_PATH
    LDA #$00
    STA HD_FPATH
    LDA HD_PATH+1
    CMP #'/'
    BEQ HFP_APPEND
    JSR MLI
    .byte MLI_GET_PREFIX
    .word HD_PFX_PARMS
    LDA HD_FPATH
    BNE HFP_APPEND
    LDA DEVNUM
    STA HD_ONLINE_PARMS+1
    JSR MLI
    .byte MLI_ON_LINE
    .word HD_ONLINE_PARMS
    BCS HFP_APPEND
    ; HD_FPATH+1 now holds the drive, slot and name length, the name after it
    LDA HD_FPATH+1
    AND #$0F
    TAX
    LDA #'/'
    STA HD_FPATH+1
    STA HD_FPATH+2,X
    INX
    INX
    STX HD_FPATH
HFP_APPEND
    LDX HD_FPATH
    LDY #$00
HFP_COPY
    CPY HD_PATH
    BEQ HFP_DONE
    LDA HD_PATH+1,Y
    STA HD_FPATH+1,X
    INX
    INY
    CPX #64
    BCC HFP_COPY
HFP_DONE
    STX HD_FPATH
    RTS

; Opens HD_FPATH. Carry set if it does not open.
HD_OPEN
    JSR MLI
    .byte MLI_OPEN
    .word HD_OPEN_PARMS
    BCC HO_OK
    STA HD_ERR
    RTS
HO_OK
    LDA HD_OPEN_REF
    STA HD_REF
    STA HD_MARK_PARMS+1
    STA HD_READ_PARMS+1
    STA HD_CLOSE_PARMS+1
    CLC
    RTS

HD_CLOSE
    LDA HD_REF
    BEQ HC_RET
    JSR MLI
    .byte MLI_CLOSE
    .word HD_CLOSE_PARMS
    LDA #$00
    STA HD_REF
HC_RET
    RTS

; Reads the glyph of KEY_0..2 into HD_GLYPH. Carry set if it cannot.
HD_READ_GLYPH
    LDA HD_REF
    BNE HR_OPEN
    JSR HD_OPEN
    BCC HR_OPEN
    LDA #$00
    STA HD_ON           ; no file, so stop trying for this & statement
    SEC
    RTS
HR_OPEN
    ; Code point from the UTF-8 bytes
    LDA KEY_0
    BMI HR_MULTI
    STA CP_LO
    LDA #$00
    STA CP_HI
    JMP HR_MARK
HR_MULTI
    CMP #$E0
    BCS HR_THREE
    AND #$1F
    JSR CP_START
    LDA KEY_1
    JSR CP_APPEND6
    JMP HR_MARK
HR_THREE
    AND #$0F
    JSR CP_START
    LDA KEY_1
    JSR CP_APPEND6
    LDA KEY_2
    JSR CP_APPEND6
HR_MARK
    ; 32 bytes into HD_GLYPH (the onboard input reads other things too)
    LDA #<HD_GLYPH
    STA HD_READ_PARMS+2
    LDA #>HD_GLYPH
    STA HD_READ_PARMS+3
    LDA #32
    STA HD_READ_PARMS+4
    LDA #$00
    STA HD_READ_PARMS+5
    ; File position = code point * 32
    LDA CP_LO
    STA HD_MARK_POS
    LDA CP_HI
    STA HD_MARK_POS+1
    LDA #$00
    STA HD_MARK_POS+2
    LDX #5
HR_SHIFT
    ASL HD_MARK_POS
    ROL HD_MARK_POS+1
    ROL HD_MARK_POS+2
    DEX
    BNE HR_SHIFT
; Reads HD_READ_PARMS bytes at HD_MARK_POS. Carry set if it cannot.
HR_SEEK
    JSR MLI
    .byte MLI_SET_MARK
    .word HD_MARK_PARMS
    BCS HR_ERR
    JSR MLI
    .byte MLI_READ
    .word HD_READ_PARMS
    BCC HR_RET
HR_ERR
    STA HD_ERR
    SEC
HR_RET
    RTS

CP_START
    STA CP_LO
    LDA #$00
    STA CP_HI
    RTS

; CP = CP << 6 | (A & $3F)
CP_APPEND6
    AND #$3F
    PHA
    LDX #6
CPA_LOOP
    ASL CP_LO
    ROL CP_HI
    DEX
    BNE CPA_LOOP
    PLA
    ORA CP_LO
    STA CP_LO
    RTS

; --- Onboard input line (Ctrl+K composed on the Apple II) ---
; Used when the font file is open and IME_SSC is 0. The same line as the
; server draws (HGR row 9, Hanja candidates on row 8, mixed mode, the rows
; put back afterwards), the glyphs read from the font file.
; Col 0 shows the mode, the Hangul syllable HAN or A. Ctrl+K switches,
; Ctrl+J (down arrow) shows Hanja for the syllable being composed or the
; one before the cursor, Return types the line into BASIC as \K..\N hex,
; Esc cancels.
; 2-Bul-Sik composes as the Windows IME does (and as KoreanAutomata in
; unicode_server.py). The syllable is kept as the jamo typed for it in three
; slots (lead, vowel, tail), each one jamo or a pair. Jamo are numbered from
; U+3131, 0-29 consonants and 30-50 vowels. Backspace takes back one jamo.
; Caps Lock is guessed from the case as the server does. An upper-case
; letter that Shift does nothing for means Caps Lock is on, and the
; syllable being composed is read again in lower case.
; The Hanja are in the font file where no glyphs are, at U+D800 * 32. For
; syllable s (code point - $AC00) 4 bytes at $1B0000 + s*4 give where its
; list starts (in code points) and how long it is. The lists are 16-bit code
; points from $1BB000.

OB_IME
    LDA CUR_COL
    STA OB_SCOL
    LDA CUR_ROW
    STA OB_SROW
    LDA CUR_COLOR
    STA OB_SCLR
    JSR HD_OPEN
    BCC OB_OPENED
    JMP CANCEL_PC_INPUT
OB_OPENED
    LDA #$00
    STA OB_NU
    STA OB_VIEW
    STA CAND_ON
    STA OB_CAPS
    JSR OB_RESET
    LDA #$00
    LDX #39
OB_CLR_DRAWN
    STA DR_L,X
    STA DR_H,X
    STA DR_S,X
    DEX
    BPL OB_CLR_DRAWN
    JSR IME_SHOW
    LDA #$00
    STA DRAW_MODE
    LDA #$03
    STA CUR_COLOR
OB_LOOP
    JSR OB_RENDER
OB_WAIT
    LDA KBD
    BPL OB_WAIT
    STA KBDSTRB
    AND #$7F
    JSR OB_KEY
    BCC OB_LOOP
    JSR HD_CLOSE
    JSR IME_HIDE
    LDA OB_SCOL
    STA CUR_COL
    LDA OB_SROW
    STA CUR_ROW
    LDA OB_SCLR
    STA CUR_COLOR
    LDA OB_OK
    BNE OB_EMIT
    JMP CANCEL_PC_INPUT
OB_EMIT
    LDA #$01
    STA OB_WRITE
    JSR OB_ENCODE
    JMP RESTORE_REG

; One key. Carry set when the line is finished (OB_OK 1 Return, 0 Esc).
OB_KEY
    STA OB_K
    LDA CAND_ON
    BEQ OBK_MAIN
    JSR CAND_KEY
    BCS OBK_CONT
    LDA #$00
    STA CAND_ON
OBK_MAIN
    LDA OB_K
    CMP #$1B
    BNE OBK_1
    LDA #$00
    STA OB_OK
    SEC
    RTS
OBK_1
    CMP #$0D
    BNE OBK_2
    JSR OB_COMMIT
    LDA #$01
    STA OB_OK
    SEC
    RTS
OBK_2
    CMP #$08
    BEQ OBK_BS
    CMP #$7F
    BEQ OBK_BS
    CMP #$0B
    BNE OBK_3
    JSR OB_COMMIT
    LDA OB_LANG
    EOR #$01
    STA OB_LANG
    JMP OBK_CONT
OBK_3
    CMP #$0A
    BNE OBK_4
    JSR OB_HANJA
    JMP OBK_CONT
OBK_4
    CMP #$20
    BCC OBK_CONT
    JSR OB_FITS
    BCS OBK_CONT
    LDA OB_LANG
    BNE OBK_ASCII
    LDA OB_K
    JSR IS_LETTER
    BCC OBK_ASCII
    JSR OB_HANGUL_KEY
    JMP OBK_CONT
OBK_ASCII
    JSR OB_COMMIT
    LDA OB_K
    STA CP_LO
    LDA #$00
    STA CP_HI
    JSR OB_ADD_UNIT
OBK_CONT
    CLC
    RTS
OBK_BS
    LDA OB_NJ
    BEQ OBK_BS_UNIT
    JSR OB_BACK
    JMP OBK_CONT
OBK_BS_UNIT
    LDA OB_NU
    BEQ OBK_CONT
    DEC OB_NU
    JMP OBK_CONT

; Carry set when the line is full (200 bytes of hex, room for one more).
OB_FITS
    LDA #$00
    STA OB_WRITE
    JSR OB_ENCODE
    LDA OB_LEN
    CMP #191
    RTS

IS_LETTER
    CMP #'A'
    BCC IL_NO
    CMP #'Z'+1
    BCC IL_YES
    CMP #'a'
    BCC IL_NO
    CMP #'z'+1
    BCC IL_YES
IL_NO
    CLC
    RTS
IL_YES
    SEC
    RTS

; A letter in 2-Bul-Sik mode, with the Caps Lock guess
OB_HANGUL_KEY
    LDA OB_K
    CMP #'a'
    BCS OHK_LOWER
    LDA OB_CAPS
    BNE OHK_TOLOW
    LDA OB_K
    JSR IS_SHIFTED
    BCS OHK_FEED
    LDA #$01
    STA OB_CAPS
    JSR OB_REFEED
OHK_TOLOW
    LDA OB_K
    ORA #$20
    STA OB_K
    JMP OHK_FEED
OHK_LOWER
    LDA #$00
    STA OB_CAPS
OHK_FEED
    LDA OB_K
    STA OB_KK
    JSR KEY_JAMO
    STA OB_J
    JMP OB_FEED

; Carry set for Q W E R T O P (Shift gives them another jamo)
IS_SHIFTED
    LDX #6
ISH_LOOP
    CMP SHIFT_KEYS,X
    BEQ ISH_YES
    DEX
    BPL ISH_LOOP
    CLC
    RTS
ISH_YES
    SEC
    RTS

; Letter in A to its jamo
KEY_JAMO
    CMP #'a'
    BCS KJ_LOW
    LDX #6
KJ_SHIFT_LOOP
    CMP SHIFT_KEYS,X
    BEQ KJ_SHIFT
    DEX
    BPL KJ_SHIFT_LOOP
    ORA #$20
KJ_LOW
    SEC
    SBC #'a'
    TAX
    LDA KEYMAP,X
    RTS
KJ_SHIFT
    LDA SHIFT_JAMO,X
    RTS

; Read the syllable being composed again with its keys in lower case
OB_REFEED
    LDX #$00
ORF_COPY
    CPX OB_NJ
    BEQ ORF_GO
    LDA OB_KEYS,X
    ORA #$20
    STA OB_TK,X
    INX
    JMP ORF_COPY
ORF_GO
    STX OB_TN
    JSR OB_RESET
    LDA #$00
    STA OB_TI
ORF_LOOP
    LDX OB_TI
    CPX OB_TN
    BEQ ORF_END
    LDA OB_TK,X
    STA OB_KK
    JSR KEY_JAMO
    STA OB_J
    JSR OB_FEED
    INC OB_TI
    JMP ORF_LOOP
ORF_END
    RTS

OB_RESET
    LDA #$00
    STA SL_CNT
    STA SL_CNT+1
    STA SL_CNT+2
    STA OB_NJ
    RTS

; Commit the syllable being composed (if any) to the line
OB_COMMIT
    JSR OB_CURRENT
    BCC OBC_RESET
    JSR OB_ADD_UNIT
OBC_RESET
    JMP OB_RESET

OB_ADD_UNIT
    LDX OB_NU
    CPX #80
    BCS OAU_RET
    LDA CP_LO
    STA OB_UL,X
    LDA CP_HI
    STA OB_UH,X
    INC OB_NU
OAU_RET
    RTS

; Take back the last jamo typed
OB_BACK
    LDX OB_NJ
    BEQ OBB_RET
    DEX
    STX OB_NJ
    LDA OB_ORDER,X
    TAX
    DEC SL_CNT,X
OBB_RET
    RTS

; Add jamo X with key Y to slot A
OB_ADD3
    STA OB_AS
    STX OB_AJ
    STY OB_AK
    LDX OB_AS
    LDA OB_AS
    ASL
    CLC
    ADC SL_CNT,X
    TAY
    LDA OB_AJ
    STA SL_J,Y
    INC SL_CNT,X
    LDX OB_NJ
    LDA OB_AS
    STA OB_ORDER,X
    LDA OB_AK
    STA OB_KEYS,X
    INC OB_NJ
    RTS

; Jamo A (first) and X (second) combined in A, carry set if they pair
PAIR
    STA OB_PA
    STX OB_PB
    LDY #$00
PR_LOOP
    LDA PAIRS,Y
    CMP #$FF
    BEQ PR_NO
    CMP OB_PA
    BNE PR_NEXT
    LDA PAIRS+1,Y
    CMP OB_PB
    BNE PR_NEXT
    LDA PAIRS+2,Y
    SEC
    RTS
PR_NEXT
    INY
    INY
    INY
    JMP PR_LOOP
PR_NO
    CLC
    RTS

; Feed jamo OB_J typed with key OB_KK
OB_FEED
    LDA OB_J
    CMP #30
    BCS OBF_VOWEL
    JMP OBF_CONS
OBF_VOWEL
    LDA SL_CNT+2
    BEQ OBF_V_NOTAIL
    ; The last final consonant leads the new syllable
    DEC SL_CNT+2
    LDX SL_CNT+2
    LDA SL_J+4,X
    STA OB_MJ
    DEC OB_NJ
    LDX OB_NJ
    LDA OB_KEYS,X
    STA OB_MK
    JSR OB_COMMIT
    LDA #0
    LDX OB_MJ
    LDY OB_MK
    JSR OB_ADD3
    JMP OBF_ADD_VOWEL
OBF_V_NOTAIL
    LDA SL_CNT+1
    BEQ OBF_V_NOVOW
    CMP #1
    BNE OBF_V_RESTART
    LDA SL_J+2
    LDX OB_J
    JSR PAIR
    BCS OBF_ADD_VOWEL
OBF_V_RESTART
    JSR OB_COMMIT
    JMP OBF_ADD_VOWEL
OBF_V_NOVOW
    LDA SL_CNT
    CMP #2
    BNE OBF_ADD_VOWEL
    ; Two consonants typed alone, then a vowel. The first stays alone, the
    ; second leads.
    LDA SL_J+1
    STA OB_MJ
    LDA OB_KEYS+1
    STA OB_MK
    LDA SL_J
    JSR JAMO_CP
    JSR OB_ADD_UNIT
    JSR OB_RESET
    LDA #0
    LDX OB_MJ
    LDY OB_MK
    JSR OB_ADD3
OBF_ADD_VOWEL
    LDA #1
    LDX OB_J
    LDY OB_KK
    JMP OB_ADD3
OBF_CONS
    LDA SL_CNT+1
    BNE OBF_C_VOW
    LDA SL_CNT
    BEQ OBF_C_LEAD
    CMP #1
    BNE OBF_C_RESTART
    LDA SL_J
    LDX OB_J
    JSR PAIR
    BCS OBF_C_LEAD
OBF_C_RESTART
    JSR OB_COMMIT
OBF_C_LEAD
    LDA #0
    LDX OB_J
    LDY OB_KK
    JMP OB_ADD3
OBF_C_VOW
    LDA SL_CNT
    BEQ OBF_C_RESTART
    LDA SL_CNT+2
    BNE OBF_C_TAIL2
    LDX OB_J
    LDA JONG_IDX,X
    CMP #$FF
    BEQ OBF_C_RESTART
OBF_C_ADDTAIL
    LDA #2
    LDX OB_J
    LDY OB_KK
    JMP OB_ADD3
OBF_C_TAIL2
    CMP #1
    BNE OBF_C_RESTART
    LDA SL_J+4
    LDX OB_J
    JSR PAIR
    BCS OBF_C_ADDTAIL
    JMP OBF_C_RESTART

JAMO_CP
    CLC
    ADC #$31
    STA CP_LO
    LDA #$31
    STA CP_HI
    RTS

; The character being composed in CP_LO/CP_HI, carry set if there is one
OB_CURRENT
    LDA SL_CNT+1
    BNE OC_VOW
    LDA SL_CNT
    BNE OC_LEAD
    CLC
    RTS
OC_LEAD
    LDA SL_J
    LDX SL_CNT
    CPX #2
    BNE OC_JAMO
    LDX SL_J+1
    JSR PAIR
OC_JAMO
    JSR JAMO_CP
    SEC
    RTS
OC_VOW
    LDA SL_J+2
    LDX SL_CNT+1
    CPX #2
    BNE OC_V1
    LDX SL_J+3
    JSR PAIR
OC_V1
    STA OB_V
    LDA SL_CNT
    BNE OC_SYL
    LDA OB_V
    JMP OC_JAMO
OC_SYL
    LDA #$00
    STA OB_JONG
    LDA SL_CNT+2
    BEQ OC_NOJONG
    LDA SL_J+4
    LDX SL_CNT+2
    CPX #2
    BNE OC_J1
    LDX SL_J+5
    JSR PAIR
OC_J1
    TAX
    LDA JONG_IDX,X
    STA OB_JONG
OC_NOJONG
    ; $AC00 + (lead * 21 + vowel) * 28 + tail
    LDA OB_V
    SEC
    SBC #30
    STA OB_NL
    LDA #$00
    STA OB_NH
    LDX SL_J
    LDA CHO_IDX,X
    TAX
    BEQ OC_MUL
OC_21
    CLC
    LDA OB_NL
    ADC #21
    STA OB_NL
    BCC OC_21_NC
    INC OB_NH
OC_21_NC
    DEX
    BNE OC_21
OC_MUL
    ASL OB_NL
    ROL OB_NH
    ASL OB_NL
    ROL OB_NH
    LDA OB_NL
    STA OB_ML
    LDA OB_NH
    STA OB_MH
    ASL OB_NL
    ROL OB_NH
    ASL OB_NL
    ROL OB_NH
    ASL OB_NL
    ROL OB_NH
    SEC
    LDA OB_NL
    SBC OB_ML
    STA CP_LO
    LDA OB_NH
    SBC OB_MH
    STA CP_HI
    CLC
    LDA CP_LO
    ADC OB_JONG
    STA CP_LO
    LDA CP_HI
    ADC #$AC
    STA CP_HI
    SEC
    RTS

; The line, and the candidates above it, as \K..\N hex. OB_WRITE 1 types it
; into the input buffer, 0 only counts it (OB_LEN).
OB_ENCODE
    LDA #$00
    STA OB_LEN
    STA OB_RUN
    STA OB_I
OBE_LOOP
    LDX OB_I
    CPX OB_NU
    BCS OBE_CUR
    LDA OB_UL,X
    STA CP_LO
    LDA OB_UH,X
    STA CP_HI
    JSR OBE_ONE
    INC OB_I
    JMP OBE_LOOP
OBE_CUR
    JSR OB_CURRENT
    BCC OBE_END
    JSR OBE_ONE
OBE_END
    LDA OB_RUN
    BEQ OBE_RET
    LDA #'\\'
    JSR OBE_PUT
    LDA #'N'
    JMP OBE_PUT
OBE_RET
    RTS
OBE_ONE
    LDA CP_HI
    BNE OBE_MULTI
    LDA CP_LO
    BMI OBE_MULTI
    LDA OB_RUN
    BEQ OBE_ASCII
    LDA #$00
    STA OB_RUN
    LDA #'\\'
    JSR OBE_PUT
    LDA #'N'
    JSR OBE_PUT
OBE_ASCII
    LDA CP_LO
    JMP OBE_PUT
OBE_MULTI
    LDA OB_RUN
    BNE OBE_UTF8
    INC OB_RUN
    LDA #'\\'
    JSR OBE_PUT
    LDA #'K'
    JSR OBE_PUT
OBE_UTF8
    ; OB_T = code point >> 6
    LDA CP_HI
    STA OB_T
    LDA CP_LO
    ASL
    ROL OB_T
    ASL
    ROL OB_T
    LDA CP_HI
    CMP #$08
    BCS OBE_3
    LDA OB_T
    ORA #$C0
    JSR OBE_HEX
    JMP OBE_LAST
OBE_3
    LDA CP_HI
    LSR
    LSR
    LSR
    LSR
    ORA #$E0
    JSR OBE_HEX
    LDA OB_T
    AND #$3F
    ORA #$80
    JSR OBE_HEX
OBE_LAST
    LDA CP_LO
    AND #$3F
    ORA #$80
OBE_HEX
    PHA
    LSR
    LSR
    LSR
    LSR
    JSR OBE_NIB
    PLA
    AND #$0F
OBE_NIB
    CMP #10
    BCC OBE_DIGIT
    ADC #6
OBE_DIGIT
    ADC #'0'
OBE_PUT
    LDX OB_WRITE
    BEQ OBP_COUNT
    LDX BUF_HEAD
    STA BUF_START,X
    INC BUF_HEAD
OBP_COUNT
    INC OB_LEN
    RTS

; Draw the line (row 9) and the candidates (row 8), the cells that changed
OB_RENDER
    LDA OB_NU
    CLC
    ADC #1
    STA OB_L
    SEC
    SBC OB_VIEW
    BCC OBR_FIX
    BEQ OBR_FIX
    CMP #20
    BCC OBR_VIEW_OK
OBR_FIX
    ; Page by half a line
    LDA OB_L
    SEC
    SBC #9
    BCS OBR_SETV
    LDA #0
OBR_SETV
    STA OB_VIEW
OBR_VIEW_OK
    LDA #9
    STA OB_ROW
    LDA #0
    STA OB_COL
    LDA #1
    STA OB_STY
    LDA OB_LANG
    BEQ OBR_HAN
    LDA #'A'
    STA CP_LO
    LDA #0
    STA CP_HI
    JMP OBR_MODE
OBR_HAN
    LDA #$5C
    STA CP_LO
    LDA #$D5
    STA CP_HI
OBR_MODE
    JSR OB_CELL
    LDA #1
    STA OB_COL
OBR_TEXT
    LDA OB_VIEW
    CLC
    ADC OB_COL
    SEC
    SBC #1
    STA OB_I2
    CMP OB_NU
    BCS OBR_NOTUNIT
    TAX
    LDA OB_UL,X
    STA CP_LO
    LDA OB_UH,X
    STA CP_HI
    LDA #0
    STA OB_STY
    JMP OBR_PUT
OBR_NOTUNIT
    LDA OB_I2
    CMP OB_NU
    BNE OBR_EMPTY
    JSR OB_CURRENT
    BCC OBR_CURSOR
    LDA #1
    STA OB_STY
    JMP OBR_PUT
OBR_CURSOR
    LDA #0
    STA CP_LO
    STA CP_HI
    LDA #2
    STA OB_STY
    JMP OBR_PUT
OBR_EMPTY
    LDA #0
    STA CP_LO
    STA CP_HI
    STA OB_STY
OBR_PUT
    JSR OB_CELL
    INC OB_COL
    LDA OB_COL
    CMP #20
    BCC OBR_TEXT
    LDA #8
    STA OB_ROW
    LDA #0
    STA OB_COL
OBR_CAND
    LDA #0
    STA CP_LO
    STA CP_HI
    STA OB_STY
    LDA CAND_ON
    BEQ OBR_CPUT
    LDA OB_COL
    CMP #18
    BCS OBR_ARROW
    LSR
    STA OB_T
    CMP CAND_N
    BCS OBR_CPUT
    LDA OB_COL
    AND #1
    BNE OBR_HANJA_CELL
    LDA OB_T
    CLC
    ADC #'1'
    STA CP_LO
    LDA #1
    STA OB_STY
    JMP OBR_CPUT
OBR_HANJA_CELL
    LDA OB_T
    ASL
    TAX
    LDA CAND_CP,X
    STA CP_LO
    LDA CAND_CP+1,X
    STA CP_HI
    JMP OBR_CPUT
OBR_ARROW
    BNE OBR_RIGHT
    LDA CAND_FIRST
    BEQ OBR_CPUT
    LDA #'<'
    STA CP_LO
    JMP OBR_CPUT
OBR_RIGHT
    JSR CAND_MORE
    BCC OBR_CPUT
    LDA #'>'
    STA CP_LO
OBR_CPUT
    JSR OB_CELL
    INC OB_COL
    LDA OB_COL
    CMP #20
    BCC OBR_CAND
    RTS

; Cell OB_COL of row OB_ROW to CP_LO/CP_HI in style OB_STY (0 plain,
; 1 inverse, 2 underline cursor), unless it already shows that
OB_CELL
    LDX OB_COL
    LDA OB_ROW
    CMP #9
    BEQ OCL_IDX
    TXA
    CLC
    ADC #20
    TAX
OCL_IDX
    LDA CP_LO
    CMP DR_L,X
    BNE OCL_DRAW
    LDA CP_HI
    CMP DR_H,X
    BNE OCL_DRAW
    LDA OB_STY
    CMP DR_S,X
    BNE OCL_DRAW
    RTS
OCL_DRAW
    LDA CP_LO
    STA DR_L,X
    LDA CP_HI
    STA DR_H,X
    LDA OB_STY
    STA DR_S,X
    LDA CP_LO
    ORA CP_HI
    BEQ OCL_BLANK
    JSR HR_MARK
    BCC OCL_STYLE
OCL_BLANK
    LDX #31
    LDA #0
OCL_ZERO
    STA HD_GLYPH,X
    DEX
    BPL OCL_ZERO
OCL_STYLE
    LDA OB_STY
    BEQ OCL_PUT
    CMP #1
    BNE OCL_CURSOR
    LDX #31
OCL_INV
    LDA HD_GLYPH,X
    EOR #$7F
    STA HD_GLYPH,X
    DEX
    BPL OCL_INV
    JMP OCL_PUT
OCL_CURSOR
    LDX #28
OCL_UNDER
    LDA HD_GLYPH,X
    ORA #$7F
    STA HD_GLYPH,X
    INX
    CPX #32
    BNE OCL_UNDER
OCL_PUT
    LDA OB_COL
    ASL
    STA CUR_COL
    LDA OB_ROW
    STA CUR_ROW
    LDA #<HD_GLYPH
    STA SRC_LO
    LDA #>HD_GLYPH
    STA SRC_HI
    JMP RENDER_FROM_SRC

; Carry set for a precomposed Hangul syllable in CP_LO/CP_HI
IS_SYL
    LDA CP_HI
    CMP #$AC
    BCC ISY_NO
    CMP #$D8
    BCS ISY_NO
    CMP #$D7
    BNE ISY_YES
    LDA CP_LO
    CMP #$A4
    BCS ISY_NO
ISY_YES
    SEC
    RTS
ISY_NO
    CLC
    RTS

OH_RET0
    RTS

; Ctrl+J. Hanja for the syllable being composed, else the one before it.
OB_HANJA
    LDA OB_LANG
    BNE OH_RET0
    JSR OB_CURRENT
    BCC OH_LAST
    JSR IS_SYL
    BCC OH_LAST
    LDA #0
    STA CAND_SRC
    JMP OH_LOOKUP
OH_LAST
    LDX OB_NU
    BEQ OH_RET0
    DEX
    LDA OB_UL,X
    STA CP_LO
    LDA OB_UH,X
    STA CP_HI
    JSR IS_SYL
    BCC OH_RET
    LDA #1
    STA CAND_SRC
OH_LOOKUP
    ; $1B0000 + (code point - $AC00) * 4
    LDA CP_LO
    STA HD_MARK_POS
    LDA CP_HI
    SEC
    SBC #$AC
    STA HD_MARK_POS+1
    LDA #0
    STA HD_MARK_POS+2
    ASL HD_MARK_POS
    ROL HD_MARK_POS+1
    ROL HD_MARK_POS+2
    ASL HD_MARK_POS
    ROL HD_MARK_POS+1
    ROL HD_MARK_POS+2
    LDA HD_MARK_POS+2
    CLC
    ADC #$1B
    STA HD_MARK_POS+2
    LDA #<CAND_HDR
    STA HD_READ_PARMS+2
    LDA #>CAND_HDR
    STA HD_READ_PARMS+3
    LDA #4
    STA HD_READ_PARMS+4
    LDA #0
    STA HD_READ_PARMS+5
    JSR HR_SEEK
    BCS OH_RET
    LDA CAND_HDR+2
    BEQ OH_RET
    STA CAND_CNT
    LDA CAND_HDR
    STA CAND_OFF
    LDA CAND_HDR+1
    STA CAND_OFF+1
    LDA #0
    STA CAND_FIRST
    JSR CAND_LOAD
    BCS OH_RET
    LDA #1
    STA CAND_ON
OH_RET
    RTS

; The page from CAND_FIRST into CAND_CP (CAND_N of them)
CAND_LOAD
    LDA CAND_CNT
    SEC
    SBC CAND_FIRST
    CMP #9
    BCC CL_N
    LDA #9
CL_N
    STA CAND_N
    LDA CAND_OFF
    CLC
    ADC CAND_FIRST
    STA HD_MARK_POS
    LDA CAND_OFF+1
    ADC #0
    STA HD_MARK_POS+1
    LDA #0
    STA HD_MARK_POS+2
    ASL HD_MARK_POS
    ROL HD_MARK_POS+1
    ROL HD_MARK_POS+2
    CLC
    LDA HD_MARK_POS+1
    ADC #$B0
    STA HD_MARK_POS+1
    LDA HD_MARK_POS+2
    ADC #$1B
    STA HD_MARK_POS+2
    LDA #<CAND_CP
    STA HD_READ_PARMS+2
    LDA #>CAND_CP
    STA HD_READ_PARMS+3
    LDA CAND_N
    ASL
    STA HD_READ_PARMS+4
    LDA #0
    STA HD_READ_PARMS+5
    JMP HR_SEEK

; Carry set if there is a page after this one
CAND_MORE
    LDA CAND_FIRST
    CLC
    ADC #9
    BCS CM_NO
    CMP CAND_CNT
    BCS CM_NO
    SEC
    RTS
CM_NO
    CLC
    RTS

; Keys while the candidates show. Carry set when the key was used.
CAND_KEY
    LDA OB_K
    CMP #'1'
    BCC CK_NOTDIG
    CMP #'9'+1
    BCS CK_NOTDIG
    SEC
    SBC #'1'
    CMP CAND_N
    BCS CK_USED
    JSR CAND_PICK
    JMP CK_USED
CK_NOTDIG
    CMP #$0D
    BNE CK_1
    LDA #0
    JSR CAND_PICK
    JMP CK_USED
CK_1
    CMP #$20
    BEQ CK_NEXT
    CMP #$15
    BEQ CK_NEXT
    CMP #$0A
    BEQ CK_NEXT
    CMP #$08
    BEQ CK_PREV
    CMP #$0B
    BEQ CK_PREV
    CMP #$1B
    BNE CK_NO
    LDA #0
    STA CAND_ON
    JMP CK_USED
CK_NO
    CLC
    RTS
CK_NEXT
    JSR CAND_MORE
    BCC CK_FIRST0
    LDA CAND_FIRST
    CLC
    ADC #9
    STA CAND_FIRST
    JMP CK_LOAD
CK_FIRST0
    LDA #0
    STA CAND_FIRST
    JMP CK_LOAD
CK_PREV
    LDA CAND_FIRST
    BEQ CK_LAST
    SEC
    SBC #9
    STA CAND_FIRST
    JMP CK_LOAD
CK_LAST
    LDA #0
    STA CAND_FIRST
CKL_LOOP
    JSR CAND_MORE
    BCC CK_LOAD
    LDA CAND_FIRST
    CLC
    ADC #9
    STA CAND_FIRST
    JMP CKL_LOOP
CK_LOAD
    JSR CAND_LOAD
CK_USED
    SEC
    RTS

; Candidate A in place of the syllable it was asked for
CAND_PICK
    ASL
    TAX
    LDA CAND_CP,X
    STA CP_LO
    LDA CAND_CP+1,X
    STA CP_HI
    LDA #0
    STA CAND_ON
    LDA CAND_SRC
    BNE CP_REPLACE
    JSR OB_RESET
    JMP OB_ADD_UNIT
CP_REPLACE
    LDX OB_NU
    DEX
    LDA CP_LO
    STA OB_UL,X
    LDA CP_HI
    STA OB_UH,X
    RTS

; 2-Bul-Sik layout. a to z, then Q W E R T O P with Shift.
KEYMAP      .byte 16, 47, 25, 22, 6, 8, 29, 38, 32, 34, 30, 50, 48
            .byte 43, 31, 35, 17, 0, 3, 20, 36, 28, 23, 27, 42, 26
SHIFT_KEYS  .byte 'Q', 'W', 'E', 'R', 'T', 'O', 'P'
SHIFT_JAMO  .byte 18, 24, 7, 1, 21, 33, 37
; Consonant jamo 0-29 as a lead (0-18) and as a tail (1-27), $FF if none
CHO_IDX     .byte 0, 1, $FF, 2, $FF, $FF, 3, 4, 5, $FF, $FF, $FF, $FF, $FF, $FF
            .byte $FF, 6, 7, 8, $FF, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18
JONG_IDX    .byte 1, 2, 3, 4, 5, 6, 7, $FF, 8, 9, 10, 11, 12, 13, 14
            .byte 15, 16, 17, $FF, 18, 19, 20, 21, 22, $FF, 23, 24, 25, 26, 27
; Jamo that combine, first, second, combined
PAIRS       .byte 38, 30, 39,  38, 31, 40,  38, 50, 41,  43, 34, 44
            .byte 43, 35, 45,  43, 50, 46,  48, 50, 49
            .byte 0, 20, 2,  3, 23, 4,  3, 29, 5,  8, 0, 9,  8, 16, 10
            .byte 8, 17, 11,  8, 20, 12,  8, 27, 13,  8, 28, 14,  8, 29, 15
            .byte 17, 20, 19,  $FF

; --- PC Streaming & Driver Core ---

PROCESS_PC_DRAWING
    JSR RECV_BYTE
    CMP #$00
    BEQ DRAWING_DONE
    CMP #$81
    BEQ EXEC_DRAW
    CMP #$82
    BEQ EXEC_CLEAR
    CMP #$84
    BEQ EXEC_SCROLL
    CMP #$88
    BEQ EXEC_SET_MODE
    JMP PROCESS_PC_DRAWING

EXEC_DRAW
    JSR DRAW_ONE_GLYPH
    JMP PROCESS_PC_DRAWING

EXEC_CLEAR
    JSR CLEAR_HGR
    JMP PROCESS_PC_DRAWING

EXEC_SCROLL
    JSR SCROLL_HGR
    JMP PROCESS_PC_DRAWING

EXEC_SET_MODE
    JSR RECV_BYTE
    STA DRAW_MODE
    JMP PROCESS_PC_DRAWING

DRAWING_DONE
    RTS

MY_KEYIN
    LDA BUF_HEAD
    CMP BUF_TAIL
    BEQ READ_KBD

    STX SAVE_X
    LDX BUF_TAIL
    LDA BUF_START,X
    INC BUF_TAIL
    LDX SAVE_X
    ORA #$80
    RTS

READ_KBD
    LDA KBD
    BPL READ_KBD
    STA KBDSTRB
    AND #$7F

    CMP #$0B
    BEQ HANDLE_CTRL_K

    CMP #$1B
    BNE NOT_ESC
    STA TXTSET
    LDA #0
    STA CUR_COL
    STA CUR_ROW
    STA HGR_HAS_DRAWN
    LDA #$8D
    RTS

NOT_ESC
    CMP #'a'
    BCC NOT_LOWER
    CMP #'z'+1
    BCS NOT_LOWER
    SEC
    SBC #$20
NOT_LOWER
    ORA #$80
    RTS

; --- Ctrl+K - 2-Bul-Sik input line ---
; Every key goes to the server as typed (no upper-casing). The server composes
; the text and draws the line on HGR row 9 (Hanja candidates on row 8) with
; $81 packets. Row 9 is the last row shown in mixed mode, so the four text
; lines stay in view. Rows 8-9 are saved on the first packet and put back
; when the server ends the input with $86, a length and the bytes, which
; are then typed into GETLN. ESC goes to the server, which closes the
; candidates or cancels. A second ESC with no answer in between leaves
; without waiting for the server.
HANDLE_CTRL_K
    STX SAVE_X
    STY SAVE_Y
    LDA DRAW_MODE
    STA IME_OLDMODE
    LDA #$00
    STA IME_SHOWN
    STA IME_ESCS
    ; Onboard unless IME_SSC asks for the server or there is no font file
    LDA IME_SSC
    BNE CTRLK_SSC
    LDA HD_FONT
    BEQ CTRLK_SSC
    JMP OB_IME
CTRLK_SSC
    LDA #$0B
    JSR SEND_BYTE

IME_LOOP
    LDA ACIA_STAT
    AND #$08
    BNE IME_RX

    LDA KBD
    BPL IME_LOOP
    STA KBDSTRB
    AND #$7F
    CMP #$1B
    BNE IME_SEND_KEY
    LDX IME_ESCS
    BNE CANCEL_PC_INPUT
    INC IME_ESCS
IME_SEND_KEY
    JSR SEND_BYTE
    JMP IME_LOOP

IME_RX
    LDX #$00
    STX IME_ESCS        ; the server answered, so ESC goes to it again
    LDA ACIA_DATA
    CMP #$81
    BEQ IME_DRAW
    CMP #$88
    BEQ IME_SET_MODE
    CMP #$86
    BEQ READ_INPUT_CMD
    JMP IME_LOOP

IME_DRAW
    LDA IME_SHOWN
    BNE IME_DRAW_GO
    JSR IME_SHOW
IME_DRAW_GO
    JSR DRAW_ONE_GLYPH
    JMP IME_LOOP

IME_SET_MODE
    JSR RECV_BYTE
    STA DRAW_MODE
    JMP IME_LOOP

READ_INPUT_CMD
    JSR IME_HIDE
    JSR RECV_BYTE
    STA SAVE_CNT
    BEQ RESTORE_REG

READ_PAYLOAD_LOOP
    JSR RECV_BYTE
    LDX BUF_HEAD
    STA BUF_START,X
    INC BUF_HEAD
    DEC SAVE_CNT
    BNE READ_PAYLOAD_LOOP

RESTORE_REG
    LDX SAVE_X
    LDY SAVE_Y
    JMP MY_KEYIN

CANCEL_PC_INPUT
    JSR IME_HIDE
    LDX SAVE_X
    LDY SAVE_Y
    JMP READ_KBD

; Save HGR lines 128-159 (rows 8-9) to IME_SAVE, blank them, show mixed HGR.
IME_SHOW
    LDA #128
    STA IME_LINE
    LDA #<IME_SAVE
    STA SRC_LO
    LDA #>IME_SAVE
    STA SRC_HI
IME_SHOW_LINE
    LDY IME_LINE
    LDA HGR_LO,Y
    STA PTR_LO
    LDA HGR_HI,Y
    STA PTR_HI
    LDY #39
IME_SHOW_BYTE
    LDA (PTR_LO),Y
    STA (SRC_LO),Y
    LDA #$00
    STA (PTR_LO),Y
    DEY
    BPL IME_SHOW_BYTE
    JSR IME_NEXT_LINE
    BNE IME_SHOW_LINE
    STA TXTCLR
    STA HIRES
    STA PAGE1
    STA MIXSET
    INC IME_SHOWN
    RTS

; Put lines 128-159 back, return to text and restore the draw mode.
IME_HIDE
    LDA IME_SHOWN
    BEQ IME_HIDE_MODE
    LDA #128
    STA IME_LINE
    LDA #<IME_SAVE
    STA SRC_LO
    LDA #>IME_SAVE
    STA SRC_HI
IME_HIDE_LINE
    LDY IME_LINE
    LDA HGR_LO,Y
    STA PTR_LO
    LDA HGR_HI,Y
    STA PTR_HI
    LDY #39
IME_HIDE_BYTE
    LDA (SRC_LO),Y
    STA (PTR_LO),Y
    DEY
    BPL IME_HIDE_BYTE
    JSR IME_NEXT_LINE
    BNE IME_HIDE_LINE
    STA TXTSET
    LDA #$00
    STA IME_SHOWN
IME_HIDE_MODE
    LDA IME_OLDMODE
    STA DRAW_MODE
    RTS

; Advance SRC by 40 bytes and IME_LINE by one; Z set after line 159.
IME_NEXT_LINE
    CLC
    LDA SRC_LO
    ADC #40
    STA SRC_LO
    BCC IME_NL_NC
    INC SRC_HI
IME_NL_NC
    INC IME_LINE
    LDA IME_LINE
    CMP #160
    RTS

RUN_TERMINAL_MODE
    STA TXTCLR
    STA HIRES
    STA PAGE1
    STA MIXSET
    LDA #$00
    STA ACIA_STAT
    LDA #$1E
    STA ACIA_CTRL
    LDA #$0B
    STA ACIA_CMD
    ; Tell the server, which clears the screen and takes the keys from now on
    LDA #$AA
    JSR SEND_BYTE

TERM_LOOP
    LDA KBD
    BPL CHECK_RX
    STA KBDSTRB
    AND #$7F
    CMP #$1B
    BEQ TERM_ESC
    PHA
WAIT_TX_TERM
    LDA ACIA_STAT
    AND #$10
    BEQ WAIT_TX_TERM
    PLA
    STA ACIA_DATA

CHECK_RX
    LDA ACIA_STAT
    AND #$08
    BEQ TERM_LOOP

    LDA ACIA_DATA
    CMP #$81
    BEQ TERM_DRAW
    CMP #$82
    BEQ TERM_CLEAR
    CMP #$83
    BEQ EXIT_TERM
    CMP #$84
    BEQ TERM_SCROLL
    CMP #$88
    BEQ TERM_SET_MODE
    JMP TERM_LOOP

TERM_DRAW
    JSR DRAW_ONE_GLYPH
    JMP TERM_LOOP

TERM_CLEAR
    JSR CLEAR_HGR
    JMP TERM_LOOP

TERM_SCROLL
    JSR SCROLL_HGR
    JMP TERM_LOOP

TERM_SET_MODE
    JSR RECV_BYTE
    STA DRAW_MODE
    JMP TERM_LOOP

TERM_ESC
    ; ESC leaves, and tells the server so it goes back to BASIC mode
    JSR SEND_BYTE
EXIT_TERM
    ; TXTPTR is still at the end of the & statement
    STA TXTSET
    RTS

DRAW_ONE_GLYPH
    JSR RECV_BYTE
    ASL
    STA COL_OFFSET
    JSR RECV_BYTE
    ASL
    ASL
    ASL
    ASL
    STA START_Y

    LDX #$00
GLYPH_ROW_LOOP
    TXA
    CLC
    ADC START_Y
    TAY
    LDA HGR_LO,Y
    CLC
    ADC COL_OFFSET
    STA PTR_LO
    LDA HGR_HI,Y
    ADC #$00
    STA PTR_HI

    JSR RECV_BYTE
    STA TEMP_BYTE
    LDY #$00
    LDA DRAW_MODE
    BEQ DOG_STORE_B0
    CMP #1
    BEQ DOG_OR_B0
    ; XOR mode, as DRAW_MODE 2 in the cache path
    LDA TEMP_BYTE
    AND #$7F
    BEQ DOG_DO_B1
    EOR (PTR_LO),Y
    BIT TEMP_BYTE
    BPL DOG_XOR_B0_ST
    ORA #$80
DOG_XOR_B0_ST
    STA (PTR_LO),Y
    JMP DOG_DO_B1
DOG_OR_B0
    ; Overlay mode, as DRAW_OR_B0. The background palette bit stays
    ; unless the glyph draws in this byte.
    LDA TEMP_BYTE
    AND #$7F
    BEQ DOG_DO_B1
    LDA (PTR_LO),Y
    ORA TEMP_BYTE
    STA (PTR_LO),Y
    JMP DOG_DO_B1
DOG_STORE_B0
    ; Replace mode
    LDA TEMP_BYTE
    STA (PTR_LO),Y

DOG_DO_B1
    JSR RECV_BYTE
    STA TEMP_BYTE
    LDY #$01
    LDA DRAW_MODE
    BEQ DOG_STORE_B1
    CMP #1
    BEQ DOG_OR_B1
    ; XOR mode, as DRAW_MODE 2 in the cache path
    LDA TEMP_BYTE
    AND #$7F
    BEQ DOG_NEXT_ROW
    EOR (PTR_LO),Y
    BIT TEMP_BYTE
    BPL DOG_XOR_B1_ST
    ORA #$80
DOG_XOR_B1_ST
    STA (PTR_LO),Y
    JMP DOG_NEXT_ROW
DOG_OR_B1
    ; Overlay mode, as DRAW_OR_B0
    LDA TEMP_BYTE
    AND #$7F
    BEQ DOG_NEXT_ROW
    LDA (PTR_LO),Y
    ORA TEMP_BYTE
    STA (PTR_LO),Y
    JMP DOG_NEXT_ROW
DOG_STORE_B1
    ; Replace mode
    LDA TEMP_BYTE
    STA (PTR_LO),Y

DOG_NEXT_ROW
    INX
    CPX #16
    BEQ DOG_RET
    JMP GLYPH_ROW_LOOP
DOG_RET
    RTS

CLEAR_HGR
    LDA #$00
    STA CUR_COL
    STA CUR_ROW
    LDA #$20
    STA PTR_HI
    LDA #$00
    STA PTR_LO
    TAY
    LDA #$00
CLR_LOOP
    STA (PTR_LO),Y
    INY
    BNE CLR_LOOP
    INC PTR_HI
    LDX PTR_HI
    CPX #$40
    BNE CLR_LOOP
    RTS

SCROLL_HGR
    LDX #$00
SCROLL_LINE
    TXA
    CLC
    ADC #16
    TAY
    LDA HGR_LO,Y
    STA SRC_LO
    LDA HGR_HI,Y
    STA SRC_HI

    LDA HGR_LO,X
    STA PTR_LO
    LDA HGR_HI,X
    STA PTR_HI

    LDY #39
COPY_40
    LDA (SRC_LO),Y
    STA (PTR_LO),Y
    DEY
    BPL COPY_40

    INX
    CPX #176
    BNE SCROLL_LINE

CLEAR_BOTTOM
    LDA HGR_LO,X
    STA PTR_LO
    LDA HGR_HI,X
    STA PTR_HI
    LDA #0
    LDY #39
CLR_40
    STA (PTR_LO),Y
    DEY
    BPL CLR_40
    INX
    CPX #192
    BNE CLEAR_BOTTOM
    RTS

SEND_BYTE
    PHA
SEND_SERIAL
    LDA ACIA_STAT
    AND #$10
    BEQ SEND_SERIAL
    PLA
    STA ACIA_DATA
    RTS

RECV_BYTE
    LDA ACIA_STAT
    AND #$08
    BEQ RECV_BYTE
    LDA ACIA_DATA
    RTS

; --- Font cache from the cassette input ---
; & "/TAPE" reads two records in the standard Apple II cassette format
; with the monitor READ routine. The first is 3 bytes, the length of the
; cache and its checksum ($FF exclusive-ored with each byte), the second
; the cache itself, put at $6000. Each record is a leader of at least 4
; seconds, a sync bit, the bytes and their checksum
; (tools/audio_font_streamer.py writes it as a WAV file, or sends it to an
; emulator). READ prints ERR on a bad record but tells the caller nothing,
; so the cache is checked here, and dropped if it does not match, so that
; & strings never draw from a damaged one.
MON_READ        = $FEFD
MON_A1L         = $3C
MON_A2L         = $3E

TAPE_LOAD
    LDA #<TAPE_LEN
    STA MON_A1L
    LDA #>TAPE_LEN
    STA MON_A1L+1
    LDA #<(TAPE_LEN+2)
    STA MON_A2L
    LDA #>(TAPE_LEN+2)
    STA MON_A2L+1
    LDX #$00
    JSR MON_READ
    ; 1 to 9215 bytes (255 glyphs need 9184) fit below HIMEM
    LDA TAPE_LEN+1
    CMP #$24
    BCS TAPE_BAD
    ORA TAPE_LEN
    BEQ TAPE_BAD
    ; $6000 to $6000 + length - 1
    LDA #$00
    STA MON_A1L
    LDA #$60
    STA MON_A1L+1
    CLC
    LDA TAPE_LEN
    ADC #$FF
    STA MON_A2L
    LDA TAPE_LEN+1
    ADC #$5F
    STA MON_A2L+1
    LDX #$00
    JSR MON_READ
    ; Check the cache against the checksum from the first record
    LDA #$00
    STA PTR_LO
    LDA #$60
    STA PTR_HI
    LDA TAPE_LEN
    STA SRC_LO          ; bytes left
    LDA TAPE_LEN+1
    STA SRC_HI
    LDA #$FF
    STA TEMP_BYTE
    LDY #$00
TAPE_SUM
    LDA (PTR_LO),Y
    EOR TEMP_BYTE
    STA TEMP_BYTE
    INC PTR_LO
    BNE TAPE_SUM_NEXT
    INC PTR_HI
TAPE_SUM_NEXT
    LDA SRC_LO
    BNE TAPE_SUM_DEC
    DEC SRC_HI
TAPE_SUM_DEC
    DEC SRC_LO
    LDA SRC_LO
    ORA SRC_HI
    BNE TAPE_SUM
    LDA TEMP_BYTE
    CMP TAPE_LEN+2
    BNE TAPE_BAD
    RTS
TAPE_BAD
    LDA #$00
    STA $6000           ; no HG mark, so the cache is not used
    RTS

TAPE_LEN   .byte 0, 0, 0    ; length and checksum, from the first record

SAVE_X     .byte 0
SAVE_Y     .byte 0
SAVE_CNT   .byte 0
BUF_HEAD   .byte 0
BUF_TAIL   .byte 0
COLOR_MASK_0 .byte $00, $2A, $55, $7F, $00, $2A, $55, $7F
COLOR_MASK_1 .byte $00, $55, $2A, $7F, $00, $55, $2A, $7F
COLOR_HB     .byte $00, $00, $00, $00, $80, $80, $80, $80
BUF_START  .dsb 256, 0
IME_SHOWN   .byte 0
IME_ESCS    .byte 0
IME_OLDMODE .byte 0
IME_LINE    .byte 0
IME_SAVE    .dsb 1280, 0
CACHE_OK    .byte 0             ; the $6000 cache is loaded (this & statement)
HD_ON       .byte 0             ; draw from the font file (this & statement)
HD_REF      .byte 0             ; its ProDOS reference number, 0 = closed
CP_LO       .byte 0
CP_HI       .byte 0
HD_PFX_PARMS    .byte 1
                .word HD_FPATH
HD_ONLINE_PARMS .byte 2, 0
                .word HD_FPATH+1
HD_FPATH    .dsb 65, 0          ; length byte, then the absolute pathname
HD_OPEN_PARMS   .byte 3
                .word HD_FPATH
                .word 0         ; the file buffer, from GETBUFR at INIT
HD_OPEN_REF     .byte 0
HD_MARK_PARMS   .byte 2, 0
HD_MARK_POS     .byte 0, 0, 0
HD_READ_PARMS   .byte 4, 0
                .word HD_GLYPH
                .word 32
                .word 0
HD_CLOSE_PARMS  .byte 1, 0
HD_GLYPH    .dsb 32, 0
; Onboard input line
OB_SCOL     .byte 0
OB_SROW     .byte 0
OB_SCLR     .byte 0
OB_OK       .byte 0
OB_K        .byte 0
OB_KK       .byte 0
OB_J        .byte 0
OB_LANG     .byte 0             ; 0 Hangul, 1 A, kept between lines
OB_CAPS     .byte 0
SL_CNT      .byte 0, 0, 0       ; jamo in the lead, vowel and tail slots
SL_J        .byte 0, 0, 0, 0, 0, 0
OB_NJ       .byte 0             ; jamo of the syllable, in typing order
OB_ORDER    .dsb 6, 0
OB_KEYS     .dsb 6, 0
OB_TK       .dsb 6, 0
OB_TN       .byte 0
OB_TI       .byte 0
OB_AS       .byte 0
OB_AJ       .byte 0
OB_AK       .byte 0
OB_MJ       .byte 0
OB_MK       .byte 0
OB_PA       .byte 0
OB_PB       .byte 0
OB_V        .byte 0
OB_JONG     .byte 0
OB_NL       .byte 0
OB_NH       .byte 0
OB_ML       .byte 0
OB_MH       .byte 0
OB_NU       .byte 0             ; committed characters
OB_UL       .dsb 80, 0
OB_UH       .dsb 80, 0
OB_VIEW     .byte 0
OB_L        .byte 0
OB_I        .byte 0
OB_I2       .byte 0
OB_T        .byte 0
OB_COL      .byte 0
OB_ROW      .byte 0
OB_STY      .byte 0
OB_WRITE    .byte 0
OB_LEN      .byte 0
OB_RUN      .byte 0
DR_L        .dsb 40, 0          ; what each cell of rows 9 and 8 shows
DR_H        .dsb 40, 0
DR_S        .dsb 40, 0
CAND_ON     .byte 0
CAND_SRC    .byte 0             ; 0 the syllable composed, 1 the one before
CAND_CNT    .byte 0
CAND_OFF    .byte 0, 0
CAND_FIRST  .byte 0
CAND_N      .byte 0
CAND_HDR    .byte 0, 0, 0, 0
CAND_CP     .dsb 18, 0

HGR_LO
.byte $00, $00, $00, $00, $00, $00, $00, $00, $80, $80, $80, $80, $80, $80, $80, $80
.byte $00, $00, $00, $00, $00, $00, $00, $00, $80, $80, $80, $80, $80, $80, $80, $80
.byte $00, $00, $00, $00, $00, $00, $00, $00, $80, $80, $80, $80, $80, $80, $80, $80
.byte $00, $00, $00, $00, $00, $00, $00, $00, $80, $80, $80, $80, $80, $80, $80, $80
.byte $28, $28, $28, $28, $28, $28, $28, $28, $A8, $A8, $A8, $A8, $A8, $A8, $A8, $A8
.byte $28, $28, $28, $28, $28, $28, $28, $28, $A8, $A8, $A8, $A8, $A8, $A8, $A8, $A8
.byte $28, $28, $28, $28, $28, $28, $28, $28, $A8, $A8, $A8, $A8, $A8, $A8, $A8, $A8
.byte $28, $28, $28, $28, $28, $28, $28, $28, $A8, $A8, $A8, $A8, $A8, $A8, $A8, $A8
.byte $50, $50, $50, $50, $50, $50, $50, $50, $D0, $D0, $D0, $D0, $D0, $D0, $D0, $D0
.byte $50, $50, $50, $50, $50, $50, $50, $50, $D0, $D0, $D0, $D0, $D0, $D0, $D0, $D0
.byte $50, $50, $50, $50, $50, $50, $50, $50, $D0, $D0, $D0, $D0, $D0, $D0, $D0, $D0
.byte $50, $50, $50, $50, $50, $50, $50, $50, $D0, $D0, $D0, $D0, $D0, $D0, $D0, $D0

HGR_HI
.byte $20, $24, $28, $2C, $30, $34, $38, $3C, $20, $24, $28, $2C, $30, $34, $38, $3C
.byte $21, $25, $29, $2D, $31, $35, $39, $3D, $21, $25, $29, $2D, $31, $35, $39, $3D
.byte $22, $26, $2A, $2E, $32, $36, $3A, $3E, $22, $26, $2A, $2E, $32, $36, $3A, $3E
.byte $23, $27, $2B, $2F, $33, $37, $3B, $3F, $23, $27, $2B, $2F, $33, $37, $3B, $3F
.byte $20, $24, $28, $2C, $30, $34, $38, $3C, $20, $24, $28, $2C, $30, $34, $38, $3C
.byte $21, $25, $29, $2D, $31, $35, $39, $3D, $21, $25, $29, $2D, $31, $35, $39, $3D
.byte $22, $26, $2A, $2E, $32, $36, $3A, $3E, $22, $26, $2A, $2E, $32, $36, $3A, $3E
.byte $23, $27, $2B, $2F, $33, $37, $3B, $3F, $23, $27, $2B, $2F, $33, $37, $3B, $3F
.byte $20, $24, $28, $2C, $30, $34, $38, $3C, $20, $24, $28, $2C, $30, $34, $38, $3C
.byte $21, $25, $29, $2D, $31, $35, $39, $3D, $21, $25, $29, $2D, $31, $35, $39, $3D
.byte $22, $26, $2A, $2E, $32, $36, $3A, $3E, $22, $26, $2A, $2E, $32, $36, $3A, $3E
.byte $23, $27, $2B, $2F, $33, $37, $3B, $3F, $23, $27, $2B, $2F, $33, $37, $3B, $3F
