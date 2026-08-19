import os
import re
import csv
from typing import Tuple, Optional, List

from .log.ssh_session import SSHSessionParser
from .log.syslog import SyslogParser
from .log.structured_csv import StructuredLogParser
from .log.generic import GenericLogParser
from .config.vrp import VRPConfigParser
from .config.ios import IOSConfigParser
from .config.generic import GenericConfigParser
from .doc.html import HTMLIndexer
from .doc.pdf import PDFIndexer
from .doc.markdown import MarkdownIndexer
from .doc.chm import CHMIndexer


class FileRouter:
    def __init__(self):
        self._log_parsers = {
            "ssh_session": SSHSessionParser,
            "syslog": SyslogParser,
            "structured_csv": StructuredLogParser,
            "generic": GenericLogParser,
        }
        self._config_parsers = {
            "vrp": VRPConfigParser,
            "ios": IOSConfigParser,
            "generic": GenericConfigParser,
        }
        self._doc_parsers = {
            "html": HTMLIndexer,
            "pdf": PDFIndexer,
            "markdown": MarkdownIndexer,
            "chm": CHMIndexer,
        }

    def _read_header_bytes(self, file_path: str, size: int = 500) -> bytes:
        try:
            with open(file_path, "rb") as f:
                return f.read(size)
        except (IOError, OSError):
            return b""

    def _read_sample_lines(self, file_path: str, count: int = 100) -> List[str]:
        lines = []
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f):
                    if i >= count:
                        break
                    lines.append(line.rstrip("\n"))
        except (IOError, OSError):
            pass
        return lines

    def detect_type(
        self, file_path: str, header_bytes: Optional[bytes] = None, sample_lines: Optional[List[str]] = None
    ) -> Tuple[str, str, float]:
        if header_bytes is None:
            header_bytes = self._read_header_bytes(file_path, 500)
        if sample_lines is None:
            sample_lines = self._read_sample_lines(file_path, 100)

        header_text = header_bytes.decode("utf-8", errors="replace")
        ext = os.path.splitext(file_path)[1].lower()

        ext_map = {
            ".log": ("log", None, 0.5),
            ".csv": ("log", "structured_csv", 0.7),
            ".cfg": ("config", None, 0.5),
            ".conf": ("config", None, 0.5),
            ".chm": ("doc", "chm", 0.8),
            ".pdf": ("doc", "pdf", 0.9),
            ".html": ("doc", "html", 0.9),
            ".htm": ("doc", "html", 0.9),
            ".md": ("doc", "markdown", 0.9),
        }

        category = None
        parser_name = None
        confidence = 0.0

        if ext in ext_map:
            category, pn, c = ext_map[ext]
            parser_name = pn
            confidence = c
            # ext_map can declare parser_name=None to indicate "category decided
            # purely by extension"; concrete parser is still chosen by sniffers below.
            # Without a sniffer hit we still want a friendly parser_name.
            if parser_name is None:
                if category == "log":
                    parser_name = "generic"
                elif category == "config":
                    parser_name = "generic"

        if "[BEGIN]" in header_text and ("Connecting to" in header_text or "Connecting to" in " ".join(sample_lines[:5])):
            category = "log"
            parser_name = "ssh_session"
            confidence = max(confidence, 0.9)

        if "!CfgFileCrc" in header_text or "sysname " in header_text:
            category = "config"
            parser_name = "vrp"
            confidence = max(confidence, 0.9)

        pri_pattern = re.compile(r"^<\d{1,3}>", re.MULTILINE)
        if pri_pattern.search(header_text):
            category = "log"
            parser_name = "syslog"
            confidence = max(confidence, 0.85)

        if sample_lines and len(sample_lines) > 0:
            first_line = sample_lines[0]
            csv_known_cols = {"time", "timestamp", "src", "source", "dst", "dest", "target", "protocol", "action", "bytes"}
            try:
                reader = csv.reader([first_line])
                cols = next(reader)
                if len(cols) >= 3:
                    col_lower = {c.strip().lower() for c in cols}
                    if col_lower & csv_known_cols:
                        category = "log"
                        parser_name = "structured_csv"
                        confidence = max(confidence, 0.8)
            except Exception:
                pass

        sample_joined = " ".join(sample_lines)

        if not parser_name or confidence < 0.6:
            vrp_keywords = len(re.findall(r"\bsysname\b|\binterface\s+GigabitEthernet\b|\bacl\s+number\b|\bsecurity-policy\b|\bospf\b|\baaa\b|\bssh\b|\bsnmp-agent\b", sample_joined))
            if vrp_keywords >= 2:
                category = "config"
                parser_name = "vrp"
                confidence = max(confidence, 0.8)

            ios_keywords = len(re.findall(r"\bhostname\b|\bversion\s+\d+\.\d+|\binterface\s+FastEthernet\b|\binterface\s+GigabitEthernet\b|\baccess-list\b", sample_joined))
            if ios_keywords >= 2 and (not parser_name or parser_name != "vrp"):
                category = "config"
                parser_name = "ios"
                confidence = max(confidence, 0.75)

            timestamp_count = len(re.findall(r"\d{4}[-/]\d{2}[-/]\d{2}[ T]\d{2}:\d{2}:\d{2}", sample_joined))
            hms_count = len(re.findall(r"\b\d{2}:\d{2}:\d{2}\b", sample_joined))
            if timestamp_count >= 3 or hms_count >= 5:
                if category is None:
                    category = "log"
                    parser_name = "generic"
                    confidence = max(confidence, 0.6)

            if ext in (".cfg", ".conf") and category is None:
                category = "config"
                parser_name = "generic"
                confidence = max(confidence, 0.6)

        if category is None:
            if ext in (".log", ".txt"):
                category = "log"
            elif ext in (".cfg", ".conf"):
                category = "config"
            elif ext in (".chm", ".pdf", ".html", ".htm", ".md"):
                category = "doc"
            else:
                category = "log"
            parser_name = "generic"
            confidence = max(confidence, 0.3)

        return category, parser_name, confidence

    def route(self, file_path: str):
        category, parser_name, confidence = self.detect_type(file_path)

        if category == "log":
            parser_cls = self._log_parsers.get(parser_name, self._log_parsers["generic"])
            return parser_cls()
        elif category == "config":
            parser_cls = self._config_parsers.get(parser_name, self._config_parsers["generic"])
            return parser_cls()
        elif category == "doc":
            parser_cls = self._doc_parsers.get(parser_name)
            if parser_cls is None:
                return None
            return parser_cls()
        else:
            return self._log_parsers["generic"]()
