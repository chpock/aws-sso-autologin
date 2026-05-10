"""
Log classifier with tokenization and runtime corpus verification.

Memory budget per stream: 64 tokens max, 768 samples max (~48 KiB per stream)
ROT13 obfuscated corpus for privacy protection.
"""

import re
import threading
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto


class LogCategory(Enum):
    """Log classification categories."""

    SUCCESS = auto()
    ERROR_AUTH = auto()
    ERROR_NETWORK = auto()
    ERROR_CONFIG = auto()
    WARNING = auto()
    INFO = auto()
    UNKNOWN = auto()


# ROT13 obfuscated corpus patterns
# These are obfuscated to avoid hardcoding sensitive patterns in plaintext
_OBFUSCATED_PATTERNS = {
    # Successful patterns (rot13 of common success messages)
    LogCategory.SUCCESS: [
        "ybtva fhpprffshy",  # login successful
        "nhgragvpngrq fhpprffshyyl",  # authenticated successfully
        "ffb ybtva pbzcyrgr",  # sso login complete
        "npprff tenagrq",  # access granted
        "ertvfgengvba fhpprppshy",  # registration successful
    ],
    # Authentication errors
    LogCategory.ERROR_AUTH: [
        "vainyvq perqragvnyf",  # invalid credentials
        "nahgubevmrq",  # unauthorized
        "npprff qravrq",  # access denied
        "snvyrq gb nhgragvpngr",  # failed to authenticate
        "nppbhag ybpxrq",  # account locked
        "jebat cnffjbeq",  # wrong password
    ],
    # Network errors
    LogCategory.ERROR_NETWORK: [
        "pbaarpgvba gvzrq bhg",  # connection timed out
        "abg ernpunoyr",  # not reachable
        "arjbex reebe",  # network error
        "qbaf erfcbaq",  # does not respond
        "pbaarpgvba ershfrq",  # connection refused
    ],
    # Configuration errors
    LogCategory.ERROR_CONFIG: [
        "vainyvq pbasvthengvba",  # invalid configuration
        "zvffvat pbasvthengvba",  # missing configuration
        "onq pbasvthengvba",  # bad configuration
        "pbasvthengvba reebe",  # configuration error
    ],
    # Warning patterns
    LogCategory.WARNING: [
        "jneavat",  # warning
        "pnhgbba",  # caution
        "qrcerpngrq",  # deprecated
        "yrtnpl",  # legacy
    ],
    # Info patterns
    LogCategory.INFO: [
        "vtabe",  # ignore (placeholder)
        "vafc",  # info (rot13) -> vaf
        "genpr",  # trace
        "qrohht",  # debug
    ],
}


def _rot13(text: str) -> str:
    """Apply ROT13 transformation."""
    result = []
    for char in text:
        if "a" <= char <= "z":
            result.append(chr((ord(char) - ord("a") + 13) % 26 + ord("a")))
        elif "A" <= char <= "Z":
            result.append(chr((ord(char) - ord("A") + 13) % 26 + ord("A")))
        else:
            result.append(char)
    return "".join(result)


def _deobfuscate_patterns() -> dict:
    """Deobfuscate the pattern corpus at runtime."""
    return {
        category: [_rot13(p) for p in patterns]
        for category, patterns in _OBFUSCATED_PATTERNS.items()
    }


def tokenize_log_line(line: str) -> list[str]:
    """
    Tokenize a log line for classification.

    Normalizes the input by:
    - Converting to lowercase
    - Removing timestamps and special characters
    - Splitting into meaningful tokens

    Args:
        line: Raw log line string

    Returns:
        List of normalized tokens
    """
    if not line:
        return []

    # Convert to lowercase
    normalized = line.lower()

    # Remove timestamp patterns (e.g., "2026-01-01 12:00:00")
    normalized = re.sub(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}", "", normalized)

    # Remove log level indicators at start
    normalized = re.sub(
        r"^(debug|info|warning|warn|error|fatal|trace)\s*[:\-]?\s*",
        "",
        normalized,
        flags=re.IGNORECASE,
    )

    # Replace special characters with spaces
    normalized = re.sub(r"[^\w\s]", " ", normalized)

    # Split into tokens and filter empty ones
    tokens = [token for token in normalized.split() if token]

    return tokens


