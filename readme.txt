NR2003 Physics Live Memory Editor
=================================

Reads and writes live physics memory in NASCAR Racing 2003 Season running
under Wine on Linux.

Requirements
------------
- NR2003 running under Wine
- Wine Python with Windows API support (ctypes.windll)

Files
-----
live_memory_io.py   Main script
addresses.csv       Address definitions (required)
readme.txt          This file

Commands
--------
Read all modules to current folder:
    wine python live_memory_io.py read

Read all modules to output folder:
    wine python live_memory_io.py read all my_folder/
    wine python live_memory_io.py read my_folder/

Read specific module:
    wine python live_memory_io.py read chassis
    wine python live_memory_io.py read engine
    wine python live_memory_io.py read wheel

Read specific module to output folder:
    wine python live_memory_io.py read chassis my_folder/

Write single value:
    wine python live_memory_io.py set 0x2EE5D9 3000.0

Write from CSV:
    wine python live_memory_io.py write changes.csv

Input CSV format for write:
    RVA,CurrentValue
    0x2EE5D9,3000.0
    0x2EE5D5,3200.0

    (Also accepts "NewValue" as column name)
    (Use output from read command, edit CurrentValue, then write)

Output Files
------------
Creates chassis.csv, engine.csv, wheel.csv with columns:
RVA, Runtime, Type, Label, Original, EXE_Value, CurrentValue

Address Formula
---------------
Runtime Address = Module Base (0x400000) + RVA - 1

Example Session
---------------
$ wine python live_memory_io.py read all session1/
NR2003 Live Memory I/O
========================================
PID: 32, Module base: 0x400000
Loaded 2732 addresses
Output folder: session1

Chassis (1520 values):
  0x2EE5D9: Net Weight (lbs) = 2600.5
  ...
Wrote session1\chassis.csv (1520 entries)

$ wine python live_memory_io.py set 0x2EE5D9 3000.0
Wrote 0x2EE5D9: 3000.0

Troubleshooting
---------------
"Could not find NR2003.exe process"
  - Make sure game is running: ps aux | grep -i nr2003

"Could not open process"
  - Check Wine process list: winedbg --command "info proc"
  - PID 32 (0x20) is typical
