# Kế hoạch trả lời tự nhiên cho bản demo DiaCare

| | |
|---|---|
| **Trạng thái** | Đề xuất, chưa triển khai |
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

Trong `_compose_node`, câu tất định hiện nối tới 5 đoạn trích dài 700 ký tự. Đổi thành **2 câu đầu của đoạn tốt nhất**, cắt đúng cuối câu, tối đa 400 ký tự, thêm dòng "Bạn xem thêm trong phần nguồn bên dưới." Bỏ qua đoạn là bảng điểm hoặc tiêu đề mục. Đoạn đầy đủ vẫn nằm trong thẻ nguồn.

Câu này chỉ hiện khi Claude lỗi hoặc không qua kiểm tra, nên chỉ cần đọc được.

### Bước 4. Sửa báo cấp cứu giả

Không sửa thì demo sẽ hỏng ngay ở câu phổ thông: "Ăn gì tốt cho người tiểu đường?" đang trả về `EMERGENCY`.

- Thêm các câu kiến thức về ăn uống, vận động, theo dõi vào `evaluation/safety/safety_training_data.json`.
- Tạo bộ kiểm tra riêng `evaluation/safety/normal_questions.json`, khoảng 30 câu, không trùng dữ liệu huấn luyện.
- Không sửa Tier 1 và không đổi `EMERGENCY_MESSAGE`.

**Đạt khi:** `evaluate_safety.py` vẫn giữ nguyên kết quả cấp cứu (10/10 và 7/7), và phần lớn bộ câu thường không còn bị báo cấp cứu. Chủ dự án xem số đo trước khi merge.

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

Câu trả lời mẫu cho tin nhắn trong ảnh chụp màn hình:

```text
Theo bảng hỏi sàng lọc trong Quyết định 3087/QĐ-BYT, bạn được 0 điểm, hoặc 1 điểm nếu là nam.
Mức này dưới ngưỡng 5 điểm, tức chưa thuộc nhóm nguy cơ cao theo bảng hỏi.
Lưu ý: bà không được tính, vì bảng hỏi chỉ tính cha, mẹ, anh, chị, em ruột và con đẻ.
Đây là bảng hỏi tham khảo, không phải chẩn đoán. Nếu có băn khoăn, bạn nên trao đổi với bác sĩ.
```

### Bước 6. Bật và chạy thử

Trong `.env`, chỉ dành cho demo:

```text
DIACARE_LLM_ENABLED=true
ANTHROPIC_API_KEY=<khóa của chủ dự án>
DIACARE_ANTHROPIC_MODEL=claude-sonnet-5-5
DIACARE_LLM_EFFORT=low
DIACARE_LLM_TIMEOUT_SECONDS=30
```

Mặc định trong code vẫn là tắt. Đây là lần đầu gọi API thật, nên chủ dự án chạy kịch bản ở mục 3 và xem `llm_composer` trong trace. Chi phí ước tính khoảng 0,03 USD mỗi câu, chưa đo. Nếu câu nào rơi về đường dự phòng, xem mã lỗi trước khi sửa. **Không nới validator về số, URL, chẩn đoán và liều** để qua demo.

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

Trước buổi demo, nên chạy thử cả 7 câu để chắc chắn mạng và API key hoạt động. Vẫn cần giữ Docker, vì vector search cho nguồn tốt hơn.

## 4. Chưa làm trong bản demo

- **Nhớ câu trước:** hãy hỏi đầy đủ. "còn típ 1 thì sao?" vẫn chưa hiểu được.
- **Trả lời bảng hỏi qua nhiều lượt:** gửi lại cả tin nhắn.
- **Gợi ý câu tiếp theo, bộ đánh giá hội thoại, chấm điểm thủ công.**
- **Sửa nốt `evaluate_llm.py`:** chỉ ảnh hưởng số đo, không ảnh hưởng demo.

Bản này chưa có số đo chất lượng và chưa được thẩm định lâm sàng, nên khi demo cần nói rõ đây là bản giáo dục. Câu hỏi đã che số đo vẫn được gửi tới Anthropic, và người dùng không nên nhập dữ liệu thật.

## 5. Quyết định đã chốt

- Sửa Tier 2 như bước 4: đã duyệt ngày 2026-11-05; chủ dự án xem số đo trước khi merge.
- Chấm bảng hỏi và nói "chưa thuộc nhóm nguy cơ cao": đã duyệt ngày 2026-11-05, kèm câu "không phải chẩn đoán".
- Ranh giới BMI, "không thừa cân" tự khai và thông tin chưa biết: làm như bước 5.
