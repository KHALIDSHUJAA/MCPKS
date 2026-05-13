from __future__ import annotations

import re
from dataclasses import dataclass


TOKEN_RE = re.compile(r"\S+")


@dataclass(frozen=True)
class Chunk:
    index: int
    text: str
    token_count: int


def count_tokens(text: str) -> int:
    return len(TOKEN_RE.findall(text))


def split_logical_blocks(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", normalized)
    return [block.strip("\n") for block in blocks if block.strip()]


def split_oversized_block(block: str, max_tokens: int) -> list[str]:
    lines = block.splitlines()
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for line in lines:
        line_tokens = count_tokens(line)
        if current and current_tokens + line_tokens > max_tokens:
            chunks.append("\n".join(current).strip())
            current = []
            current_tokens = 0
        if line_tokens > max_tokens:
            words = TOKEN_RE.findall(line)
            for start in range(0, len(words), max_tokens):
                chunks.append(" ".join(words[start : start + max_tokens]).strip())
            continue
        current.append(line)
        current_tokens += line_tokens

    if current:
        chunks.append("\n".join(current).strip())
    return [chunk for chunk in chunks if chunk]


def chunk_text(text: str, min_tokens: int = 300, max_tokens: int = 800) -> list[Chunk]:
    if not text.strip():
        return []
    if min_tokens <= 0 or max_tokens <= 0 or min_tokens > max_tokens:
        raise ValueError("Expected 0 < min_tokens <= max_tokens")

    blocks: list[str] = []
    for block in split_logical_blocks(text):
        if count_tokens(block) > max_tokens:
            blocks.extend(split_oversized_block(block, max_tokens))
        else:
            blocks.append(block)

    chunks: list[Chunk] = []
    current: list[str] = []
    current_tokens = 0

    for block in blocks:
        block_tokens = count_tokens(block)
        if current and current_tokens + block_tokens > max_tokens:
            chunk = "\n\n".join(current).strip()
            chunks.append(Chunk(index=len(chunks), text=chunk, token_count=count_tokens(chunk)))
            current = []
            current_tokens = 0

        current.append(block)
        current_tokens += block_tokens

        if current_tokens >= min_tokens:
            chunk = "\n\n".join(current).strip()
            chunks.append(Chunk(index=len(chunks), text=chunk, token_count=count_tokens(chunk)))
            current = []
            current_tokens = 0

    if current:
        chunk = "\n\n".join(current).strip()
        chunks.append(Chunk(index=len(chunks), text=chunk, token_count=count_tokens(chunk)))

    return chunks


if __name__ == "__main__":
    import sys

    source = sys.stdin.read()
    for chunk in chunk_text(source):
        print(f"--- chunk {chunk.index} ({chunk.token_count} tokens) ---")
        print(chunk.text)
