# app.py

import re
from flask import Flask, render_template, request

# Import hàm search từ module 3 của bạn
# Đảm bảo module_3.py ở cùng thư mục với app.py
from module_3 import search as perform_search 

app = Flask(__name__)

# =============================================================================
# CẤU HÌNH CÁC ĐƯỜNG DẪN VÀ THAM SỐ
# =============================================================================
# Thay đổi các giá trị này nếu bạn đặt tên file khác
INVERTED_INDEX_PATH = "inverted_index.json"
RECIPE_FILES = ["dienmayxanh.json", "monngonmoingay_multi.json"]
BITSET_PATH = "bitset_recipes.pkl"  # Đặt là None nếu không dùng bitset
TOP_K = 10 # Số kết quả tối đa muốn hiển thị
SCORE_THRESHOLD = 10  # Ngưỡng điểm tối thiểu (tăng để lọc kết quả yếu)


# =============================================================================
# ĐỊNH NGHĨA CÁC ROUTE (ĐƯỜNG DẪN WEB)
# =============================================================================

@app.route('/')
def index():
    """Hiển thị trang chủ với form tìm kiếm."""
    return render_template('index.html')


@app.route('/search')
def search_results():
    """
    Xử lý query, tìm kiếm và hiển thị trang kết quả.
    URL: /search?query=thịt+kho
    """
    # Lấy query từ URL, ví dụ: ?query=thịt kho
    query = request.args.get('query', '')

    results = []
    if query:
        # Gọi hàm search từ module_3.py
        search_results = perform_search(
            raw_query=query,
            inverted_index_path=INVERTED_INDEX_PATH,
            recipe_files=RECIPE_FILES,
            bitset_path=BITSET_PATH,
            top_k=TOP_K,
            score_threshold=SCORE_THRESHOLD,
            # Các tham số khác có thể giữ mặc định từ module_3
            stage1_k=50,
            title_boost=2.5,
            ingredients_boost=1.2,
            k1=1.5,
            b=0.75
        )

        # Xử lý snippet để highlight bằng HTML
        for res in search_results:
            # Thay thế markdown **word** thành <strong>word</strong>
            # DÙNG DẤU CHẤM (.) ĐỂ TRUY CẬP ATTRIBUTE
            snippet_html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', res.snippet)
            res.snippet = snippet_html # Gán lại giá trị cho attribute
            results.append(res)
            
    # Render template `results.html` và truyền query cùng kết quả vào
    return render_template('results.html', query=query, results=results)


# =============================================================================
# CHẠY ỨNG DỤNG
# =============================================================================
if __name__ == '__main__':
    # prewarm: build cache 1 lần (truy vấn rất ngắn)
    try:
        perform_search(
            raw_query="Cá kho",  # bất kỳ
            inverted_index_path=INVERTED_INDEX_PATH,
            recipe_files=RECIPE_FILES,
            bitset_path=BITSET_PATH,
            top_k=1,
            stage1_k=10,
        )
    except Exception as _:
        pass

    app.run(debug=False)  # tắt debug cho hiệu năng và tránh reload tốn CPU