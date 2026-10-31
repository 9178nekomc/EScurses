import sys
import os
if os.name == 'posix':
    import termios, tty, select
if os.name == 'nt':
    import msvcrt

_screen = []
_screenWidth = None
_screenHeight = None

def linuxTerminalCheck():
    isTTY = os.isatty(sys.stdin.fileno())
    return isTTY

def getTerminalSize():
    scrSize = os.get_terminal_size()
    maxX = scrSize.columns
    maxY = scrSize.lines
    return (maxX, maxY)

def initGame():
    scrSize = getTerminalSize()
    global _screenWidth
    global _screenHeight
    _screenWidth = scrSize[0]
    _screenHeight = scrSize[1]
    global _screen
    _screen = []
    for i in range(_screenHeight):
        _screen.append([[] for i in range(_screenWidth)])
def clear():
    sys.stdout.write('\033[2J')

def drawChar(x, y, char):
    _screen[y-1][x-1] = (char, y, x)

def getch(nodelay=True):
    if os.name == 'nt':
        if nodelay:
            if msvcrt.kbhit():
                ch = msvcrt.getwch()
                return ch
            return None
        elif not nodelay:
            ch = msvcrt.getwch()
            return ch
    elif os.name == 'posix':
        if nodelay:
            fd = sys.stdin.fileno()
            oldSettings = termios.tcgetattr(fd)
            try:
                tty.setcbreak(fd)
                if select.select([fd], [], [], 0):
                    ch = sys.stdin.read(1)
                    return ch
                return None
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, oldSettings)
        elif not nodelay:
            fd = sys.stdin.fileno()
            oldSettings = termios.tcgetattr(fd)
            try: 
                ch = sys.stdin.read(1)
                return ch
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, oldSettings)

def refresh():
    for line in _screen:
        for char in line:
            if char:
                sys.stdout.write(f'\033[{char[1]};{char[2]}H{char[0]}')
    sys.stdout.flush()

def cursorEcho(echo=False):
    if echo:
        sys.stdout.write('\033[?25h')
    if not echo:
        sys.stdout.write('\033[?25l')

def exitGame():
    sys.stdout.write('\033[?25h')
    sys.stdout.write('\033[2J')
    sys.stdout.flush()
    sys.exit()