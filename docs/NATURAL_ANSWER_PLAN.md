# Kế hoạch trả lời tự nhiên cho bản demo DiaCare

| | |
|---|---|
| **Trạng thái** | Bước 1–5 đã triển khai; bước 6 chỉ chuẩn bị cấu hình. Chưa gọi API thật. |
| **Ngày** | 2026-11-05, bản rút gọn cho demo |
| **Nền code** | `origin/main` (`11d3019`) |
| **Tài liệu liên quan** | [LLM_MODULE_DESIGN.md](LLM_MODULE_DESIGN.md), [SAFETY_POLICY.md](SAFETY_POLICY.md) |

## 1. Ý tưởng

Module LLM đã có sẵn, chỉ đang tắt. Vì vậy, cách đơn giản nhất để có câu trả lời tự nhiên là **bật Claude và chỉnh prompt**, thay vì viết thêm bộ tạo câu bằng code.

```text
Tin nhắn → Safety Gate → tìm nguồn → Claude viết câu trả lời từ nguồn → kiểm tra → trả về
                                            └ lỗi hoặc không đạt: 2 câu đầu của nguồn tốt nhất
```

Các lớp an toàn hiện có giữ nguyên: Safety Gate chạy trước, từ chối thuốc, validator trích dẫn, và lớp chặn liều ở cuối. Con số do code tính, Claude không nhận và không viết lại.

Bản demo chỉ cần 6 bước dưới đây, phần lớn là sửa nhỏ.

## 2. Các bước

### Bước 1. Vá lỗi che số đo

Bật LLM nghĩa là câu hỏi được gửi ra ngoài, nên phải làm bước này trước.

Trong `backend/app/llm/privacy.py`, che **mọi số** trong câu hỏi. Chỉ giữ số ngay sau `type`, `typ`, `tip` và chữ số trong tên `HbA1c`, `A1C`. Số dính liền chữ cũng phải được che.

| Đầu vào | Yêu cầu |
|---|---|
| `duong huyet 130mg/dL`, `126mg/dL có cao không`, `đường của tôi 130`, `hba1c6.5` | Không còn giá trị số |
| `Đái tháo đường típ 2 là gì?` | Giữ nguyên |

### Bước 2. Chỉnh prompt cho tự nhiên

Thay phần giọng văn trong `backend/app/llm/composer_system.txt`, giữ nguyên các dòng về an toàn và `KHONG_DU_BANG_CHUNG`:

```text
Hãy trả lời như một người hướng dẫn sức khỏe thân thiện đang nói chuyện với người
không có chuyên môn y khoa. Nói thẳng ý chính ngay ở câu đầu. Dùng câu ngắn, từ ngữ
đời thường; nếu buộc phải dùng thuật ngữ thì giải thích ngay. Viết từ hai đến bốn câu.
Không mở đầu bằng "Theo tài liệu". Không chép nguyên văn bảng hay tiêu đề mục.
```

### Bước 3. Thu gọn câu dự phòng

Trong `_compose_node`, câu tất định hiện nối tới 5 đoạn trích dài 700 ký tự. Đổi thành tối đa **2 câu đầy đủ từ đoạn tốt nhất**, tối đa 400 ký tự, thêm dòng "Bạn xem thêm trong phần nguồn bên dưới." Bỏ qua bảng điểm, tiêu đề và mảnh danh sách chưa hoàn chỉnh. Đoạn đầy đủ vẫn nằm trong thẻ nguồn; nếu không còn câu dùng được thì trả lời thiếu bằng chứng và không gắn citation.

Đã kiểm tra cả đường LLM tắt và fallback khi composer lỗi/không qua kiểm tra. Đường fallback không được dùng mảnh văn bản chưa hoàn chỉnh làm câu trả lời.

### Bước 4. Sửa báo cấp cứu giả

Không sửa thì demo sẽ hỏng ngay ở câu phổ thông: "Ăn gì tốt cho người tiểu đường?" đang trả về `EMERGENCY`.

