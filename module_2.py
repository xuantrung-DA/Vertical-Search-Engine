import json
import re
from collections import defaultdict
from underthesea import word_tokenize

# =============================
# 🔹 1. STOPWORDS (TỪ DỪNG)
# =============================
VIETNAMESE_STOPWORDS = {
    "và", "của", "là", "cho", "với", "những", "các", "được", "trong", "khi",
    "một", "bằng", "thì", "ở", "rồi", "để", "ra", "có", "này", "nên", "đến",
    "cũng", "như", "nhưng", "vào", "vì", "từ", "đó", "đang", "lúc"
}

# =============================
# 🔹 2. HÀM LÀM SẠCH VĂN BẢN
# =============================
def clean_text(text):
    """
    Chuẩn hóa và làm sạch văn bản:
    - Chuyển thành chữ thường
    - Bỏ ký tự đặc biệt
    - Tách từ tiếng Việt (underthesea)
    - Bỏ từ dừng
    """
    text = text.lower()

    # Giữ lại chữ cái tiếng Việt, số và dấu cách
    text = re.sub(r"[^a-z0-9àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễ"
                  r"ìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ\s]",
                  " ", text)

    # Tách từ (tokenization)
    tokens = word_tokenize(text)

    # Bỏ từ dừng và khoảng trắng
    tokens = [t for t in tokens if t.strip() and t not in VIETNAMESE_STOPWORDS]

    return tokens


# =============================
# 🔹 3. ĐỌC DỮ LIỆU
# =============================
def load_data(files):
    """
    Đọc danh sách file JSON chứa công thức nấu ăn
    Trả về danh sách recipes (mỗi recipe là 1 dict)
    """
    recipes = []
    for file in files:
        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)
            recipes.extend(data)
    print(f"Đã đọc {len(recipes)} công thức nấu ăn từ {len(files)} file.")
    return recipes


# =============================
# 🔹 4. XÂY DỰNG INVERTED INDEX
# =============================
def build_inverted_index(recipes):
    """
    Tạo chỉ mục ngược dạng:
    token -> {docID: {"freq": x, "positions": [pos1, pos2, ...]}}
    """
    inverted_index = {}

    for doc_id, recipe in enumerate(recipes):
        # Gộp nội dung thành 1 đoạn văn
        text = (
            recipe.get("title", "") + " "
            + " ".join(recipe.get("ingredients", [])) + " "
            + " ".join(recipe.get("instructions", []))
        )

        tokens = clean_text(text)

        for position, token in enumerate(tokens):
            if token not in inverted_index:
                inverted_index[token] = {}

            if doc_id not in inverted_index[token]:
                inverted_index[token][doc_id] = {"freq": 0, "positions": []}

            inverted_index[token][doc_id]["freq"] += 1
            inverted_index[token][doc_id]["positions"].append(position)

    print(f"Đã xây dựng chỉ mục cho {len(inverted_index)} từ khóa.")
    return inverted_index


# =============================
# 🔹 5. LƯU FILE JSON
# =============================
def save_index(inverted_index, filename="inverted_index.json"):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(inverted_index, f, ensure_ascii=False, indent=2)
    print(f"Đã lưu chỉ mục tại: {filename}")


# =============================
# 🔹 6. HÀM MAIN
# =============================
def main():
    # Bước 1: Đọc dữ liệu
    recipe_files = ["dienmayxanh.json", "monngonmoingay_multi.json"]
    recipes = load_data(recipe_files)

    # Bước 2: Xây dựng chỉ mục ngược
    inverted_index = build_inverted_index(recipes)

    # Bước 3: Lưu lại file
    save_index(inverted_index)


if __name__ == "__main__":
    main()
