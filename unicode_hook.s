; HANGUL_HOOK.S - Apple II KSW Multilingual Input Hook
; Direct hardware keyboard read - 100% stable across all Apple II models

    * = $4000

KSW_LO      = $38
KSW_HI      = $39

DOS_KSW_LO  = $AA55
DOS_KSW_HI  = $AA56

ACIA_DATA   = $C0A8
ACIA_STAT   = $C0A9
ACIA_CMD    = $C0AA
ACIA_CTRL   = $C0AB

KBD         = $C000
KBDSTRB     = $C010

INIT
    ; 1. Reset and configure SSC ACIA (Slot 2)
    LDA #$00
    STA ACIA_STAT
    LDA #$1E            ; 9600 baud, 8-N-1
    STA ACIA_CTRL
    LDA #$0B            ; Rx enabled
    STA ACIA_CMD

    ; 2. Clear buffer pointers
    LDA #$00
    STA BUF_HEAD
    STA BUF_TAIL

    ; 3. Hook KSW ($38/$39) and DOS 3.3 persistent vector ($AA55/$AA56)
    LDA #<MY_KEYIN
    STA KSW_LO
    STA DOS_KSW_LO
    LDA #>MY_KEYIN
    STA KSW_HI
    STA DOS_KSW_HI

    RTS

UNHOOK
    LDA #$1B
    STA KSW_LO
    STA DOS_KSW_LO
    LDA #$FD
    STA KSW_HI
    STA DOS_KSW_HI
    RTS

MY_KEYIN
    ; 1. Check if FIFO buffer has bytes from PC
    LDA BUF_HEAD
    CMP BUF_TAIL
    BEQ READ_KBD

    ; Pull next byte from buffer
    LDX BUF_TAIL
    LDA BUF_START,X
    INC BUF_TAIL
    ORA #$80            ; High bit set for Apple II
    RTS

READ_KBD
    ; Direct hardware read from Apple II keyboard ($C000)
    LDA KBD
    BPL READ_KBD
    STA KBDSTRB
    AND #$7F

    CMP #$0B            ; Ctrl+K?
    BEQ HANDLE_CTRL_K

    ; Normal key - set high bit and return to GETLN
    ORA #$80
    RTS

HANDLE_CTRL_K
    ; Send $0B to PC to request multilingual input
    LDA #$0B
    JSR SEND_BYTE

WAIT_FOR_PC
    ; Check if serial data arrived
    LDA ACIA_STAT
    AND #$08
    BNE READ_CMD

    ; Check if user pressed a key on Apple II to cancel (e.g. ESC)
    LDA KBD
    BPL WAIT_FOR_PC
    STA KBDSTRB
    JMP READ_KBD

READ_CMD
    LDA ACIA_DATA
    CMP #$86            ; CMD_INPUT_BYTES
    BNE WAIT_FOR_PC

    ; Read length N
    JSR RECV_BYTE
    TAX
    BEQ EMPTY_INPUT

    ; Read N bytes into FIFO buffer
    LDY #$00
READ_LOOP
    JSR RECV_BYTE
    STA BUF_START,Y
    INY
    DEX
    BNE READ_LOOP

    STY BUF_HEAD
    LDA #$00
    STA BUF_TAIL

    ; Return the first byte
    JMP MY_KEYIN

EMPTY_INPUT
    ; Cancelled: return to reading keyboard
    JMP READ_KBD

SEND_BYTE
    PHA
WAIT_TX
    LDA ACIA_STAT
    AND #$10            ; Tx Empty?
    BEQ WAIT_TX
    PLA
    STA ACIA_DATA
    RTS

RECV_BYTE
    LDA ACIA_STAT
    AND #$08            ; Rx Full?
    BEQ RECV_BYTE
    LDA ACIA_DATA
    RTS

; Internal Data Buffer
BUF_HEAD:   .byte 0
BUF_TAIL:   .byte 0
BUF_START:  .dsb 64, 0
