# 🍳 Vertical Search Engine: Recipe Finder
> **Dự án Cuối kỳ:** Hệ thống tìm kiếm chuyên sâu công thức món ăn Việt Nam - **Đã hoàn thành và nghiệm thu.**

<p align="center">
  <img src="https://img.shields.io/badge/Status-Done-green?style=for-the-badge&logo=checkmarx" />
  <img src="https://img.shields.io/badge/Review-Graded%20by%20Lecturer-brightgreen?style=for-the-badge&logo=googlekeep" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Flask-000000?style=flat-square&logo=flask&logoColor=white" />
  <img src="https://img.shields.io/badge/MongoDB-47A248?style=flat-square&logo=mongodb&logoColor=white" />
  <img src="https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white" />
</p>

---

## 🎖 Kết quả Dự án
* **Trạng thái:** Hoàn thành (Finalized).
* **Đánh giá:** Đã được giảng viên review nội dung và chấm điểm tổng kết.
* **Ghi chú:** Hệ thống đáp ứng đầy đủ 5 module yêu cầu và vượt qua các bài kiểm tra đánh giá Precision/MAP.

---

## 🏗 Kiến trúc Hệ thống (System Architecture)
Hệ thống được chia thành 5 module chính, xây dựng theo quy trình xử lý dữ liệu và truy vấn hiện đại:

### 1. 🕷 Module Thu Thập Dữ Liệu (Crawling)
Tự động lấy dữ liệu từ các nguồn uy tín như *Điện Máy Xanh (Vào Bếp)* và *Món Ngon Mỗi Ngày*.
* **Công cụ:** `BeautifulSoup` (xử lý HTML tĩnh) & `Selenium` (xử lý nội dung động/JavaScript).
* **Chiến lược:** Tuân thủ `robots.txt`, giới hạn tần suất request để tránh spam.
* **Lưu trữ:** Dữ liệu thô được xuất ra định dạng `JSON` hoặc `MongoDB` để phục vụ tiền xử lý.

### 2. 📑 Xử Lý Văn Bản & Indexing
Chuyển đổi dữ liệu thô thành cấu trúc có thể tìm kiếm nhanh chóng.
* **NLP:** Sử dụng thư viện `underthesea` để tách từ tiếng Việt (Tokenization).
* **Preprocessing:** Chuyển chữ thường, loại bỏ Stopwords (và, của, là...), chuẩn hóa gốc từ.
* **Inverted Index:** Xây dựng chỉ mục ngược giúp ánh xạ từ khóa -> Danh sách tài liệu (DocID, Frequency, Position).

### 3. ⚖️ Truy Vấn & Xếp Hạng (Ranking)
Trái tim của máy tìm kiếm, đảm bảo kết quả trả về liên quan nhất.
* **Thuật toán:** Sử dụng trọng số **TF-IDF** để tính toán độ liên quan.
* **Boosting:** Thêm trọng số ưu tiên cho các trường quan trọng như `Tiêu đề món ăn` và `Nguyên liệu chính`.
* **Flow:** Query người dùng -> Preprocessing -> Scoring -> Ranked List.

### 4. 💻 Giao Diện Web (Web UI)
Demo hệ thống trực quan cho người dùng cuối.
* **Framework:** `Flask` (hoặc Django) tích hợp RESTful API.
* **Tính năng:**
    * Ô tìm kiếm thông minh.
    * Trang kết quả với Snippet (đoạn tóm tắt) có **highlight** từ khóa.
    * Phân trang (Pagination) và liên kết ngược về nguồn gốc của món ăn.

### 5. 📊 Đánh Giá Hệ Thống (Evaluation)
Đo lường hiệu quả bằng các chỉ số khoa học với bộ test 20 truy vấn mẫu.
* **Precision@10:** Độ chính xác trong 10 kết quả đầu tiên.
* **MAP (Mean Average Precision):** Đánh giá chất lượng xếp hạng tổng thể.
* **Ground Truth:** So sánh với tập kết quả chuẩn được gán nhãn thủ công.

---

## 🛠 My Stack & Tools
<p align="left">
  <a href="https://skillicons.dev">
    <img src="https://skillicons.dev/icons?i=py,flask,mongodb,selenium,docker,vscode,git&theme=dark" />
  </a>
</p>

---

## 📂 Danh mục Nộp bài (Deliverables)
| STT | Hạng mục | Mô tả |
|---|---|---|
| 1 | **Source Code** | Toàn bộ mã nguồn kèm comment chi tiết. |
| 2 | **Báo cáo PDF** | Giải thích kiến trúc, thuật toán và phân công công việc. |
| 3 | **Video Demo** | Video ngắn giới thiệu luồng hoạt động của web. |
| 4 | **Thuyết trình** | Slide trình bày và các câu hỏi Q&A. |

---

## 👥 Đội ngũ thực hiện
* **Nhóm trưởng:** Xuân Trung - Quản lý chung & Module Ranking.
* **Thành viên:** Thành Phát - Phát triển Crawler & Web UI.
* *Cùng sự đóng góp của các thành viên trong nhóm 5 người.*

---
<p align="center">
Built with ❤️ by AI Engineering Students
</p>
