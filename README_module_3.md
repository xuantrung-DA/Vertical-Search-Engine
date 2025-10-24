# Module 3 – Truy vấn & Xếp hạng kết quả (TF-IDF / BM25)
---

## Giới thiệu

Module 3 chịu trách nhiệm **xử lý truy vấn người dùng** và **xếp hạng kết quả** từ kho công thức món ăn.  
Hệ thống sử dụng **TF-IDF / BM25** kết hợp với **phrase-based re-ranking** và **bitset filtering** để tăng tốc độ truy xuất mà vẫn đảm bảo độ chính xác cao.

---

## Yêu cầu & Chuẩn đầu vào

| Thành phần | Mô tả |
|-------------|-------|
| **Chỉ mục đảo** | `inverted_index.json` hoặc `inverted_index.pkl` — được tạo từ Module 2 |
| **Dữ liệu gốc** | Một hoặc nhiều file `.json` chứa công thức, ví dụ:<br>`dienmayxanh.json`, `monngonmoingay_multi.json` |
| **Thư viện cần cài** | `underthesea`, `argparse`, `json`, `pickle` |
| **(Tuỳ chọn)** | `bitset.pkl` – file chỉ mục bitset được tạo từ `bitset.py` để tăng tốc lọc ứng viên |

---

## Mô tả hoạt động

### 1. Tiền xử lý truy vấn
- Chuyển chữ thường, loại bỏ ký tự đặc biệt.
- Tách từ bằng `underthesea.word_tokenize`.
- Loại bỏ stopwords tiếng Việt.

### 2. Lọc ứng viên (Stage-1)
- Nếu có `bitset.pkl`: sử dụng **Bitset** để chọn nhanh các tài liệu chứa token truy vấn (bit operation).
- Nếu không: dùng **union postings** trong `inverted_index` để tạo danh sách ứng viên thô.

### 3. Tính điểm TF-IDF / BM25
- Áp dụng công thức BM25 để tính điểm từng tài liệu.
- Gán trọng số theo trường:
  - `title_boost = 2.5`
  - `ingredients_boost = 1.2`
  - `instructions` (mặc định = 1.0)

### 4. Re-ranking (Phrase / Proximity)
- Ưu tiên tài liệu chứa **cụm từ chính xác** trong `title` hoặc `body`.
- Cộng điểm nếu các token truy vấn xuất hiện **gần nhau** (proximity).
- Giảm điểm nếu thiếu các **từ cốt lõi (essential terms)**.

### 5. Phân tầng liên quan (Relevance Tiering)
- **Tier 0:** exact phrase + anchor trong tiêu đề  
- **Tier 1:** đủ tất cả token truy vấn + anchor trong title/ingredients  
- **Tier ≥2:** cover một phần hoặc thiếu anchor

### 6. Xuất kết quả
Trả về danh sách tài liệu kèm:
- `title`  
- `url`  
- `score` (điểm BM25 tổng hợp)  
- `snippet` – đoạn văn bản chứa từ khóa được **highlight** bằng `**`

---

## Hướng dẫn cách chạy
### Chạy file bitset.py
```bash
python bitset.py --data dienmayxanh.json monngonmoingay_multi.json --out bitset_recipes.pkl
```
### Chạy bằng CLI
Nếu chưa chạy file bitset.py:
```bash
python Module3.py "canh chua tôm"   --index inverted_index.json   --data dienmayxanh.json monngonmoingay_multi.json   --topk 10
```

Nếu đã có bitset:
```bash
python Module3.py "gà kho gừng"   --index inverted_index.pkl   --data dienmayxanh.json monngonmoingay_multi.json   --bitset bitset_recipes.pkl   --topk 10
```

## Cấu trúc đầu ra

| Trường | Mô tả |
|---------|-------|
| `title` | Tiêu đề món ăn |
| `url` | Liên kết đến trang gốc |
| `score` | Điểm BM25 / TF-IDF tổng hợp |
| `snippet` | Đoạn văn bản chứa từ khóa được bôi đậm |

---

## Ví dụ kết quả

```
================================================================================
[1] Cách làm canh chua tôm chuẩn vị miền Tây (score=93.12)
    URL: https://www.dienmayxanh.com/vao-bep/cach-lam-canh-chua-tom-chuan-vi-mien-tay-23211
    Cách làm **canh chua tôm** đậm đà hương vị truyền thống miền Tây...
================================================================================
[2] Canh chua cá basa nấu tôm (score=84.05)
    URL: https://www.dienmayxanh.com/vao-bep/canh-chua-ca-basa-nau-tom-22593
    Món **canh chua cá** nấu **tôm** đơn giản, vị ngọt thanh...
```

---

## Ghi chú kỹ thuật

- Tối ưu tốc độ bằng:
  - Cache `CorpusView` (token/lens trung bình, idf cache)
  - Stage-1 lọc thô (Union postings hoặc Bitset)
  - Stage-2 xếp hạng chi tiết bằng BM25
- Có thể chuyển đổi chỉ mục JSON sang `.pkl` để tăng tốc load:
  ```bash
  python - <<'PY'
  import json, pickle
  with open("inverted_index.json","r",encoding="utf-8") as f: idx=json.load(f)
  with open("inverted_index.pkl","wb") as f: pickle.dump(idx,f,pickle.HIGHEST_PROTOCOL)
  PY
  ```

---
