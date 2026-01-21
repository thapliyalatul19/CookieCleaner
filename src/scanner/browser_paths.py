"""Browser path constants for Cookie Cleaner."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BrowserConfig:
    """Configuration for a browser's profile locations."""

    name: str  # "Chrome", "Edge", etc.
    user_data_path: Path  # Root User Data folder
    is_chromium: bool  # Chromium-based or Firefox-based
    executable_name: str  # For process detection


# Environment paths
_LOCAL_APPDATA = Path(os.environ.get("LOCALAPPDATA", ""))
_APPDATA = Path(os.environ.get("APPDATA", ""))

# Browser configurations
CHROME_CONFIG = BrowserConfig(
    name="Chrome",
    user_data_path=_LOCAL_APPDATA / "Google" / "Chrome" / "User Data",
    is_chromium=True,
    executable_name="chrome.exe",
)

EDGE_CONFIG = BrowserConfig(
    name="Edge",
    user_data_path=_LOCAL_APPDATA / "Microsoft" / "Edge" / "User Data",
    is_chromium=True,
    executable_name="msedge.exe",
)

BRAVE_CONFIG = BrowserConfig(
    name="Brave",
    user_data_path=_LOCAL_APPDATA / "BraveSoftware" / "Brave-Browser" / "User Data",
    is_chromium=True,
    executable_name="brave.exe",
)

OPERA_CONFIG = BrowserConfig(
    name="Opera",
    user_data_path=_LOCAL_APPDATA / "Opera Software" / "Opera Stable",
    is_chromium=True,
    executable_name="opera.exe",
)

VIVALDI_CONFIG = BrowserConfig(
    name="Vivaldi",
    user_data_path=_LOCAL_APPDATA / "Vivaldi" / "User Data",
    is_chromium=True,
    executable_name="vivaldi.exe",
)

FIREFOX_CONFIG = BrowserConfig(
    name="Firefox",
    user_data_path=_APPDATA / "Mozilla" / "Firefox",
    is_chromium=False,
    executable_name="firefox.exe",
)

# All supported browsers
CHROMIUM_BROWSERS = (CHROME_CONFIG, EDGE_CONFIG, BRAVE_CONFIG, OPERA_CONFIG, VIVALDI_CONFIG)
ALL_BROWSERS = (*CHROMIUM_BROWSERS, FIREFOX_CONFIG)

# Directories to skip when scanning Chromium profiles
CHROMIUM_SKIP_DIRS = frozenset({
    "Crashpad",
    "Safe Browsing",
    "ShaderCache",
    "GrShaderCache",
    "GraphiteDawnCache",
    "BrowserMetrics",
    "Crowd Deny",
    "CertificateRevocation",
    "FileTypePolicies",
    "MEIPreload",
    "SSLErrorAssistant",
    "Subresource Filter",
    "ZxcvbnData",
    "hyphen-data",
    "pnacl",
    "WidevineCdm",
    "SwReporter",
    "OriginTrials",
    "OnDeviceHeadSuggestModel",
    "OptimizationGuide",
    "SafetyTips",
    "TrustTokenKeyCommitments",
})
