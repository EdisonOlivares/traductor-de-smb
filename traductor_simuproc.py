"""Lector y traductor conservador de archivos guardados por SimuProc.

El formato .smp no tiene una especificación pública completa. Por eso este
lector conserva cada línea tal como aparece en el archivo y no intenta
reinterpretar palabras cuyo opcode no se pueda verificar.
"""

from __future__ import annotations

import csv
import re
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes


_BINARY = re.compile(r"^[01]+$")
_WORD = re.compile(r"^\d{2}[0-9A-Fa-f]{3}$")
_HEADER_LINES = 3
_OPCODE_WIDTH = 2
_OPERAND_WIDTH = 3
_MEMORY_SIZE = 0x1000


@dataclass(frozen=True)
class MemoryLine:
    """Una línea física y su posición dentro del volcado de memoria."""

    source_line: int
    memory_index: int | None
    kind: str
    raw: str
    translated: str


def read_text(path: Path) -> list[str]:
    """Lee un archivo SimuProc tolerando BOM y archivos antiguos en Windows."""

    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return path.read_text(encoding=encoding).splitlines()
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"No se pudo leer {path}")


def classify(raw: str) -> str:
    value = raw.strip()
    if not value:
        return "empty"
    if value.startswith('"'):
        return "text"
    if _WORD.fullmatch(value):
        return "word"
    if _BINARY.fullmatch(value):
        return "binary"
    return "instruction"


def clean_text(value: str) -> str:
    """Normaliza texto guardado con el ':' fuera de las comillas."""

    value = value.strip()
    if value.startswith('"') and value.endswith('":'):
        return value[:-1]
    return value


def load_opcodes(path: Path) -> dict[str, dict[str, str]]:
    """Carga la tabla CSV que define el significado de cada opcode."""

    try:
        with path.open(encoding="utf-8-sig", newline="") as file:
            rows = csv.DictReader(file)
            required = {"codigo", "nombre", "sintaxis", "descripcion"}
            if not required.issubset(rows.fieldnames or set()):
                missing = ", ".join(sorted(required - set(rows.fieldnames or [])))
                raise ValueError(f"faltan columnas requeridas: {missing}")
            return {
                row["codigo"].zfill(_OPCODE_WIDTH): row
                for row in rows
                if row.get("codigo") and row.get("nombre")
            }
    except OSError as error:
        raise ValueError(
            f"no se pudo leer la tabla de opcodes: {path.name}"
        ) from error


def translate(raw: str, kind: str, opcodes: dict[str, dict[str, str]]) -> str:
    """Traduce palabras de memoria usando la tabla de opcodes."""

    value = raw.strip()
    if kind == "empty":
        return "; vacío"
    if kind == "text":
        return f"DB {clean_text(value)}"
    if kind == "binary":
        return f"DW %{value}"
    if kind == "word":
        opcode = value[:_OPCODE_WIDTH]
        operand = value[_OPCODE_WIDTH : _OPCODE_WIDTH + _OPERAND_WIDTH]
        instruction = opcodes.get(opcode)
        if instruction is None:
            return f"DW {value}"
        syntax = instruction["sintaxis"].strip()
        takes_operand = any(
            marker in syntax.lower() for marker in ("mem", "[", "registro", "destino")
        )
        if not takes_operand or operand == "000":
            return instruction["nombre"]
        return f"{instruction['nombre']} {operand}"
    if kind == "instruction" and value.startswith(("80", "81")):
        opcode = value[:_OPCODE_WIDTH]
        instruction = opcodes.get(opcode)
        if instruction is not None and "," in value:
            return f"{instruction['nombre']} {value[2:]}"
    return value


