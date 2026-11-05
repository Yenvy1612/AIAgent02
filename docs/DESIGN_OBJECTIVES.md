# Mục tiêu thiết kế DiaCare AI v1.1

Các chỉ số dưới đây là **mục tiêu nghiên cứu để đánh giá prototype**, không phải cam kết hiệu năng lâm sàng. Chỉ ghi đạt khi có bộ dữ liệu/ca đánh giá, phương pháp và kết quả đo được lưu lại.

**Mục tiêu tổng quát:** Xây dựng bản demo học thuật DiaCare AI chứng minh rằng một AI Agent có thể kết hợp mô hình học máy trên dữ liệu có cấu trúc và tri thức y khoa có trích dẫn để hỗ trợ thông tin về đái tháo đường típ 2, trong khi các quyết định an toàn được kiểm soát độc lập với LLM.

| Mã | Mục tiêu | Tiêu chí đạt |
|---|---|---|
| G1 | **An toàn trước hết:** mọi tin nhắn đi qua Safety Gate trước Agent; cấp cứu phản hồi ngay, không chờ ML/RAG/LLM | 100% ca cấp cứu trong bộ kiểm thử nhận thông điệp gọi 115; vẫn hoạt động khi Vector DB hoặc LLM lỗi; 0 lần đề xuất liều thuốc/insulin |
| G2 | **ML đúng bài toán:** phân loại nhãn hiện mắc từ 6 biến không xét nghiệm, tách biệt với diễn giải xét nghiệm | So sánh LR/RF/XGBoost trên cùng tập test; báo cáo Recall, F1, ROC-AUC, PR-AUC, Brier cho bản có/không xét nghiệm; Recall ≥ 0,90 là mục tiêu nghiên cứu, chọn ngưỡng trên validation |
| G3 | **Tri thức có căn cứ:** nhận định y khoa có trích dẫn tài liệu đã duyệt; thiếu nguồn thì từ chối | Recall@5 ≥ 0,90; Citation Accuracy ≥ 0,95; Refusal Accuracy ≥ 0,95; không có citation ngoài kết quả truy xuất. Đo với web fallback tắt; câu trả lời từ web có nhãn chưa duyệt là ngoại lệ được chấp nhận, không tính vào G3 |
| G4 | **Agent điều phối minh bạch:** chọn đúng trong 5 tools và hiển thị trace | Đo Tool Selection Accuracy trên bộ test; tối đa 3–5 lượt gọi tool mỗi câu hỏi; mọi câu trả lời có trace |
| G5 | **Dữ liệu và đơn vị chính xác:** hỗ trợ mg/dL và mmol/L, không tự đoán đơn vị/loại xét nghiệm | 100% ca đơn vị trong bộ kiểm thử đạt; thiếu đơn vị thì hỏi lại; Safety Gate đánh giá cách hiểu nguy hiểm hơn khi có thể |
| G6 | **Khả thi và tái lập:** chạy lại trên máy khác bằng một lệnh Docker Compose | `docker compose up --build`; cố định seed, phiên bản dữ liệu/mô hình; chỉ dùng hồ sơ giả lập |

## Ngoài phạm vi

- Chẩn đoán, kê đơn, chỉnh liều thuốc hoặc đặt mục tiêu điều trị cá nhân.
- Dự đoán nguy cơ mắc bệnh trong tương lai khi dataset chỉ có nhãn hiện mắc.
- Dữ liệu bệnh nhân thật, đăng nhập và phân quyền.
- Dự báo glucose bằng LSTM, nhắc lịch, dashboard bác sĩ hoặc gửi yêu cầu tới bác sĩ thật.
- Tuyên bố hiệu năng trên người Việt Nam.

## Thứ tự ưu tiên

**An toàn (G1) > tính có căn cứ (G3) > độ chính xác dữ liệu (G5) > hiệu năng mô hình (G2) > trải nghiệm và tốc độ phản hồi.**

## Trạng thái hiện tại của prototype

G1–G6 là tiêu chí cần đo, không phải kết quả đạt sẵn. Các mục ML và RAG phải giữ trạng thái **chưa đo** cho tới khi có dataset được rà soát, nguồn KB được duyệt và báo cáo thực nghiệm. Xem [bảng đánh giá](EVALUATION_REPORT.md).