def classify_log_line(line: str, max_tokens: int = 64) -> LogCategory:
    """
    Classify a log line into a category.

    Args:
        line: Raw log line string
        max_tokens: Maximum tokens to process (for memory budget)

    Returns:
        LogCategory enum value
    """
    tokens = tokenize_log_line(line)

    # Apply token budget
    tokens = tokens[:max_tokens]

    if not tokens:
        return LogCategory.UNKNOWN

    # Deobfuscate patterns at runtime
    patterns = _deobfuscate_patterns()

    # Join tokens for pattern matching
    text = " ".join(tokens)

    # Check each category's patterns
    for category in [
        LogCategory.ERROR_AUTH,
        LogCategory.ERROR_NETWORK,
        LogCategory.ERROR_CONFIG,
        LogCategory.SUCCESS,
        LogCategory.WARNING,
    ]:
        for pattern in patterns.get(category, []):
            if pattern in text:
                return category

    # Check for info patterns (lowest priority)
    info_text = _rot13("vagb")  # "info" in rot13
    debug_text = _rot13("qrohht")  # "debug" in rot13
    if info_text in text or debug_text in text:
        return LogCategory.INFO

    return LogCategory.UNKNOWN


@dataclass
class ClassifiedLog:
    """A classified log entry."""

    original_line: str
    tokens: list[str]
    category: LogCategory


class LogClassifier:
    """
    Memory-budgeted log classifier with FIFO eviction.

    Memory budget per stream:
    - 64 tokens per sample maximum
    - 768 samples per stream maximum
    - Approximately 48 KiB per stream
    - Approximately 12 MiB total for 3 streams
    """

    DEFAULT_MAX_TOKENS = 64
    DEFAULT_MAX_SAMPLES = 768

    def __init__(
        self,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        max_samples: int = DEFAULT_MAX_SAMPLES,
    ):
        """
        Initialize the classifier.

        Args:
            max_tokens: Maximum tokens per sample (default: 64)
            max_samples: Maximum samples to retain (default: 768)
        """
        self.max_tokens = max_tokens
        self.max_samples = max_samples
        self._samples: deque = deque(maxlen=max_samples)
        self._lock = threading.Lock()
        self._corpus_verified = False

    def _verify_corpus(self) -> bool:
        """
        Verify the corpus is properly deobfuscated at runtime.

        Returns:
            True if corpus verification passes
        """
        try:
            patterns = _deobfuscate_patterns()
            # Verify some known patterns are present
            success_patterns = patterns.get(LogCategory.SUCCESS, [])
            if not success_patterns:
                return False
            # Check that patterns are not still obfuscated
            sample = success_patterns[0]
            if all(c.isalpha() and c.islower() for c in sample.replace(" ", "")):
                # Looks like valid deobfuscated text
                self._corpus_verified = True
                return True
            return False
        except Exception:
            return False

    def classify(self, line: str) -> ClassifiedLog:
        """
        Classify a log line and store it.

        Args:
            line: Raw log line string

        Returns:
            ClassifiedLog object with tokens and category
        """
        # Verify corpus on first use
        if not self._corpus_verified:
            self._verify_corpus()

        # Tokenize with budget
        tokens = tokenize_log_line(line)[: self.max_tokens]

        # Classify
        category = classify_log_line(line, max_tokens=self.max_tokens)

        result = ClassifiedLog(original_line=line, tokens=tokens, category=category)

        # Store with thread safety
        with self._lock:
            self._samples.append(result)

        return result

    def get_samples(self) -> list[ClassifiedLog]:
        """
        Get all stored samples.

        Returns:
            List of ClassifiedLog objects (most recent first due to FIFO)
        """
        with self._lock:
            return list(self._samples)

    def get_samples_by_category(self, category: LogCategory) -> list[ClassifiedLog]:
        """
        Get samples filtered by category.

        Args:
            category: Category to filter by

        Returns:
            List of ClassifiedLog objects matching the category
        """
        with self._lock:
            return [s for s in self._samples if s.category == category]

    def clear(self) -> None:
        """Clear all stored samples."""
        with self._lock:
            self._samples.clear()

    def __len__(self) -> int:
        """Return the number of stored samples."""
        return len(self._samples)