def parse_lines(
    lines: Iterable[str], opcodes: dict[str, dict[str, str]]
) -> list[MemoryLine]:
    records: list[MemoryLine] = []
    for source_line, raw in enumerate(lines, start=1):
        # Cada línea después de la cabecera representa una posición de
        # memoria, incluso cuando está vacía.
        kind = "header" if source_line <= _HEADER_LINES else classify(raw)
        record_memory_index = (
            None if kind == "header" else source_line - _HEADER_LINES - 1
        )
        if record_memory_index is not None and record_memory_index >= _MEMORY_SIZE:
            raise ValueError("el archivo supera la memoria máxima FFF de SimuProc")
        translated = raw if kind == "header" else translate(raw, kind, opcodes)
        records.append(
            MemoryLine(
                source_line=source_line,
                memory_index=record_memory_index,
                kind=kind,
                raw=raw,
                translated=translated,
            )
        )
    return records


def render(
    records: Iterable[MemoryLine],
    opcodes: dict[str, dict[str, str]],
    include_comments: bool = False,
) -> str:
    """Genera código SimuProc y una sección de datos direccionada."""

    records = list(records)
    output: list[str] = []
    data_records: list[MemoryLine] = []
    halted = False
    last_code_address: int | None = None
    last_data_address: int | None = None

    def add_instruction(line: str, memory_index: int | None = None) -> None:
        nonlocal last_code_address
        if memory_index is not None and (
            last_code_address is None and memory_index != 0
            or last_code_address is not None and memory_index != last_code_address + 1
        ):
            output.append(f"#{memory_index:03X}")
        if include_comments:
            instruction_name = line.split(maxsplit=1)[0].upper()
            description = next(
                (
                    item["descripcion"]
                    for item in opcodes.values()
                    if item["nombre"].upper() == instruction_name
                ),
                "",
            )
            if description:
                line = f"{line} ; {description}"
        output.append(line)
        if memory_index is not None:
            last_code_address = memory_index

    for index, record in enumerate(records):
        if record.kind == "word" and record.translated == "HLT":
            halted = True
            add_instruction(record.translated, record.memory_index)
            continue
        if halted and record.kind == "binary":
            data_records.append(record)
            continue
        if record.kind in {"header", "empty", "binary"}:
            continue
        text_instruction = record.translated in {"MSG", "LDT", "EAP"}
        if text_instruction:
            next_record = records[index + 1] if index + 1 < len(records) else None
            if next_record is not None and next_record.kind == "text":
                add_instruction(f"{record.translated} {clean_text(next_record.raw)}",
                                record.memory_index)
                if next_record.memory_index is not None:
                    last_code_address = next_record.memory_index
                continue
        if record.kind == "text":
            previous = records[index - 1] if index > 0 else None
            if (
                previous is not None
                and previous.kind == "word"
                and previous.translated in {"MSG", "LDT", "EAP"}
            ):
                continue
        add_instruction(record.translated, record.memory_index)

    if data_records:
        output.append("")
        for record in data_records:
            if (
                last_data_address is None
                or record.memory_index != last_data_address + 1
            ):
                output.append(f"#{record.memory_index:03X}")
            output.append(record.raw.strip())
            last_data_address = record.memory_index
    return "\n".join(output) + ("\n" if output else "")


