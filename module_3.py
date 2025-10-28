# -*- coding: utf-8 -*-
"""
Module 3 – Retrieval (BM25) + Generic Phrase/Proximity Re-ranking (Strict & Fast)

- Output: Title, URL, Snippet
- “Liên quan trước”: exact phrase/full cover chứa anchor → partial giảm dần
- Giữ kỹ thuật gốc; bổ sung:
  * Stage-1 có thể dùng bitset.pkl (nhanh) hoặc fallback union-postings (cũ)
  * Sắp xếp lại thứ tự hàm theo flow
"""

import json
import math
import re
import os
import pickle
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Iterable, Set

# =============================================================================
# 0) TOKENIZER & TEXT UTILS
# =============================================================================

try:
    from underthesea import word_tokenize
except Exception:
    word_tokenize = None

VIETNAMESE_STOPWORDS = {
    "và", "của", "là", "cho", "với", "những", "các", "được", "trong", "khi",
    "một", "bằng", "thì", "ở", "rồi", "để", "ra", "có", "này", "nên", "đến",
    "cũng", "như", "nhưng", "vào", "vì", "từ", "đó", "đang", "lúc"
}

def clean_text(text: str) -> List[str]:
    """Lowercase, giữ chữ/số/khoảng trắng, tách từ, bỏ stopwords."""
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

def _tokens_seq(text: str) -> List[str]:
    """Giữ thứ tự token (phục vụ phrase & proximity)."""
    return clean_text(text)

def ngrams(tokens: List[str], n: int) -> List[List[str]]:
    return [tokens[i : i + n] for i in range(len(tokens) - n + 1)]

def phrase_present(seq: List[str], phrase: List[str]) -> bool:
    L = len(phrase)
    for i in range(len(seq) - L + 1):
        if seq[i : i + L] == phrase:
            return True
    return False

def has_ordered_within(seq: List[str], a: str, b: str, window: int = 3) -> bool:
    pos_a = [i for i, t in enumerate(seq) if t == a]
    pos_b = [i for i, t in enumerate(seq) if t == b]
    for i in pos_a:
        for j in pos_b:
            if j > i and (j - i) <= window:
                return True
    return False

# =============================================================================
# 1) DATA STRUCTS & LOADERS
# =============================================================================

@dataclass
class SearchResult:
    doc_id: int
    title: str
    url: Optional[str]
    score: float
    snippet: str = ""

def load_recipes(files: List[str]) -> List[Dict[str, Any]]:
    recipes: List[Dict[str, Any]] = []
    for file in files:
        with open(file, "r", encoding="utf-8") as f:
            recipes.extend(json.load(f))
    return recipes

