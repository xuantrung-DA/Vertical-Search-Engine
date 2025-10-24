# -*- coding: utf-8 -*-
"""
bitset.py — Build a deterministic BitsetIndex and save to a single .pkl

- Input: 1+ JSON files, mỗi file là list[recipe] với các field phổ biến:
  { "title": str, "url": str|None, "ingredients": list[str], "instructions": list[str], ... }
- Output: 1 file .pkl (đường dẫn bắt buộc do bạn chỉ định) chứa:
  {
     "token_bits": { token: (title_bits:int, body_bits:int) },
     "N": <số tài liệu>,
     "meta": { "sources": [...], "created_at": "...", "include_ingredients": bool }
  }

Dùng cho Stage-1 lọc thô cực nhanh trong Module3.py.
Chạy lại script này khi (và chỉ khi) bạn thay đổi tập JSON nguồn.

CLI:
    python bitset.py --data dienmayxanh.json monngonmoingay_multi.json --out bitset_recipes.pkl
    # (tùy chọn) gộp cả ingredients vào body:
    python bitset.py --data ... --out bitset_recipes.pkl --include-ingredients
"""

import argparse
import json
import pickle
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

# ----------------------------
# Tokenizer (vi + fallback)
# ----------------------------
try:
    from underthesea import word_tokenize  # type: ignore
except Exception:
    word_tokenize = None  # fallback: str.split()

VIETNAMESE_STOPWORDS = {
    "và", "của", "là", "cho", "với", "những", "các", "được", "trong", "khi",
    "một", "bằng", "thì", "ở", "rồi", "để", "ra", "có", "này", "nên", "đến",
    "cũng", "như", "nhưng", "vào", "vì", "từ", "đó", "đang", "lúc"
}

def clean_text(text: str) -> List[str]:
    """Lowercase → giữ chữ/số/khoảng trắng → tách từ → bỏ stopwords."""
    if not text:
        return []
    text = text.lower()
    text = re.sub(
        r"[^a-z0-9àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễ"
        r"ìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ\s]",
        " ",
        text,
    )
    tokens = word_tokenize(text) if word_tokenize is not None else text.split()
    return [t for t in (tok.strip() for tok in tokens) if t and t not in VIETNAMESE_STOPWORDS]

# ----------------------------
# IO helpers
# ----------------------------
def load_json_list(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# ----------------------------
# Bitset builder
# ----------------------------
@dataclass
class BitsetIndexData:
    token_bits: Dict[str, Tuple[int, int]]  # token -> (title_bits, body_bits)
    N: int
    meta: Dict[str, Any]

def build_bitset(
    recipes: List[Dict[str, Any]],
    include_ingredients_in_body: bool = False,
) -> BitsetIndexData:
    """
    Tạo 2 bitset cho mỗi token:
      - title_bits: token xuất hiện trong title
      - body_bits : token xuất hiện trong instructions (và tùy chọn ingredients)
    """
    token_bits: Dict[str, Tuple[int, int]] = {}
    N = len(recipes)

    for i, r in enumerate(recipes):
        # Title tokens
        title_tokens = set(clean_text(r.get("title", "") or ""))

        # Body = instructions (+ optional ingredients)
        body_pieces: List[str] = []
        body_pieces.extend(r.get("instructions", []) or [])
        if include_ingredients_in_body:
            body_pieces.append(" ".join(r.get("ingredients", []) or []))
        body_tokens = set(clean_text(" ".join(body_pieces)))

        # Update title bits
        for t in title_tokens:
            tb, bb = token_bits.get(t, (0, 0))
            tb |= (1 << i)
            token_bits[t] = (tb, bb)

        # Update body bits
        for t in body_tokens:
            tb, bb = token_bits.get(t, (0, 0))
            bb |= (1 << i)
            token_bits[t] = (tb, bb)

    meta = {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tokens": len(token_bits),
        "include_ingredients": include_ingredients_in_body,
    }
    return BitsetIndexData(token_bits=token_bits, N=N, meta=meta)

# ----------------------------
# Main CLI
# ----------------------------
def main():
    parser = argparse.ArgumentParser(description="Build a single bitset .pkl for the recipe corpus")
    parser.add_argument(
        "--data", nargs="+", required=True,
        help="Danh sách file JSON nguồn (vd: dienmayxanh.json monngonmoingay_multi.json)",
    )
    parser.add_argument(
        "--out", required=True,
        help="Đường dẫn file .pkl sẽ ghi (vd: bitset_recipes.pkl). Gợi ý commit file này lên Git.",
    )
    parser.add_argument(
        "--include-ingredients", action="store_true",
        help="Nếu bật: gộp ingredients vào body_bits (tăng recall). Mặc định: chỉ instructions.",
    )
    parser.add_argument(
        "--show", action="store_true",
        help="In thống kê & vài token demo sau khi build.",
    )
    args = parser.parse_args()

    # Load all recipes
    recipes: List[Dict[str, Any]] = []
    for p in args.data:
        recipes.extend(load_json_list(p))

    # Build
    bsi = build_bitset(recipes, include_ingredients_in_body=args.include_ingredients)

    # Save deterministic single file
    payload = {
        "token_bits": bsi.token_bits,
        "N": bsi.N,
        "meta": {**bsi.meta, "sources": args.data},
    }
    with open(args.out, "wb") as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)

    # Report
    print(f"[Bitset] Saved: {args.out}")
    print(f"[Bitset] Docs (N) = {bsi.N}, Tokens = {len(bsi.token_bits)}, IncludeIngredients = {args.include_ingredients}")
    if args.show:
        # In 10 token đầu tiên (nếu có)
        c = 0
        for tok, (tb, bb) in bsi.token_bits.items():
            print(f"  {tok!r}  title_bits={bin(tb)}  body_bits={bin(bb)}")
            c += 1
            if c >= 10:
                break

if __name__ == "__main__":
    main()
