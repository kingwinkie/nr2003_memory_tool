#!/usr/bin/env python3
"""
Live Memory Reader/Writer for NR2003 under Wine
Uses runtime addresses calculated from EXE RVAs.

Formula: Runtime Address = Module Base + RVA - 1
"""

import sys
import csv
import os
from pathlib import Path
import ctypes
from ctypes import wintypes

kernel32 = ctypes.windll.kernel32

PROCESS_ALL_ACCESS = 0x1F0FFF
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008

kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]

kernel32.ReadProcessMemory.restype = wintypes.BOOL
kernel32.ReadProcessMemory.argtypes = [
    wintypes.HANDLE,
    wintypes.LPCVOID,
    wintypes.LPVOID,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]

kernel32.WriteProcessMemory.restype = wintypes.BOOL
kernel32.WriteProcessMemory.argtypes = [
    wintypes.HANDLE,
    wintypes.LPCVOID,
    wintypes.LPCVOID,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]

kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


class LiveMemoryIO:
    def __init__(self):
        self.handle = None
        self.pid = None
        self.module_base = None
        self.address_map = {}
        self.address_offset = -1

    def find_process(self):
        import subprocess

        result = subprocess.run(
            ["winedbg", "--command", "info proc"], capture_output=True, text=True
        )
        for line in result.stdout.split("\n"):
            if "nr2003" in line.lower():
                parts = line.split()
                if parts:
                    self.pid = int(parts[0], 16)
                    return True
        return False

    def get_module_base(self):
        self.module_base = 0x400000
        return self.module_base

    def open_process(self, write_access=False):
        if not self.pid:
            if not self.find_process():
                return False
        access = (
            PROCESS_ALL_ACCESS
            if write_access
            else (PROCESS_VM_READ | PROCESS_VM_OPERATION)
        )
        self.handle = kernel32.OpenProcess(access, False, self.pid)
        return self.handle is not None and self.handle != 0

    def close_process(self):
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None

    def load_addresses(self):
        addr_file = Path(__file__).parent / "addresses.csv"
        if not addr_file.exists():
            print(f"Error: {addr_file} not found")
            return False

        with open(addr_file, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    rva_str = row.get("RVA", "")
                    if rva_str.startswith("0x"):
                        rva = int(rva_str, 16)
                    else:
                        continue
                    module = row.get("Module", "Unknown")
                    key = (module, row.get("Label", "???"), rva)
                    self.address_map[key] = {
                        "rva": rva,
                        "type": row.get("Type", "Sing"),
                        "label": row.get("Label", "???"),
                        "module": module,
                        "original": row.get("EXE_Value", row.get("Original", "")),
                    }
                except (ValueError, KeyError):
                    continue

        print(f"Loaded {len(self.address_map)} addresses")
        return True

    def get_runtime_address(self, rva):
        if not self.module_base:
            self.get_module_base()
        if self.module_base:
            return self.module_base + rva + self.address_offset
        return None

    def read_float(self, address):
        buffer = ctypes.c_float()
        bytes_read = ctypes.c_size_t()
        success = kernel32.ReadProcessMemory(
            self.handle,
            ctypes.c_void_p(address),
            ctypes.byref(buffer),
            4,
            ctypes.byref(bytes_read),
        )
        return buffer.value if success else None

    def write_float(self, address, value):
        buffer = ctypes.c_float(value)
        bytes_written = ctypes.c_size_t()
        success = kernel32.WriteProcessMemory(
            self.handle,
            ctypes.c_void_p(address),
            ctypes.byref(buffer),
            4,
            ctypes.byref(bytes_written),
        )
        return success

    def read_all_values(self, module_filter=None):
        values = {}
        for key, info in self.address_map.items():
            module = info["module"]
            if module_filter and module.lower() != module_filter.lower():
                continue
            rva = info["rva"]
            runtime = self.get_runtime_address(rva)
            if runtime:
                value = self.read_float(runtime)
                if value is not None:
                    if module not in values:
                        values[module] = []
                    values[module].append(
                        {
                            "rva": rva,
                            "runtime": runtime,
                            "label": info["label"],
                            "value": value,
                            "original": info.get("original", ""),
                            "type": info["type"],
                        }
                    )
        return values


def write_csv(output_path, module, values):
    filepath = output_path / f"{module.lower()}.csv"
    fieldnames = [
        "RVA",
        "Runtime",
        "Type",
        "Label",
        "Original",
        "EXE_Value",
        "CurrentValue",
    ]
    rows = []
    for v in values:
        rows.append(
            {
                "RVA": hex(v["rva"]),
                "Runtime": hex(v["runtime"]),
                "Type": v["type"],
                "Label": v["label"],
                "Original": v["original"],
                "EXE_Value": v["original"],
                "CurrentValue": v["value"],
            }
        )
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {filepath} ({len(rows)} entries)")


def main():
    print("NR2003 Live Memory I/O")
    print("=" * 40)

    if len(sys.argv) < 2:
        print("Commands:")
        print("  read [module] [output_path]")
        print("  write <input.csv>")
        print("  set <RVA> <value>")
        print()
        print("Modules: chassis, engine, wheel, all (default)")
        print("Output: folder path (default: current folder)")
        print()
        print("Examples:")
        print("  wine python live_memory_io.py read")
        print("  wine python live_memory_io.py read chassis")
        print("  wine python live_memory_io.py read chassis my_data/")
        print("  wine python live_memory_io.py read all output/")
        return

    command = sys.argv[1].lower()
    module_filter = None
    output_path = Path(".")

    if len(sys.argv) >= 3:
        arg2 = sys.argv[2].lower()
        if arg2 in ["chassis", "engine", "wheel"]:
            module_filter = arg2.capitalize()
            if len(sys.argv) >= 4:
                output_path = Path(sys.argv[3])
        elif arg2 == "all":
            if len(sys.argv) >= 4:
                output_path = Path(sys.argv[3])
        else:
            output_path = Path(sys.argv[2])

    io = LiveMemoryIO()

    if not io.find_process():
        print("Could not find NR2003.exe process")
        return

    print(f"PID: {io.pid}, Module base: 0x{io.module_base or 0x400000:X}")

    if not io.load_addresses():
        return

    if command == "read":
        if not io.open_process(write_access=False):
            print("Could not open process")
            return

        values = io.read_all_values(module_filter)

        output_str = str(output_path)
        if output_str != "." and output_str != "":
            os.makedirs(output_path, exist_ok=True)
            print(f"Output folder: {output_path}")

        for module, vals in values.items():
            print(f"\n{module} ({len(vals)} values):")
            for v in vals[:5]:
                print(f"  0x{v['rva']:X}: {v['label']} = {v['value']}")
            if len(vals) > 5:
                print(f"  ... and {len(vals) - 5} more")
            write_csv(output_path, module, vals)

    elif command == "write":
        if len(sys.argv) < 3:
            print("Usage: live_memory_io.py write <input.csv>")
            return
        input_file = sys.argv[2]
        if not io.open_process(write_access=True):
            print("Could not open process for writing")
            return
        with open(input_file, "r") as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                rva_str = row.get("RVA", "")
                if rva_str.startswith("0x"):
                    rva = int(rva_str, 16)
                    new_value = float(row.get("NewValue", row.get("CurrentValue", 0)))
                    runtime = io.get_runtime_address(rva)
                    if runtime and io.write_float(runtime, new_value):
                        count += 1
                        print(f"Wrote 0x{rva:X}: {new_value}")
        print(f"Wrote {count} values")

    elif command == "set":
        if len(sys.argv) < 4:
            print("Usage: live_memory_io.py set <RVA> <value>")
            return
        rva = int(sys.argv[2], 16)
        new_value = float(sys.argv[3])
        if not io.open_process(write_access=True):
            print("Could not open process for writing")
            return
        runtime = io.get_runtime_address(rva)
        if io.write_float(runtime, new_value):
            print(f"Wrote 0x{rva:X}: {new_value}")
        else:
            print("Write failed")

    io.close_process()


if __name__ == "__main__":
    main()
