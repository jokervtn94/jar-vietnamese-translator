# Strict JSON Translation Protocol

Version 4.6 exports `jar-translator-exchange-v2`.

## Editable field

The translation model may edit only:

```text
items[].translation
```

## Immutable fields

The model must not modify:

```text
id
key
source
kind
index
original
original_sha256
placeholders
```

## Required model behavior

- Return valid JSON only.
- Do not wrap the response in Markdown code fences.
- Keep the complete top-level structure.
- Keep the exact item count and order.
- Do not add, delete, merge, split, or rename items.
- Preserve `%s`, `%d`, `{0}`, `{name}`, `\n`, `\t`, and `<...>` placeholders.
- Do not add explanations or alternate translations.
- Keep game text concise for small J2ME displays.
- When uncertain, copy `original` into `translation`.

## Import validation

The app validates:

1. schema version;
2. source JAR filename;
3. source JAR SHA-256;
4. item count;
5. duplicate IDs/keys;
6. key existence;
7. unchanged original text;
8. original SHA-256;
9. placeholder manifest;
10. source/kind/index metadata;
11. non-empty translation;
12. placeholder preservation in translation.

A failed row is rejected instead of being applied silently.