class SimuProcWindow:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Traductor de archivos SimuProc")
        self.root.geometry("850x600")
        self.root.minsize(600, 400)
        self._old_window_proc = None
        self._window_proc = None
        self.current_records: list[MemoryLine] | None = None
        self.current_opcodes: dict[str, dict[str, str]] | None = None
        self.comments_enabled = tk.BooleanVar(value=False)

        toolbar = ttk.Frame(root, padding=8)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Abrir archivo .SMP", command=self.choose_file).pack(
            side="left"
        )
        ttk.Button(toolbar, text="Copiar resultado", command=self.copy_result).pack(
            side="left", padx=(8, 0)
        )
        ttk.Checkbutton(
            toolbar,
            text="Agregar comentarios",
            variable=self.comments_enabled,
            command=self.refresh_result,
        ).pack(side="left", padx=(8, 0))
        self.file_label = ttk.Label(toolbar, text="Arrastra un archivo aquí")
        self.file_label.pack(side="left", padx=12)

        self.text = tk.Text(root, wrap="none", undo=False)
        self.text.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=(0, 8))
        y_scroll = ttk.Scrollbar(root, orient="vertical", command=self.text.yview)
        y_scroll.pack(side="right", fill="y", padx=(0, 8), pady=(0, 8))
        self.text.configure(yscrollcommand=y_scroll.set)
        x_scroll = ttk.Scrollbar(root, orient="horizontal", command=self.text.xview)
        x_scroll.pack(side="bottom", fill="x", padx=8)
        self.text.configure(xscrollcommand=x_scroll.set)

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.enable_windows_drop()

    def choose_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Seleccionar archivo SimuProc",
            filetypes=[("Archivos SimuProc", "*.smp"), ("Todos los archivos", "*.*")],
        )
        if path:
            self.load_file(Path(path))

    def load_file(self, path: Path) -> None:
        try:
            if path.suffix.lower() != ".smp":
                raise ValueError("Selecciona un archivo con extensión .smp.")
            table_path = Path(__file__).with_name("tabla_opcodes_simuproc.csv")
            opcodes = load_opcodes(table_path)
            records = parse_lines(read_text(path), opcodes)
        except (OSError, UnicodeError, ValueError) as error:
            messagebox.showerror("No se pudo traducir el archivo", str(error), parent=self.root)
            return
        self.current_records = records
        self.current_opcodes = opcodes
        self.refresh_result()
        self.file_label.configure(text=path.name)

    def refresh_result(self) -> None:
        if self.current_records is None or self.current_opcodes is None:
            return
        result = render(
            self.current_records,
            self.current_opcodes,
            self.comments_enabled.get(),
        )
        self.text.delete("1.0", "end")
        self.text.insert("1.0", result)

    def copy_result(self) -> None:
        result = self.text.get("1.0", "end-1c")
        if not result:
            messagebox.showinfo("Sin resultado", "Primero abre un archivo SimuProc.", parent=self.root)
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(result)
        self.root.update()
        self.file_label.configure(text="Resultado copiado al portapapeles")

    def enable_windows_drop(self) -> None:
        if sys.platform != "win32":
            return
        hwnd = self.root.winfo_id()
        ctypes.windll.shell32.DragAcceptFiles(hwnd, True)
        callback_type = ctypes.WINFUNCTYPE(
            ctypes.c_ssize_t,
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        )
        call_window_proc = ctypes.windll.user32.CallWindowProcW
        call_window_proc.argtypes = [
            ctypes.c_void_p,
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        call_window_proc.restype = ctypes.c_ssize_t

        @callback_type
        def window_proc(window, message, wparam, lparam):
            if message == 0x0233:  # WM_DROPFILES
                count = ctypes.windll.shell32.DragQueryFileW(wparam, 0xFFFFFFFF, None, 0)
                for index in range(count):
                    length = ctypes.windll.shell32.DragQueryFileW(wparam, index, None, 0)
                    buffer = ctypes.create_unicode_buffer(length + 1)
                    ctypes.windll.shell32.DragQueryFileW(wparam, index, buffer, length + 1)
                    self.load_file(Path(buffer.value))
                ctypes.windll.shell32.DragFinish(wparam)
                return 0
            return call_window_proc(
                self._old_window_proc, window, message, wparam, lparam
            )

        self._window_proc = window_proc
        set_proc = ctypes.windll.user32.SetWindowLongPtrW
        set_proc.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
        set_proc.restype = ctypes.c_void_p
        self._old_window_proc = set_proc(hwnd, -4, ctypes.cast(window_proc, ctypes.c_void_p))

    def close(self) -> None:
        if sys.platform == "win32" and self._old_window_proc:
            set_proc = ctypes.windll.user32.SetWindowLongPtrW
            set_proc.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
            set_proc.restype = ctypes.c_void_p
            set_proc(self.root.winfo_id(), -4, self._old_window_proc)
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    SimuProcWindow(root)
    root.mainloop()