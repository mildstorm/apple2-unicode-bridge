; HANGUL.S - Apple II Super Serial Card (SSC) Hangul Terminal Client
; Assembled with xa for 6502

    * = $4000

KBD         = $C000
KBDSTRB     = $C010
TXTCLR      = $C050
TXTSET      = $C051
MIXCLR      = $C052
PAGE1       = $C054
HIRES       = $C057

ACIA_DATA   = $C0A8
ACIA_STAT   = $C0A9
ACIA_CMD    = $C0AA
ACIA_CTRL   = $C0AB

PTR_LO      = $06
PTR_HI      = $07
COL_OFFSET  = $08
START_Y     = $09
SRC_LO      = $0A
SRC_HI      = $0B

MAIN:
    ; 1. Initialize SSC (Slot 2)
    LDA #$00
    STA ACIA_STAT   ; Reset ACIA
    LDA #$1E        ; 9600 baud, 8-N-1
    STA ACIA_CTRL
    LDA #$0B        ; No parity, Rx enabled, DTR/RTS low
    STA ACIA_CMD

    ; 2. Initialize HGR screen
    STA TXTCLR      ; Graphics mode
    STA HIRES       ; Hi-res
    STA PAGE1       ; Page 1 ($2000-$3FFF)
    STA MIXCLR      ; Full screen graphics (no text window)

    JSR CLEAR_HGR

    ; Send ready handshake byte ($AA) to PC
    LDA #$AA
    JSR SEND_BYTE

    ; 3. Main Event Loop
EVENT_LOOP:
    ; Check keyboard on Apple II
    LDA KBD
    BPL CHECK_SERIAL
    STA KBDSTRB     ; Clear strobe
    AND #$7F        ; 7-bit ASCII
    CMP #$1B        ; ESC key?
    BEQ EXIT_TERM
    JSR SEND_BYTE   ; Send key to PC

CHECK_SERIAL:
    LDA ACIA_STAT
    AND #$08        ; Bit 3 = Rx Full?
    BEQ EVENT_LOOP

    ; Byte received from PC!
    LDA ACIA_DATA

    ; Dispatch command
    CMP #$81        ; CMD_DRAW_GLYPH
    BEQ DO_DRAW
    CMP #$82        ; CMD_CLEAR
    BEQ DO_CLEAR
    CMP #$83        ; CMD_EXIT
    BEQ EXIT_TERM
    CMP #$84        ; CMD_SCROLL
    BEQ DO_SCROLL
    JMP EVENT_LOOP

DO_CLEAR:
    JSR CLEAR_HGR
    JMP EVENT_LOOP

DO_SCROLL:
    JSR SCROLL_HGR
    JMP EVENT_LOOP

EXIT_TERM:
    STA TXTSET      ; Restore 40-column text mode
    RTS

DO_DRAW:
    JSR GET_BYTE    ; COL (0..19)
    ASL             ; COL * 2
    STA COL_OFFSET

    JSR GET_BYTE    ; ROW (0..11)
    ASL
    ASL
    ASL
    ASL             ; ROW * 16 (0..176)
    STA START_Y

    LDX #$00        ; Scanline offset (0..15)
ROW_LOOP:
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

    JSR GET_BYTE    ; Byte 0 of row
    LDY #$00
    STA (PTR_LO),Y

    JSR GET_BYTE    ; Byte 1 of row
    INY
    STA (PTR_LO),Y

    INX
    CPX #16
    BNE ROW_LOOP

    JMP EVENT_LOOP

; Subroutines
GET_BYTE:
    LDA ACIA_STAT
    AND #$08
    BEQ GET_BYTE
    LDA ACIA_DATA
    RTS

SEND_BYTE:
    PHA
WAIT_TX:
    LDA ACIA_STAT
    AND #$10        ; Bit 4 = Tx Empty?
    BEQ WAIT_TX
    PLA
    STA ACIA_DATA
    RTS

CLEAR_HGR:
    LDA #$20
    STA PTR_HI
    LDA #$00
    STA PTR_LO
    TAY
    LDA #$00
CLR_LOOP:
    STA (PTR_LO),Y
    INY
    BNE CLR_LOOP
    INC PTR_HI
    LDX PTR_HI
    CPX #$40
    BNE CLR_LOOP
    RTS

SCROLL_HGR:
    LDX #$00
SCROLL_LINE:
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
COPY_40:
    LDA (SRC_LO),Y
    STA (PTR_LO),Y
    DEY
    BPL COPY_40

    INX
    CPX #176
    BNE SCROLL_LINE

CLEAR_BOTTOM:
    LDA HGR_LO,X
    STA PTR_LO
    LDA HGR_HI,X
    STA PTR_HI
    LDA #0
    LDY #39
CLR_40:
    STA (PTR_LO),Y
    DEY
    BPL CLR_40

    INX
    CPX #192
    BNE CLEAR_BOTTOM
    RTS

; HGR Line Address Tables (192 lines)
HGR_LO:
#include "hgr_lo.inc"

HGR_HI:
#include "hgr_hi.inc"