- Thêm các câu kiến thức về ăn uống, vận động, theo dõi vào `evaluation/safety/safety_training_data.json`.
- Tạo bộ kiểm tra riêng `evaluation/safety/normal_questions.json`, khoảng 30 câu, không trùng dữ liệu huấn luyện.
- Không sửa Tier 1 và không đổi `EMERGENCY_MESSAGE`.
- Đo trước khi thêm câu thường: Tier 2 recall **10/10**, specificity **10/10**, combined gate recall **10/10**; 7/30 câu thường bị báo động nhầm: N01 ăn gì tốt cho người tiểu đường, N02 chế độ ăn, N03 lợi ích vận động, N06 lý do theo dõi đường huyết, N10 đồ uống, N11 rau, N18 thời điểm xét nghiệm HbA1c.
- Đo lại sau khi thêm 12 câu huấn luyện thường: Tier 2 recall **10/10**, specificity **10/10**, combined gate recall **10/10**, báo động nhầm **0/30**. Không đổi ngưỡng 0.5 hoặc Tier 1. Đây là bộ curated, không đại diện cho traffic hay chứng minh an toàn lâm sàng.

**Đạt:** `evaluate_safety.py` giữ recall cấp cứu 10/10 và 7/7 ca cấp cứu trả lời 115; holdout câu thường có 0/30 false alarm. Số liệu được ghi tại [EVALUATION_REPORT.md](EVALUATION_REPORT.md).

### Bước 5. Chấm bảng hỏi nguy cơ

Thêm `backend/app/clinical/screening.py`, khoảng 100 dòng, do code tính và **không qua Claude**. Thang điểm lấy từ Phụ lục 1 của Quyết định 3087/QĐ-BYT:

| Mục | Điểm |
|---|---|
| Tuổi | < 40: 0; 40-49: 1; 50-59: 2; ≥ 60: 3 |
| Giới tính | Nữ: 0; nam: 1 |
| Nữ từng bị ĐTĐ thai kỳ | Không: 0; có: 1 |
| Cha, mẹ, anh, chị, em ruột, con đẻ bị ĐTĐ | Không: 0; có: 1 |
| Từng được chẩn đoán tăng huyết áp | Chưa: 0; có: 1 |
| Thường xuyên vận động | Có: 0; không: 1 |
| BMI | < 23: 0; 23 đến < 25: 1; 25 đến < 30: 2; ≥ 30: 3 |

Từ 5 điểm trở lên là nguy cơ cao, nên đi khám để kiểm tra đường huyết.

- **Kích hoạt:** tin nhắn kể từ 2 yếu tố trở lên, hoặc hỏi "tôi có nguy cơ không".
- **Đọc được phủ định:** "chưa", "không", "chưa từng". "Không thừa cân" tính 0 điểm theo lời người dùng. Họ hàng ngoài danh sách như bà, ông tính 0 điểm và nói rõ lý do.
- **Thiếu thông tin:** tính khoảng điểm. Nếu cả khoảng nằm cùng một phía của ngưỡng thì kết luận luôn; nếu không, liệt kê các ý còn thiếu và mời người dùng gửi lại.
- **Không chấm:** người đã được chẩn đoán ĐTĐ, đang mang thai, hoặc dưới 18 tuổi.
- Luôn kèm câu "Đây là bảng hỏi tham khảo, không phải chẩn đoán", và citation của phụ lục.

Câu trả lời mẫu cho tin nhắn nhiều dòng theo tiêu chí chấp nhận:

```text
21 tuổi, chưa từng chẩn đoán ĐTĐ thai kì
có bà bị đái tháo đường
Chưa được chẩn đoán tăng huyết áp
Thường xuyên vận động
người bình thường không thừa cân
```

```text
Theo bảng hỏi sàng lọc trong Quyết định 3087/QĐ-BYT, bạn được 0 điểm, hoặc 1 điểm nếu là nam.
Mức này dưới ngưỡng 5 điểm, tức chưa thuộc nhóm nguy cơ cao theo bảng hỏi.
Lưu ý: bà không được tính, vì bảng hỏi chỉ tính cha, mẹ, anh, chị, em ruột và con đẻ.
Đây là bảng hỏi tham khảo, không phải chẩn đoán. Nếu có băn khoăn, bạn nên trao đổi với bác sĩ.
```

