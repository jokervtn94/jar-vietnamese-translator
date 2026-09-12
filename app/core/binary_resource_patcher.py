
import struct

def patch_binary_entry(data: bytes, item, replacement: str) -> bytes:
    if not item.patch_safe:
        raise ValueError("Binary entry is not safe to patch.")
    encoded = replacement.encode("utf-8")
    start, end = item.offset, item.offset + item.length

    if item.framing == "null-terminated":
        return data[:start] + encoded + b"\x00" + data[end + item.terminator_size:]

    if item.length_field_offset is None:
        raise ValueError("Missing length field offset.")

    if item.framing == "u8-length-prefixed":
        if len(encoded) > 255:
            raise ValueError("Replacement exceeds u8 length field.")
        return data[:item.length_field_offset] + bytes([len(encoded)]) + encoded + data[end:]

    if item.framing == "u16be-length-prefixed":
        if len(encoded) > 65535:
            raise ValueError("Replacement exceeds u16 length field.")
        return data[:item.length_field_offset] + struct.pack(">H", len(encoded)) + encoded + data[end:]

    if item.framing == "u16le-length-prefixed":
        if len(encoded) > 65535:
            raise ValueError("Replacement exceeds u16 length field.")
        return data[:item.length_field_offset] + struct.pack("<H", len(encoded)) + encoded + data[end:]

    raise ValueError(f"Unsupported framing: {item.framing}")
