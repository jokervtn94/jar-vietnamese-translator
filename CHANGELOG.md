# Changelog

## 4.6 – Strict JSON Protocol

- Replaced API-based translation with manual JSON exchange.
- Added `jar-translator-exchange-v2`.
- Added mandatory translation rules and exact output contract.
- Added source JAR SHA-256 validation.
- Added per-string SHA-256 validation.
- Added placeholder manifests and import validation.
- Added item-count, duplicate ID/key, and immutable metadata validation.
- Kept backward-compatible import for V1/simple JSON formats.

## 4.5 – JSON Exchange

- Removed OpenAI/Gemini API integration.
- Removed API key and credential-storage requirements.
- Added JSON export/import workflow for external ChatGPT/Gemini translation.

## 4.4 – Precision Scan

- Added precision-first per-string classification.
- Reduced Java descriptors, class names, paths, URLs, identifiers, and other technical false positives.

## 4.3 – Deep Scan

- Expanded language discovery to non-standard JAR resources, ASCII, UTF-8, UTF-16LE and UTF-16BE.

## 4.2 – Responsive UI

- Added adaptive toolbar, splitters, table sizing and compact layouts for smaller displays.

## 4.0 – Stable Pipeline

- Integrated scan, safe build, readiness, regression validation, runtime packaging and runtime log analysis.