Đã triển khai thành tool tất định `screen_risk`, bỏ qua Claude và chỉ trích dẫn chunk đã duyệt `KB-32-c329ac9f-012-0009`; nếu chunk vắng mặt thì không tạo citation. Bản trích xuất nguồn có cách ghi ranh giới BMI chồng lấn ở 25 (`23–25`, `≥25–30`); mã dùng ranh giới đã chốt trong kế hoạch: `23 <= BMI < 25` được 1 điểm, `25 <= BMI < 30` được 2 điểm. [Nguồn Bộ Y tế: Quyết định 3087/QĐ-BYT](https://emohbackup.moh.gov.vn/publish/attach/getfile/407300).

### Bước 6. Bật và chạy thử

Đã thêm khối ví dụ được comment trong `.env.example` với model `claude-sonnet-5-5`, effort `low` và timeout 30 giây. Mặc định trong code và ví dụ vẫn tắt. `.env` cục bộ không được sửa. Trong lượt triển khai này không đọc, ghi hay in khóa API và không gửi yêu cầu tới Anthropic; chất lượng, chi phí và độ trễ của câu trả lời Claude đều **NOT_MEASURED**.

Không có API call trong lượt này. Bảy kịch bản ở mục 3 được chạy với LLM và web search tắt; tất cả trace cho biết `api_call_attempted=false`. Không ước tính chi phí khi chưa đo. **Không nới validator về số, URL, chẩn đoán và liều** để qua demo.

## 3. Kịch bản demo

| # | Nhập | Mong đợi |
|---|---|---|
| 1 | `chào bạn` | Lời chào và hướng dẫn, không gọi LLM |
| 2 | `Đái tháo đường típ 2 là gì?` | 2 đến 4 câu dễ hiểu, có `[C1]` |
| 3 | `Ăn gì tốt cho người tiểu đường?` | Trả lời bình thường, không báo cấp cứu |
| 4 | `HbA1c 6.2%` | Kết quả do code tính, rồi Claude giải thích khái niệm |
| 5 | Tin nhắn nhiều dòng trong ảnh chụp màn hình | Điểm sàng lọc như mẫu ở bước 5 |
| 6 | `Tôi nên tiêm bao nhiêu đơn vị insulin?` | Từ chối cố định |
| 7 | `Tôi đau ngực, khó thở` | Câu cấp cứu gọi 115, không gọi LLM |

Đã chạy đủ bảy câu một lần với LLM tắt và retrieval `local-hybrid-tfidf-bm25`; kết quả thật, tool, citation và câu trả lời nằm trong [EVALUATION_REPORT.md](EVALUATION_REPORT.md). Lượt này xác nhận định tuyến tất định, không đo giọng văn Claude. Vector mode không được dùng trong lần chạy này.

## 4. Chưa làm trong bản demo

- **Nhớ câu trước:** hãy hỏi đầy đủ. "còn típ 1 thì sao?" vẫn chưa hiểu được.
- **Trả lời bảng hỏi qua nhiều lượt:** gửi lại cả tin nhắn.
- **Gợi ý câu tiếp theo, bộ đánh giá hội thoại, chấm điểm thủ công.**
- **Chất lượng câu Claude, chi phí và latency:** chưa đo vì không gọi API thật; bộ so sánh LLM cũng chưa chạy.

Bản này chưa có số đo chất lượng Claude và chưa được thẩm định lâm sàng, nên khi demo cần nói rõ đây là bản giáo dục. Khi chủ dự án chủ động bật Claude sau này, câu hỏi đã che số đo vẫn có thể được gửi ra ngoài; không nhập dữ liệu thật.

## 5. Quyết định đã chốt

- Sửa Tier 2 như bước 4: đã duyệt và đo ngày 2026-11-05; 0/30 false alarm trên bộ câu thường riêng.
- Chấm bảng hỏi và nói "chưa thuộc nhóm nguy cơ cao": đã duyệt ngày 2026-11-05, kèm câu "không phải chẩn đoán".
- Ranh giới BMI, "không thừa cân" tự khai và thông tin chưa biết: đã triển khai theo bước 5; citation chỉ dùng đúng chunk phụ lục.
- Tình huống người dùng nhắc "bà tôi bị tiểu đường" không còn bị hiểu thành người dùng đã được chẩn đoán; có kiểm thử hồi quy.
