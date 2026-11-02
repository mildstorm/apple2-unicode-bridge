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

TAPEIN          = $C060
TAPEOUT         = $C020

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
IO_MODE         = $20
AUD_LASTIN      = $21
AUD_TIMEY       = $22
AUD_BITCNT      = $23
AUD_VAL         = $24
AUD_CHK         = $25
HCOLOR_FLG      = $E4
HGR_HAS_DRAWN   = $F9

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
    STA IO_MODE
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

    LDA #<MY_KEYIN
    STA KSW_LO
    STA DOS_KSW_LO
    LDA #>MY_KEYIN
    STA KSW_HI
    STA DOS_KSW_HI

    JSR CLEAR_HGR
    LDA #$00
    STA HGR_HAS_DRAWN
    RTS

AMPERSAND_HANDLER
    CMP #'"'
    BEQ RUN_AMP_STRING

    JSR CHRGET
    CMP #'"'
    BEQ RUN_AMP_STRING

    JMP RUN_TERMINAL_MODE

RUN_AMP_STRING
    STA TXTCLR
    STA HIRES
    STA PAGE1
    STA MIXSET

    ; Sync CUR_COLOR from Applesoft HCOLOR ($E4) if user called HCOLOR=
    JSR SYNC_HCOLOR

    ; Check if Cache is valid at $6000 ('H','G')
    LDA $6000
    CMP #'H'
    BNE NO_LOCAL_CACHE
    LDA $6001
    CMP #'G'
    BEQ RUN_OFFLINE_STRING

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
    BNE SKIP_CHAR
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
    BNE HSC_CHECK_AUD
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

HSC_CHECK_AUD
    CMP #'a'            ; /audio or /aud?
    BNE HSC_CHECK_SER
    LDA #1
    STA IO_MODE
    JMP SKIP_SLASH_TO_END

HSC_CHECK_SER
    CMP #'s'            ; /serial or /ser?
    BNE SKIP_SLASH_TO_END
    LDA #0
    STA IO_MODE
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
    ; Parse Byte 1
    INC TXTPTR_LO
    BNE HEX_ADV_3
    INC TXTPTR_HI
HEX_ADV_3
    LDY #0
    LDA (TXTPTR_LO),Y
    JSR CHAR_TO_NIBBLE
    ASL
    ASL
    ASL
    ASL
    STA TEMP_BYTE
    INC TXTPTR_LO
    BNE HEX_ADV_4
    INC TXTPTR_HI
HEX_ADV_4
    LDY #0
    LDA (TXTPTR_LO),Y
    JSR CHAR_TO_NIBBLE
    ORA TEMP_BYTE
    STA KEY_1

    ; Parse Byte 2
    INC TXTPTR_LO
    BNE HEX_ADV_5
    INC TXTPTR_HI
HEX_ADV_5
    LDY #0
    LDA (TXTPTR_LO),Y
    JSR CHAR_TO_NIBBLE
    ASL
    ASL
    ASL
    ASL
    STA TEMP_BYTE
    INC TXTPTR_LO
    BNE HEX_ADV_6
    INC TXTPTR_HI
HEX_ADV_6
    LDY #0
    LDA (TXTPTR_LO),Y
    JSR CHAR_TO_NIBBLE
    ORA TEMP_BYTE
    STA KEY_2

    ; Draw glyph from cache
    JSR DRAW_CACHED_GLYPH

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

DRAW_CACHED_GLYPH
    LDA $6002
    BNE DCG_HAS_ITEMS
    RTS
DCG_HAS_ITEMS
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
    RTS

FOUND_CACHE_SLOT
    LDA CACHE_PTR_LO
    CLC
    ADC #4
    STA SRC_LO
    LDA CACHE_PTR_HI
    ADC #0
    STA SRC_HI

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
    ; XOR mode (DRAW_MODE == 2)
    LDA TEMP_B0
    AND #$7F
    EOR (PTR_LO),Y
    STA (PTR_LO),Y
    JMP DRAW_DO_B1
DRAW_OR_B0
    ; Overlay mode (DRAW_MODE == 1)
    LDA (PTR_LO),Y
    AND #$7F
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
    ; XOR mode (DRAW_MODE == 2)
    LDA TEMP_B1
    AND #$7F
    EOR (PTR_LO),Y
    STA (PTR_LO),Y
    JMP CACHE_NEXT_ROW