def load_inverted_index(path: str) -> Dict[str, Dict[str, Dict[str, Any]]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# =============================================================================
# 2) CORPUS CACHE (speed-up)
# =============================================================================

class CorpusView:
    """Cache các đặc trưng hay dùng để tránh tính lại nhiều lần."""
    def __init__(self, recipes: List[Dict[str, Any]]):
        self.recipes = recipes
        self.N = len(recipes)
        # BM25 doc tokens/lengths
        self.doc_tokens: List[List[str]] = [self._doc_tokens(r) for r in recipes]
        self.doc_lens: List[int] = [len(toks) or 1 for toks in self.doc_tokens]
        self.avgdl: float = (sum(self.doc_lens) / self.N) if self.N else 0.0
        # Field seqs & sets
        self.title_seqs, self.body_seqs = self._field_seqs(recipes)
        self.title_token_sets: List[Set[str]] = [set(seq) for seq in self.title_seqs]
        self.ing_token_sets: List[Set[str]] = [
            set(clean_text(" ".join(r.get("ingredients", []) or []))) for r in recipes
        ]

    @staticmethod
    def _doc_tokens(recipe: Dict[str, Any]) -> List[str]:
        title = recipe.get("title", "") or ""
        ing = " ".join(recipe.get("ingredients", []) or [])
        instr = " ".join(recipe.get("instructions", []) or [])
        return clean_text(" ".join([title, ing, instr]))

    @staticmethod
    def _field_seqs(recipes: List[Dict[str, Any]]) -> Tuple[List[List[str]], List[List[str]]]:
        titles = [_tokens_seq(r.get("title", "") or "") for r in recipes]
        bodies = [_tokens_seq(" ".join(r.get("instructions", []) or [])) for r in recipes]
        return titles, bodies

# =============================================================================
# 3) STAGE-1 (LỌC THÔ)
# 3.1) Cheap scoring & union-postings (bản cũ / fallback)
# =============================================================================

from heapq import nlargest

def _title_startswith(token: str, title: str) -> bool:
    return title.lower().strip().startswith(token + " ")

def _cheap_signal_scores(
    doc_id: int,
    cv: CorpusView,
    q_tokens: List[str],
    anchor: str,
) -> int:
    """
    Điểm 'rẻ' dùng cho Stage-1:
    - exact phrase ở title/body (ưu tiên mạnh)
    - số token truy vấn xuất hiện trong title/body (title nặng hơn)
    - title bắt đầu bằng token đầu
    - anchor trong title
    - có ít nhất một cặp kề trong w=3
    """
    t_seq = cv.title_seqs[doc_id]
    b_seq = cv.body_seqs[doc_id]
    tset  = cv.title_token_sets[doc_id]
    bset  = set(b_seq)

    p3 = ngrams(q_tokens, 3)
    p2 = ngrams(q_tokens, 2)
    exact_t = any(phrase_present(t_seq, ph) for ph in (p3 if p3 else p2))
    exact_b = any(phrase_present(b_seq, ph) for ph in (p3 if p3 else p2))

    hit_t = sum(1 for t in q_tokens if t in tset)
    hit_b = sum(1 for t in q_tokens if t in bset)

    title_str = (cv.recipes[doc_id].get("title") or "").lower().strip()
    pref = 1 if _title_startswith(q_tokens[0], title_str) else 0
    anch = 1 if anchor in tset else 0

    q_pairs = [(q_tokens[i], q_tokens[i+1]) for i in range(len(q_tokens)-1)]
    adj = 0
    if q_pairs:
        if any(has_ordered_within(t_seq, a, b, 3) for a, b in q_pairs) \
           or any(has_ordered_within(b_seq, a, b, 3) for a, b in q_pairs):
            adj = 1

    score = (
        10*int(exact_t) + 6*int(exact_b) +
        2*hit_t + 1*hit_b +
        2*pref + 2*anch + 1*adj
    )
    return score

def stage1_coarse_candidates(
    query_tokens: List[str],
    inverted_index,
    cv: CorpusView,
    anchor: str,
    k_coarse: int = 50,
) -> List[int]:
    """UNION postings + cheap scoring (fallback)."""
    cand_all = set()
    for t in query_tokens:
        p = inverted_index.get(t)
        if p:
            cand_all |= {int(x) for x in p.keys()}
    if not cand_all:
        cand_all = set(range(cv.N))

    scored = []
    for d in cand_all:
        s = _cheap_signal_scores(d, cv, query_tokens, anchor)
        if s > 0:
            scored.append((s, d))

    if not scored:
        return list(cand_all)[:k_coarse]

    with_anchor = [(s, d) for (s, d) in scored if anchor in cv.title_token_sets[d] or anchor in set(cv.body_seqs[d])]
    without_anchor = [(s, d) for (s, d) in scored if d not in {x[1] for x in with_anchor}]

    topA = nlargest(k_coarse, with_anchor, key=lambda x: x[0])
    if len(topA) >= k_coarse:
        return [d for _, d in topA]

    need = k_coarse - len(topA)
    topB = nlargest(need, without_anchor, key=lambda x: x[0])
    return [d for _, d in (topA + topB)]

# =============================================================================
# 3.2) Stage-1 dùng BITSET (nếu có file pkl)
# =============================================================================

@dataclass
class _BitsetIndex:
    token_bits: Dict[str, Tuple[int, int]]  # token -> (title_bits, body_bits)
    N: int

def _load_bitset(path: Optional[str]) -> Optional[_BitsetIndex]:
    if not path or not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        obj = pickle.load(f)
    # hỗ trợ payload từ bitset.py (dict) hoặc dataclass
    token_bits = getattr(obj, "token_bits", None) or obj.get("token_bits")
    N = getattr(obj, "N", None) or obj.get("N")
    return _BitsetIndex(token_bits=token_bits, N=N)

def _bits_title(bsi: _BitsetIndex, token: str) -> int:
    pair = bsi.token_bits.get(token)
    return pair[0] if pair else 0

def _bits_body(bsi: _BitsetIndex, token: str) -> int:
    pair = bsi.token_bits.get(token)
    return pair[1] if pair else 0

def _bits_union(bsi: _BitsetIndex, tokens: List[str]) -> int:
    u = 0
    get = bsi.token_bits.get
    for t in tokens:
        pair = get(t)
        if pair:
            u |= (pair[0] | pair[1])
    return u

def _iter_set_bits(bits: int):
    """Yield doc_ids (0-based) có bit=1."""
    while bits:
        lsb = bits & -bits
        idx = (lsb.bit_length() - 1)
        yield idx
        bits ^= lsb

def stage1_bitset_candidates(
    query_tokens: List[str],
    anchor: str,
    bsi: _BitsetIndex,
    cv: CorpusView,
    k_coarse: int = 50,
) -> List[int]:
    """Stage-1 cực nhanh bằng bitset: chọn ứng viên, rồi cheap-score & top-k."""
    cand_anchor = _bits_title(bsi, anchor) | _bits_body(bsi, anchor)
    cand_all = _bits_union(bsi, query_tokens)
    cand_bits = cand_anchor if cand_anchor else cand_all
    if cand_bits == 0:
        cand_bits = cand_all
    if cand_bits == 0:
        cand_bits = (1 << cv.N) - 1  # all docs

    scored = []
    for doc_id in _iter_set_bits(cand_bits):
        s = _cheap_signal_scores(doc_id, cv, query_tokens, anchor)
        if s > 0:
            scored.append((s, doc_id))

    if not scored:
        out = []
        for d in _iter_set_bits(cand_bits):
            out.append(d)
            if len(out) >= k_coarse:
                break
        return out

    top = nlargest(k_coarse, scored, key=lambda x: x[0])
    return [d for _, d in top]

# =============================================================================
# 4) BM25 CORE + FIELD BOOSTS
# =============================================================================

def term_idf(token: str, inverted_index, N: int) -> float:
    posting = inverted_index.get(token)
    df = len(posting) if posting else 0
    return math.log((N - df + 0.5) / (df + 0.5) + 1.0)

def compute_bm25_scores(
    query_tokens: List[str],
    inverted_index: Dict[str, Dict[str, Dict[str, Any]]],
    cv: CorpusView,
    *,
    k1: float = 1.5,
    b: float = 0.75,
    title_boost: float = 2.5,
    ingredients_boost: float = 1.2,
    candidate_docs: Optional[Iterable[int]] = None,
) -> Dict[int, float]:
    """BM25 (single-field) + field boosts; chỉ tính trên candidate_docs nếu có."""
    N = cv.N
    scores: Dict[int, float] = {}
    cand_set: Optional[Set[int]] = set(candidate_docs) if candidate_docs is not None else None

    for token in query_tokens:
        posting = inverted_index.get(token)
        if not posting:
            continue
        df = len(posting)
        if df == 0:
            continue
        idf = math.log((N - df + 0.5) / (df + 0.5) + 1.0)

        for doc_id_str, info in posting.items():
            doc_id = int(doc_id_str)
            if cand_set is not None and doc_id not in cand_set:
                continue

            tf = int(info.get("freq", 0))
            if tf <= 0:
                continue

            dl = cv.doc_lens[doc_id]
            denom = tf + k1 * (1.0 - b + b * (dl / (cv.avgdl or 1.0)))
            w = idf * (tf * (k1 + 1.0)) / (denom or 1.0)

            if token in cv.title_token_sets[doc_id]:
                w *= title_boost
            elif token in cv.ing_token_sets[doc_id]:
                w *= ingredients_boost

            scores[doc_id] = scores.get(doc_id, 0.0) + float(w)

    return scores

# =============================================================================
# 5) QUERY INTENT, FILTERS & RE-RANK
# =============================================================================

def build_query_intent(query_tokens: List[str], inverted_index, N: int) -> Dict[str, Any]:
    idf = {t: term_idf(t, inverted_index, N) for t in query_tokens}
    sorted_terms = sorted(query_tokens, key=lambda t: idf[t], reverse=True)
    k = max(1, (len(sorted_terms) + 1) // 2)
    essential_terms = sorted_terms[:k]
    p2 = ngrams(query_tokens, 2)
    p3 = ngrams(query_tokens, 3)
    w = lambda ph: sum(idf.get(t, 0.0) for t in ph)
    return {
        "idf": idf,
        "essential_terms": essential_terms,
        "phrases_2": p2,
        "phrases_3": p3,
        "p2w": {tuple(p): w(p) for p in p2},
        "p3w": {tuple(p): w(p) for p in p3},
    }

def df_ratio(token: str, inverted_index, N: int) -> float:
    posting = inverted_index.get(token)
    df = len(posting) if posting else 0
    return df / max(1, N)

def effective_query_tokens(query_tokens: List[str], inverted_index, N: int, tau: float = 0.25) -> List[str]:
    keep = [t for t in query_tokens if df_ratio(t, inverted_index, N) <= tau]
    return keep or query_tokens[:]  # fallback nếu lọc sạch

def must_have_with_anchor(
    scores: Dict[int, float],
    cv: CorpusView,
    inverted_index,
    query_tokens: List[str],
    anchor: str
) -> Dict[int, float]:
    """Yêu cầu: anchor xuất hiện + >=1 essential khác xuất hiện (precision↑)."""
    intent = build_query_intent(query_tokens, inverted_index, cv.N)
    essential = intent["essential_terms"]
    filtered: Dict[int, float] = {}
    for doc_id, s in scores.items():
        appear = set(cv.title_seqs[doc_id]) | set(cv.body_seqs[doc_id])
        if anchor not in appear:
            continue
        ok = any((t != anchor) and (t in appear) for t in essential)
        if ok:
            filtered[doc_id] = s
    return filtered

def must_have_any_token(
    scores: Dict[int, float],
    cv: CorpusView,
    query_tokens: List[str],
    anchor: Optional[str] = None
) -> Dict[int, float]:
    """Fallback cho truy vấn ngắn (≤2 token): giữ doc chứa ≥1 token; ưu tiên anchor."""
    qt_set = set(query_tokens)
    strong, weak = {}, {}
    for doc_id, s in scores.items():
        appear = set(cv.title_seqs[doc_id]) | set(cv.body_seqs[doc_id])
        if qt_set & appear:
            if anchor and anchor in appear:
                strong[doc_id] = s
            else:
                weak[doc_id] = s
    out = {}
    out.update(strong)
    out.update(weak)
    return out

def rerank_generic(
    scores: Dict[int, float],
    cv: CorpusView,
    inverted_index,
    query_tokens: List[str],
    prox_window: int = 3,
    alpha_phrase_title: float = 1.6,
    alpha_phrase_body: float = 1.0,
    beta_prox_title: float = 0.6,
    beta_prox_body: float = 0.4,
    gamma_missing_idf: float = 0.9,
) -> Dict[int, float]:
    """Boost cụm (2/3-gram), boost proximity, phạt mềm thiếu essential terms."""
    intent = build_query_intent(query_tokens, inverted_index, cv.N)
    idf = intent["idf"]
    essential = intent["essential_terms"]
    p2, p3 = intent["phrases_2"], intent["phrases_3"]
    p2w, p3w = intent["p2w"], intent["p3w"]

    new_scores: Dict[int, float] = {}
    for doc_id, base in scores.items():
        bonus = 0.0
        t_seq = cv.title_seqs[doc_id]
        b_seq = cv.body_seqs[doc_id]
        appear = set(t_seq) | set(b_seq)

        missing_idf = sum(idf[t] for t in essential if t not in appear)
        if missing_idf > 0:
            bonus -= gamma_missing_idf * missing_idf

        for ph in p3:
            w = p3w[tuple(ph)]
            if w <= 0:
                continue
            if phrase_present(t_seq, ph):
                bonus += alpha_phrase_title * w * 1.2
            elif phrase_present(b_seq, ph):
                bonus += alpha_phrase_body * w

        for ph in p2:
            w = p2w[tuple(ph)]
            if w <= 0:
                continue
            if phrase_present(t_seq, ph):
                bonus += alpha_phrase_title * w
            elif phrase_present(b_seq, ph):
                bonus += alpha_phrase_body * w

        for (a, b) in p2:
            w_pair = 0.5 * (idf.get(a, 0.0) + idf.get(b, 0.0))
            if has_ordered_within(t_seq, a, b, prox_window):
                bonus += beta_prox_title * w_pair
            elif has_ordered_within(b_seq, a, b, prox_window):
                bonus += beta_prox_body * w_pair

        new_scores[doc_id] = base + bonus

    return new_scores

def rerank_phrase_tiering(
    scores: Dict[int, float],
    cv: CorpusView,
    query_tokens: List[str],
    big_bonus_title: float = 8.0,
    big_bonus_body: float = 4.0,
) -> Tuple[Dict[int, float], Set[int]]:
    """Tiering bonus cho exact phrase 3-gram/2-gram (ưu tiên title)."""
    p3 = ngrams(query_tokens, 3)
    p2 = ngrams(query_tokens, 2)
    title_phrase_hit: Set[int] = set()
    new: Dict[int, float] = {}
    for doc_id, base in scores.items():
        bonus = 0.0
        t_seq = cv.title_seqs[doc_id]
        b_seq = cv.body_seqs[doc_id]

        hit3_t = any(phrase_present(t_seq, ph) for ph in p3)
        hit3_b = any(phrase_present(b_seq, ph) for ph in p3)
        if hit3_t:
            title_phrase_hit.add(doc_id)
            bonus += big_bonus_title
        elif hit3_b:
            bonus += big_bonus_body

        if bonus == 0.0:
            hit2_t = any(phrase_present(t_seq, ph) for ph in p2)
            hit2_b = any(phrase_present(b_seq, ph) for ph in p2)
            if hit2_t:
                title_phrase_hit.add(doc_id)
                bonus += big_bonus_title * 0.6
            elif hit2_b:
                bonus += big_bonus_body * 0.6

        new[doc_id] = base + bonus
    return new, title_phrase_hit

# =============================================================================
# 6) SNIPPET & HIGHLIGHT
# =============================================================================

def _highlight(text: str, raw_query: str) -> str:
    """Bôi đậm (**) những chuỗi con khớp từ khóa (không phân biệt hoa thường)."""
    if not text or not raw_query:
        return text or ""
    terms = [re.escape(t) for t in raw_query.strip().split() if t]
    if not terms:
        return text
    pattern = re.compile("(" + "|".join(terms) + ")", flags=re.IGNORECASE)
    return pattern.sub(r"**\1**", text)

def build_snippet(recipe: Dict[str, Any], raw_query: str, max_len: int = 220) -> str:
    """Chọn 1 đoạn có từ khóa (ưu tiên title → lines có nhiều token truy vấn → ingredients)."""
    candidates: List[str] = []
    title = (recipe.get("title", "") or "").strip()
    if title:
        candidates.append(title)

    q_terms = set(clean_text(raw_query))
    lines_scored: List[Tuple[int, str]] = []
    for line in recipe.get("instructions", []) or []:
        toks = set(clean_text(str(line)))
        lines_scored.append((len(q_terms & toks), str(line).strip()))
    lines_scored.sort(key=lambda x: x[0], reverse=True)
    for k, s in lines_scored[:2]:
        if k > 0:
            candidates.append(s)

    if not candidates:
        ing = recipe.get("ingredients", []) or []
        if ing:
            candidates.append(", ".join(ing[:4]))

    text = candidates[0] if candidates else ""
    if len(text) > max_len:
        text = text[: max_len - 3] + "..."
    return _highlight(text, raw_query)

# =============================================================================
# 7) CANDIDATES (anchor-first helper giữ nguyên để không đổi logic)
# =============================================================================

def postings_set(token: str, inverted_index) -> Set[int]:
    p = inverted_index.get(token)
    return set(map(int, p.keys())) if p else set()

def build_candidates_anchor_first(query_tokens: List[str], inverted_index, top_k: int) -> List[int]:
    """Giữ lại theo logic cũ (không can thiệp)."""
    if not query_tokens:
        return []
    anchor = query_tokens[0]
    rest = query_tokens[1:]

    anchor_set = postings_set(anchor, inverted_index)
    rest_union: Set[int] = set()
    for t in rest:
        rest_union |= postings_set(t, inverted_index)

    cand_A = anchor_set & (rest_union if rest else anchor_set)

    union_all = set(anchor_set)
    for t in rest:
        union_all |= postings_set(t, inverted_index)

    if not cand_A:
        return list(union_all)

    if len(cand_A) >= top_k:
        return list(cand_A)

    extra = list(union_all - cand_A)
    return list(cand_A) + extra

# =============================================================================
# 8) RELEVANCE TIERING (strict)
# =============================================================================

def coverage(doc_tokens_set: Set[str], query_tokens: List[str]) -> int:
    return sum(1 for t in query_tokens if t in doc_tokens_set)

def has_any_adjacent_pair_within_window(
    seq: List[str], q_pairs: List[Tuple[str, str]], window: int
) -> bool:
    for a, b in q_pairs:
        if has_ordered_within(seq, a, b, window):
            return True
    return False

def compute_relevance_tier(
    doc_id: int,
    cv: CorpusView,
    query_tokens: List[str],
    anchor: Optional[str],
    prox_window: int = 3,
) -> Tuple[int, float, bool]:
    """
    (tier, coverage_ratio, title_phrase_hit_flag_for_sort)
    Tier 0: exact phrase (+anchor trong title) + coverage_thresh (+adjacency nếu |Q|≥4)
    Tier 1: full cover (+anchor trong title/ingredients)
    Tier ≥2: partial; thiếu anchor bị hạ tier.
    """
    t_seq = cv.title_seqs[doc_id]
    b_seq = cv.body_seqs[doc_id]
    seq_set = set(t_seq) | set(b_seq)
    q_len = len(query_tokens)
    cov = coverage(seq_set, query_tokens)
    cov_ratio = cov / max(1, q_len)
    coverage_thresh = (cov >= int(math.ceil(0.75 * q_len))) if q_len >= 3 else True

    p3 = ngrams(query_tokens, 3)
    p2 = ngrams(query_tokens, 2)
    exact_title = any(phrase_present(t_seq, ph) for ph in (p3 if p3 else p2))
    exact_body  = any(phrase_present(b_seq, ph) for ph in (p3 if p3 else p2))
    exact_any = exact_title or exact_body

    need_adj = q_len >= 4
    q_pairs = [(query_tokens[i], query_tokens[i+1]) for i in range(q_len-1)]
    adj_ok = (not need_adj) or has_any_adjacent_pair_within_window(t_seq, q_pairs, prox_window) \
                         or has_any_adjacent_pair_within_window(b_seq, q_pairs, prox_window)

    if exact_any and coverage_thresh and adj_ok:
        if anchor and anchor not in set(t_seq):  # Title-anchor gate
            return (2, cov_ratio, bool(exact_title))
        return (0, 1.0, bool(exact_title))

    if cov == q_len and coverage_thresh:
        if anchor and (anchor not in set(t_seq) and anchor not in cv.ing_token_sets[doc_id]):
            return (2, cov_ratio, bool(exact_title))
        return (1, cov_ratio, bool(exact_title))

    tier_partial = 2 + (q_len - cov)
    if anchor and anchor not in seq_set:
        tier_partial += 1
    return (tier_partial, cov_ratio, bool(exact_title))

# =============================================================================
# 9) SEARCH PIPELINE
# =============================================================================

def search(
    raw_query: str,
    inverted_index_path: str = "inverted_index.json",
    recipe_files: Optional[List[str]] = None,
    top_k: int = 10,
    title_boost: float = 2.5,
    ingredients_boost: float = 1.2,
    k1: float = 1.5,
    b: float = 0.75,
    *,
    bitset_path: Optional[str] = None,
    stage1_k: int = 50,
) -> List[SearchResult]:
    """
    query → tokenize → Stage-1 (bitset nếu có, else union-postings) → BM25
          → must-have(anchor)/fallback → generic re-rank → phrase tiering
          → relevance tiering → sort → build results
    """
    if not raw_query or not raw_query.strip():
        return []

    if recipe_files is None:
        recipe_files = ["dienmayxanh.json", "monngonmoingay_multi.json"]

    recipes = load_recipes(recipe_files)
    inverted_index = load_inverted_index(inverted_index_path)
    cv = CorpusView(recipes)

    # tokenize
    query_tokens = clean_text(raw_query)
    if not query_tokens:
        return []
    anchor = query_tokens[0]

    # dynamic query-stopword cho BM25 core
    q_eff = effective_query_tokens(query_tokens, inverted_index, cv.N, tau=0.25)

    # Stage-1: dùng bitset nếu có, ngược lại fallback cũ
    bsi = _load_bitset(bitset_path)
    if bsi is not None:
        cand_docs = stage1_bitset_candidates(
            query_tokens=query_tokens,
            anchor=anchor,
            bsi=bsi,
            cv=cv,
            k_coarse=stage1_k,
        )
    else:
        cand_docs = stage1_coarse_candidates(
            query_tokens=query_tokens,
            inverted_index=inverted_index,
            cv=cv,
            anchor=anchor,
            k_coarse=stage1_k,
        )

    # BM25 trên candidates
    scores = compute_bm25_scores(
        query_tokens=q_eff,
        inverted_index=inverted_index,
        cv=cv,
        k1=k1, b=b,
        title_boost=title_boost,
        ingredients_boost=ingredients_boost,
        candidate_docs=cand_docs,
    )
    if not scores:
        return []

    # must-have với anchor (nghiêm ngặt)
    strict_scores = must_have_with_anchor(
        scores=scores,
        cv=cv,
        inverted_index=inverted_index,
        query_tokens=query_tokens,
        anchor=anchor,
    )

    # fallback cho truy vấn rất ngắn (≤2 token)
    if not strict_scores and len(query_tokens) <= 2:
        filtered_scores = must_have_any_token(
            scores=scores,
            cv=cv,
            query_tokens=query_tokens,
            anchor=anchor,
        )
    else:
        filtered_scores = strict_scores

    if not filtered_scores:
        return []

    # generic re-rank
    scores = rerank_generic(
        scores=filtered_scores,
        cv=cv,
        inverted_index=inverted_index,
        query_tokens=query_tokens,
        prox_window=3,
        alpha_phrase_title=1.6,
        alpha_phrase_body=1.0,
        beta_prox_title=0.6,
        beta_prox_body=0.4,
        gamma_missing_idf=0.9,
    )

    # phrase tiering
    scores, title_phrase_hit = rerank_phrase_tiering(
        scores=scores,
        cv=cv,
        query_tokens=query_tokens,
        big_bonus_title=8.0,
        big_bonus_body=4.0,
    )

    # (giữ nhịp cũ: generic → phrase lặp lại)
    scores = rerank_generic(
        scores=scores,
        cv=cv,
        inverted_index=inverted_index,
        query_tokens=query_tokens,
        prox_window=3,
        alpha_phrase_title=1.6,
        alpha_phrase_body=1.0,
        beta_prox_title=0.6,
        beta_prox_body=0.4,
        gamma_missing_idf=0.9,
    )
    scores, title_phrase_hit = rerank_phrase_tiering(
        scores=scores,
        cv=cv,
        query_tokens=query_tokens,
        big_bonus_title=8.0,
        big_bonus_body=4.0,
    )

    # relevance tiering + final sort
    pack: List[Tuple[Tuple[int, float, bool], int, float]] = []
    for doc_id, s in scores.items():
        tier_info = compute_relevance_tier(doc_id, cv, query_tokens, anchor, prox_window=3)
        tier_info = (tier_info[0], tier_info[1], tier_info[2] or (doc_id in title_phrase_hit))
        pack.append((tier_info, doc_id, s))

    pack.sort(key=lambda x: (x[0][0], -x[2], -x[0][1], not x[0][2]))
    ranked = pack[:top_k]

    # build output
    results: List[SearchResult] = []
    for (_, _cov_ratio, _title_hit), doc_id, score in ranked:
        r = cv.recipes[doc_id]
        results.append(
            SearchResult(
                doc_id=doc_id,
                title=r.get("title", f"Recipe #{doc_id}"),
                url=r.get("url"),
                score=round(float(score), 6),
                snippet=build_snippet(r, raw_query),
            )
        )
    return results

# =============================================================================
# 10) CLI DEMO
# =============================================================================

def _print_results(results: List[SearchResult]) -> None:
    for i, res in enumerate(results, 1):
        print("=" * 80)
        print(f"[{i}] {res.title} (score={res.score})")
        print(f"URL: {res.url or '—'}")
        print(res.snippet)

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Module 3 - BM25 + Phrase/Proximity Re-rank (Strict & Fast) + Bitset Stage-1"
    )
    parser.add_argument("query", nargs="?", default="Canh chua tôm", type=str)
    parser.add_argument("--index", default="inverted_index.json")
    parser.add_argument("--data", nargs="+", default=["dienmayxanh.json", "monngonmoingay_multi.json"])
    parser.add_argument("--stage1", type=int, default=50, help="Số ứng viên lấy ở Stage-1 (lọc thô)")
    parser.add_argument("--bitset", default=None, help="Đường dẫn bitset.pkl (nếu có sẽ dùng Stage-1 siêu nhanh)")
    parser.add_argument("--topk", type=int, default=10)
    parser.add_argument("--title_boost", type=float, default=2.5)
    parser.add_argument("--ingredients_boost", type=float, default=1.2)
    parser.add_argument("--k1", type=float, default=1.5)
    parser.add_argument("--b", type=float, default=0.75)
    args = parser.parse_args()

    results = search(
        raw_query=args.query,
        inverted_index_path=args.index,
        recipe_files=args.data,
        top_k=args.topk,
        title_boost=args.title_boost,
        ingredients_boost=args.ingredients_boost,
        k1=args.k1,
        b=args.b,
        bitset_path=args.bitset,
        stage1_k=args.stage1,
    )
    if not results:
        print("Không tìm thấy kết quả phù hợp.")
    else:
        _print_results(results)

if __name__ == "__main__":
    main()