DRAW_OR_B1
    ; Overlay mode (DRAW_MODE == 1)
    LDA (PTR_LO),Y
    AND #$7F
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

HANDLE_CTRL_K
    STX SAVE_X
    STY SAVE_Y
    LDA #$0B
    JSR SEND_BYTE

WAIT_FOR_PC_INPUT
    LDA ACIA_STAT
    AND #$08
    BNE READ_INPUT_CMD

    LDA KBD
    BPL WAIT_FOR_PC_INPUT
    STA KBDSTRB
    AND #$7F
    CMP #$1B
    BEQ CANCEL_PC_INPUT
    JMP WAIT_FOR_PC_INPUT

READ_INPUT_CMD
    LDA ACIA_DATA
    CMP #$86
    BNE WAIT_FOR_PC_INPUT

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
    LDX SAVE_X
    LDY SAVE_Y
    JMP READ_KBD

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

TERM_LOOP
    LDA KBD
    BPL CHECK_RX
    STA KBDSTRB
    AND #$7F
    CMP #$1B
    BEQ EXIT_TERM
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

EXIT_TERM
    STA TXTSET
    JSR CHRGET
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
    ; XOR mode
    LDA TEMP_BYTE
    AND #$7F
    EOR (PTR_LO),Y
    STA (PTR_LO),Y
    JMP DOG_DO_B1
DOG_OR_B0
    ; Overlay mode
    LDA (PTR_LO),Y
    AND #$7F
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
    ; XOR mode
    LDA TEMP_BYTE
    AND #$7F
    EOR (PTR_LO),Y
    STA (PTR_LO),Y
    JMP DOG_NEXT_ROW
DOG_OR_B1
    ; Overlay mode
    LDA (PTR_LO),Y
    AND #$7F
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
    BNE GLYPH_ROW_LOOP
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
    LDA IO_MODE
    BEQ SEND_SERIAL
    ; Audio mode - no feedback needed for font streaming, toggle speaker/tapeout
    STA TAPEOUT
    PLA
    RTS
SEND_SERIAL
    LDA ACIA_STAT
    AND #$10
    BEQ SEND_SERIAL
    PLA
    STA ACIA_DATA
    RTS

RECV_BYTE
    LDA IO_MODE
    BNE AUD_RECV_BYTE
RECV_SERIAL
    LDA ACIA_STAT
    AND #$08
    BEQ RECV_SERIAL
    LDA ACIA_DATA
    RTS

; --- ADTPro Audio / Cassette Protocol Receiver ---
; Standard Apple II Audio FSK demodulator compatible with ADTPro BytesToWav
; Leader 770 Hz, Sync 2000-2200 Hz, 0-bit 2000 Hz, 1-bit 1000 Hz

AUD_RECV_BYTE
    LDA #$08
    STA AUD_BITCNT
AUD_BIT_LOOP
    LDA #$FF
    STA AUD_TIMEY
    JSR AUD_RD2BIT
    ROL AUD_VAL
    DEC AUD_BITCNT
    BNE AUD_BIT_LOOP
    LDA AUD_VAL
    RTS

AUD_RD2BIT
    JSR AUD_RDBIT
AUD_RDBIT
    DEC AUD_TIMEY
    BEQ AUD_TMOT
    LDA KBD
    BPL AUD_NO_KBD
    STA KBDSTRB
    CMP #$9B            ; ESC key to cancel
    BEQ AUD_ESC
AUD_NO_KBD
    DEY
    LDA TAPEIN
    EOR AUD_LASTIN
    BPL AUD_RDBIT
    EOR AUD_LASTIN
    STA AUD_LASTIN
    CPY #$80            ; Carry set if Y >= $80 (1000 Hz, '1'), clear if Y < $80 (2000 Hz, '0')
    RTS

AUD_TMOT
    CLC
    RTS
AUD_ESC
    PLA
    PLA
    RTS

SAVE_X     .byte 0
SAVE_Y     .byte 0
SAVE_CNT   .byte 0
BUF_HEAD   .byte 0
BUF_TAIL   .byte 0
COLOR_MASK_0 .byte $00, $2A, $55, $7F, $00, $2A, $55, $7F
COLOR_MASK_1 .byte $00, $55, $2A, $7F, $00, $55, $2A, $7F
COLOR_HB     .byte $00, $00, $00, $00, $80, $80, $80, $80
BUF_START  .dsb 256, 0

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
