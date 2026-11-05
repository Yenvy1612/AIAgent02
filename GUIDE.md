# Hướng dẫn sửa lại Knowledge Base (KB)

Tài liệu này mô tả cách đưa 37 tệp trong `data/kb/candidates/` thành một KB dùng được: đúng đường dẫn, đúng bản quyền, đúng hiệu lực, chunk sạch và truy xuất đo được.

> **Trạng thái (2026-11-04):** đã làm xong bước 1–5 và phần mã của kế hoạch, kể cả tìm web khi chat (tắt mặc định). Sau đó dự án đổi từ Qdrant sang pgvector; xem mục 8. Mọi chỗ nhắc Qdrant ở các mục cũ nay hiểu là pgvector. Các phần dưới giữ nguyên để làm căn cứ; xem mục 7 để biết chỗ đã làm khác đi và lỗi mới phát hiện.

Số liệu kiểm tra ngày 2026-11-04. Phần chạy thử dùng 10 nguồn, chế độ local và **chưa được duyệt nội dung**. Chỉ dùng số liệu đó để tìm lỗi, không dùng làm kết quả đánh giá.

## 1. Nguyên tắc không được phá vỡ

1. Một nguồn chỉ vào index khi có **cả hai** `review_status=approved` và `license_status=approved`, kèm tệp cục bộ và hash khớp.
2. Duyệt bản quyền không thay cho duyệt nội dung y khoa.
3. **Chỉ người có thẩm quyền mới được đặt `review_status=approved` và ký** trong `kb_manifest/source_review.md`. Không tự duyệt để làm các bài test chạy qua.
4. Muốn thử thì dùng manifest và index tạm (bước 5 ở mục 4). Không sửa trạng thái trong manifest thật để thử.

## 2. Các lỗi đang có

### Dữ liệu và bản quyền

| # | Mức | Vấn đề | Bằng chứng |
|---|---|---|---|
| D1 | Chặn | **12 tệp ADA 2026 cấm khai thác bằng máy.** Trang đầu mỗi tệp ghi không được dùng cho "text or data mining, machine learning, or similar technologies" nếu chưa có văn bản cho phép, và phải xin phép ADA khi đăng lên nền tảng bên thứ ba. | Có trong 12/12 tệp `ADA_2026_*` |
| D2 | Chặn | **6 `local_path` đã hỏng** vì tệp bị chuyển sang thư mục con: KB-01A, KB-18, KB-25, KB-27, KB-30A, KB-30B. | `kb_manifest/sources.csv` |
| D3 | Chặn | **Hash của KB-01A sai**: bản ghi có 65 ký tự (`404beeba…`), hash thật là `404beba5811b8894b0164ef4a926989b26d84d2c4099dc82d688a8fcf70595ae`. Sau khi duyệt, ingest sẽ báo `content_sha256 mismatch`. | `sources.csv`, `document_metadata.json`, `source_review.md` (2 chỗ) |
| D4 | Chặn | **KB-01 trang PDF 39 có nội dung đã bị đảo ngược.** Bản gốc: "insulin trộn không được khuyến cáo sử dụng thường quy". QĐ 1353 sửa thành: "Chế độ insulin nền – nhanh, trộn hỗn hợp (tiêm dưới da) là các lựa chọn…". Hệ thống hiện vẫn trả đoạn cũ, chỉ kèm một dòng lưu ý. | Trang 39 khớp "điểm b, mục 3, trang 37" |
| D5 | Cao | **Văn bản hết hiệu lực nằm chung với bản hiện hành.** Điều 3 của QĐ 5481 thay thế QĐ 3319 (2017). | Trang 1 của QĐ 5481 |
| D6 | Cao | **Tên tệp gây hiểu nhầm**: `BYT_QD3319_2017_Quyet_dinh_va_huong_dan…` chỉ có 1 trang quyết định, không có hướng dẫn, và chữ trích xuất bị lỗi font (`BOYTE`, `DQc l~p`). | Trích xuất PyMuPDF |
| D7 | Trung bình | Tệp trùng hoặc gần trùng: WHO PEN có 2 bản giống hệt nhau (SHA-256 `a09cc0ea…`); QĐ 2558 có 2 bản nội dung gần như nhau. | So hash và so nội dung |
| D8 | Trung bình | Mọi tài liệu mới chưa có dòng trong `sources.csv`. `document_metadata.json` chỉ có KB-01, KB-01A, KB-18. Tài liệu thiếu metadata bị gán mặc định `population=adult_type2`, kể cả khi sai đối tượng. | `scripts/ingest_kb.py` |
| D9 | Trung bình | Git index có 7 mục trạng thái `AD`, trỏ tới đường dẫn cũ. Bộ ADA chưa được theo dõi, nên `git add data/` sẽ đưa chúng vào. Không có remote nào được cấu hình, nên hiện chưa có gì bị đẩy lên. | `git status` |
| D10 | Trung bình | `Dockerfile` có `COPY data/ /app/data/`, nên mọi tệp trong `data/kb` (kể cả ADA) sẽ vào image. Ngược lại, `Tài liệu/` bị loại khỏi image, nên `local_path` hiện tại của KB-01 không tồn tại trong container. | `Dockerfile`, `.dockerignore` |
| D11 | Trung bình | Chưa thấy lời ghi nguồn hay miễn trừ chứng thực của CDC/WHO trong câu trả lời, dù `source_review.md` yêu cầu. | Tìm trong `backend/app/agent`, `api`, `frontend/src` |

### Mã nguồn (đo bằng chạy thử)

| # | Mức | Vấn đề | Kết quả đo | Vị trí |
|---|---|---|---|---|
| C1 | Chặn | **Câu hỏi ngoài lĩnh vực không bị từ chối**, vì điểm được chuẩn hóa theo kết quả cao nhất nên kết quả đầu gần như luôn cao. | "Giá cổ phiếu Apple…" → `OK`, KB-31 trang 11, điểm 0.98; "Cách nấu phở bò ngon?" → `OK`, điểm 0.98 | `retriever.py:185-190` |
| C2 | Chặn | **Mỗi tài liệu chỉ có một `topic`**, trong khi tìm kiếm lọc khớp tuyệt đối theo topic. | KB-T06 (hạ đường huyết) → `INSUFFICIENT_EVIDENCE`, dù KB-01 có nội dung liên quan | `retriever.py:257`, `ingest_kb.py` |
| C3 | Cao | **Câu hỏi tiếng Việt khó chạm tài liệu tiếng Anh ở chế độ local.** Chat thường gọi với `topic=None`, nên nguồn CDC/WHO bị lấn át. | Không lọc topic, "Chế độ ăn lành mạnh…" trả KB-31, KB-01, KB-32, không có KB-30A | `graph.py:220`, `retriever.py:31` |
| C4 | Cao | **Không nhận diện được mục**: chunk không có `section`. Ingest cũng gọi `chunk_pages` từng trang nên tên mục không mang sang trang sau. | 362/389 chunk (93%) | `chunker.py:10`, `chunker.py:50-56`, `ingest_kb.py` |
| C5 | Cao | **Chunk rác được đưa vào index**: mục lục, trang quyết định hành chính, tài liệu tham khảo, mảnh quá ngắn. | 38 chunk mục lục; 45 chunk dưới 100 token; nhỏ nhất 1 token | `ingest_kb.py` |
| C6 | Cao | **Trang chỉ có ảnh bị bỏ qua**, có thể làm mất sơ đồ hoặc bảng. | KB-01 tr.23; QĐ 3087 tr.15–16; WHO PEN tr.11 | `ingest_kb.py` |
| C7 | Trung bình | `content_sha256` trống vẫn qua kiểm tra (KB-18 đang như vậy). | | `ingest_kb.py:45-47` |
| C8 | Trung bình | Một tệp lỗi làm dừng toàn bộ lần ingest; `.docx` chưa được hỗ trợ và sẽ gây lỗi này. | | `loader.py:71`, `ingest_kb.py` |
| C9 | Thấp | `is_active` luôn là `True`, nên không thể giữ văn bản cũ ở trạng thái không hoạt động. Mục 3 tránh vấn đề này bằng cách không đưa văn bản cũ vào index. | | `ingest_kb.py` |
| C10 | Thấp | `snapshot_web_sources.py` ghi về gốc `candidates/` và đổi `local_path` trong manifest. Không chạy lại trước khi sửa. | | `snapshot_web_sources.py` |

Phần đang hoạt động đúng: ngưỡng chẩn đoán ở KB-01 trang 11 trích xuất đủ; cờ `amended` gắn đúng trang 39. `get_text(sort=True)` trộn hai cột trên trang ADA, nhưng tài liệu ADA đang bị loại nên chưa cần xử lý. Nếu sau này ADA đồng ý, phải sửa lỗi này trước khi ingest.

## 3. Quyết định cho từng tệp

Đây là **đề xuất** để người duyệt xác nhận. "Mã mới" có thể đổi, miễn là không trùng mã đã có.

### Đưa vào đợt 1 (vẫn phải qua duyệt)

| Mã | Tệp | topic mặc định | population | Bản quyền | Việc cần lưu ý |
|---|---|---|---|---|---|
| KB-01 | `BYT_KB-01_QD5481_2020_…pdf` | diagnosis | adult_type2 | unknown | Chưa xác nhận còn hiệu lực; tài liệu dành cho nhân viên y tế; xử lý D4 |
| KB-01A | `BYT_KB-01A_QD1353_2021_…pdf` | medication | adult_type2 | unknown | Duyệt cùng KB-01 |
| KB-31 (mới) | `BYT_QD1530_2023_…pdf` | foot_care | adult_diabetes_foot | unknown | KB-T25 vẫn phải từ chối hướng dẫn xử trí tại nhà |
| KB-32 (mới) | `BYT_QD3087_2020_…pdf` | diagnosis | prediabetes | unknown | Sao chép thủ công sơ đồ ở tr.15–16 nếu cần |
| KB-33 (mới) | `BYT_QD2558_2022_…_ban_ky_so.pdf` | complications | adult_diabetes_retinopathy | unknown | Dùng bản ký số |
| KB-16 | `WHO_2019_Classification_…pdf` | diagnosis | general | CC BY-NC-SA 3.0 IGO | Mã đã có trong manifest; chỉ cập nhật |
| KB-18 | `WHO_2020_PEN_…Primary_Health_Care.pdf` | management | primary_care | approved | Hash: `a09cc0ea4b39fd6ebfceb4d73f20bee7c4a7baeb3ae60150160cad646d6ec7e6` |
| KB-34 (mới) | `WHO_Type_2_Diabetes_Diagnosis_and_Management.pdf` | management | adult_type2 | CC BY-NC-SA 3.0 IGO | Loại nội dung của bên thứ ba |
| KB-25 | `CDC_KB-25_…md` | nutrition | adult_diabetes | approved | Bắt buộc có ghi nguồn và miễn trừ chứng thực |
| KB-27 | `CDC_KB-27_…md` | monitoring | adult_diabetes | approved | Tên trong manifest là "Managing Blood Sugar", tên tệp khác; thống nhất lại |
| KB-30A | `WHO_KB-30A_…md` | nutrition | general | approved | Nội dung chung, không riêng cho đái tháo đường |
| KB-30B | `WHO_KB-30B_…md` | activity | general | approved | Nội dung gồm nhiều nhóm đối tượng |

Với cột bản quyền của BYT: người duyệt cần xác nhận và ghi căn cứ, ví dụ quy định về văn bản hành chính trong Luật Sở hữu trí tuệ và việc tài liệu kèm quyết định có thuộc phạm vi đó hay không. Tài liệu này không kết luận thay.

### Để lại `candidates/`, chưa đưa vào

| Mã | Tệp | Lý do |
|---|---|---|
| KB-35 | `BYT_QD1470_2024_…docx` | Thai kỳ đang ngoài phạm vi (KB-03 là `OUT`, KB-T28 phải từ chối). Thay thế QĐ 6173/2018, không phải QĐ 3387 ghi ở KB-03. Cần bộ đọc `.docx` nếu đưa vào sau này. |
| KB-36 | `WHO_Guidelines_Medicines_and_Insulin_for_Diabetes.pdf` | Dành cho chuyên môn; câu hỏi về thuốc của hệ thống phần lớn phải chuyển nhân viên y tế. |
| KB-37 | `BYT_QD2557_2022_…pdf` | Quy trình kỹ thuật, ít giá trị cho câu hỏi của người dùng. |
| KB-38 | `WHO_Hypertension_Management_…pdf` | Ngoài trọng tâm đái tháo đường. |
| KB-39 | `WHO_Diabetes_Prevention_Control_…Framework.pdf` | Chỉ số giám sát cấp dân số. |

### Chuyển ra khỏi `candidates/`

| Đích | Tệp | Lý do |
|---|---|---|
| `rejected/license_blocked/` | 12 tệp `ADA_2026_*` | Điều khoản cấm khai thác dữ liệu (D1). Chỉ xét lại khi có văn bản cho phép. KB-06 đến KB-15 và KB-23 giữ `reference_only`; KB-T29 vẫn phải từ chối. |
| `rejected/license_blocked/` | `Diabetes_Plate_Method_Flyer.pdf` | Không có điều khoản cấp phép, có dẫn nguồn Diabetes Food Hub/ADA. KB-25 đã có nội dung Plate Method. |
| `rejected/out_of_scope/` | `ADA_2022_Introduction_…historical.pdf` | Bản cũ, chỉ nói về phương pháp, không có nội dung lâm sàng cần dùng. |
| `rejected/superseded/` | `BYT_QD3319_2017_…pdf`, `BYT_Huong_dan_DTD_typ2_2017.pdf` | Bị QĐ 5481 thay thế theo Điều 3. |
| `rejected/superseded/` | `BYT_QD3280_2011_…pdf`, `BYT_QT3798_2017_…pdf` | Cũ hơn hoặc dựa trên hướng dẫn 2017. Các tệp hiện có **không** nêu rõ việc bãi bỏ, nên người duyệt cần xác nhận rồi ghi căn cứ. |
| `rejected/duplicate/` | `WHO_2020_PEN_…_Duplicate_KB-18.pdf`, `BYT_QD2558_2022_Huong_dan_vong_mac_DTD.pdf` | Trùng với bản được chọn. |

`data/kb/rejected/*` đã nằm trong `.gitignore`. Các tệp được duyệt **vẫn để nguyên chỗ**: `data/kb/approved/*` cũng bị bỏ qua khi commit, nên chuyển vào đó sẽ khiến bản clone mới không dựng lại được index.

## 4. Các bước thực hiện

### Bước 1 — Sắp xếp tệp và Git

```powershell
$k = "data/kb/candidates"
New-Item -ItemType Directory -Force data/kb/rejected/license_blocked, data/kb/rejected/superseded, data/kb/rejected/duplicate, data/kb/rejected/out_of_scope

Move-Item "$k/B_ADA_Standards_of_Care/ADA_2026_*.pdf" data/kb/rejected/license_blocked/
Move-Item "$k/D_Dinh_duong_cho_nguoi_mac_dai_thao_duong/Diabetes_Plate_Method_Flyer.pdf" data/kb/rejected/license_blocked/
Move-Item "$k/B_ADA_Standards_of_Care/ADA_2022_*.pdf" data/kb/rejected/out_of_scope/
Move-Item "$k/A_Bo_Y_Te_Viet_Nam/BYT_QD3319_2017_*.pdf", "$k/A_Bo_Y_Te_Viet_Nam/BYT_Huong_dan_DTD_typ2_2017.pdf", "$k/A_Bo_Y_Te_Viet_Nam/BYT_QD3280_2011_*.pdf", "$k/A_Bo_Y_Te_Viet_Nam/BYT_QT3798_2017_*.pdf" data/kb/rejected/superseded/
Move-Item "$k/C_WHO/*_Duplicate_KB-18.pdf", "$k/A_Bo_Y_Te_Viet_Nam/BYT_QD2558_2022_Huong_dan_vong_mac_DTD.pdf" data/kb/rejected/duplicate/

# Bỏ 7 mục "AD" trỏ tới đường dẫn cũ khỏi Git index
git rm --cached --quiet -- data/kb/candidates/KB-01A_QD1353_2021.pdf data/kb/candidates/KB-01_QD5481_2020.pdf data/kb/candidates/KB-18_WHO_PEN_2020.pdf data/kb/candidates/KB-25_2026-11-03.md data/kb/candidates/KB-27_2026-11-03.md data/kb/candidates/KB-30A_2026-11-03.md data/kb/candidates/KB-30B_2026-11-03.md
```

Thêm vào `.dockerignore`:

```
data/kb/rejected/**
```

Sau đó xóa thư mục `B_ADA_Standards_of_Care` đã rỗng và cập nhật `data/kb/candidates/README.md`. Chạy `git status` để chắc chắn không có tệp ADA nào được đưa vào trước khi commit.

### Bước 2 — Sửa `kb_manifest/sources.csv`

Với mọi dòng ở bảng đợt 1:

- `local_path`: đường dẫn mới, dùng `/`, tính từ gốc repo. KB-01 trỏ sang `data/kb/candidates/A_Bo_Y_Te_Viet_Nam/BYT_KB-01_QD5481_2020_Huong_dan_DTD_typ2.pdf` (cùng hash với `Tài liệu/5481.pdf`).
- `content_sha256`: tính từ tệp thật, xem lệnh bên dưới. Sửa cả hash KB-01A ở `document_metadata.json` và `source_review.md`.
- `license_status` của KB-16, KB-34: chỉ đổi sau khi người duyệt xác nhận. Không sửa `review_status` ở bước này.
- Dòng mới: thêm KB-31 đến KB-39 với `review_status=candidate`, `priority` theo bảng ở mục 3.
- `source_url` của tài liệu mới: lấy từ trang chính thức. Tệp hiện có không đủ thông tin, nên **không đoán URL**.

```powershell
Get-ChildItem data/kb/candidates -Recurse -File | Where-Object Name -ne README.md |
  ForEach-Object { "{0}  {1}" -f (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower(), $_.Name }
```

Với tệp `.md`, `content_sha256` trong manifest là hash **của cả tệp**, khác với `content_sha256` ở front matter (chỉ phần thân). Không chép lẫn.

### Bước 3 — Bổ sung `kb_manifest/document_metadata.json`

Mỗi tài liệu đợt 1 cần một mục. Các trường `topic_by_page`, `exclude_pages`, `text_replacements` là trường mới, sẽ được hỗ trợ ở bước 4.

```json
{
  "source_code": "KB-01",
  "local_path": "data/kb/candidates/A_Bo_Y_Te_Viet_Nam/BYT_KB-01_QD5481_2020_Huong_dan_DTD_typ2.pdf",
  "document_version": "2020-12-30",
  "language": "vi",
  "population": "adult_type2",
  "supersedes": ["QĐ 3319/QĐ-BYT"],
  "amended_by": ["KB-01A"],
  "amended_sections": [
    {"pdf_page": 39, "printed_page": 37, "section": "Phần 5, mục 3, điểm b", "amended_by": "KB-01A"}
  ],
  "topic_by_page": [
    {"from": 11, "to": 12, "topic": "diagnosis"}
  ],
  "exclude_pages": [1, 5, 6],
  "text_replacements": [
    {
      "pdf_page": 39,
      "find": "<nguyên văn câu cũ, lấy từ text đã trích xuất>",
      "replace": "Chế độ insulin nền – nhanh, trộn hỗn hợp (tiêm dưới da) là các lựa chọn để kiểm soát glucose máu ở bệnh nhân có tăng glucose máu kèm bệnh nặng không nguy kịch",
      "authority": "KB-01A"
    }
  ]
}
```

Các giá trị `topic_by_page` và `exclude_pages` ở trên chỉ là ví dụ. Hãy lập danh sách đủ theo mục lục và kết quả chạy thử. Điểm bắt đầu phát hiện được:

- Tài liệu tham khảo: KB-01 từ tr.76, KB-16 từ tr.31, KB-31 từ tr.43, KB-32 từ tr.18. Cần xem lại vì tài liệu có thể còn phụ lục sau đó.
- Trang quyết định hành chính: KB-01, KB-31, KB-32 có ở tr.1. KB-01A **không được loại** vì toàn bộ nội dung sửa đổi nằm trên trang này.

### Bước 4 — Sửa mã nguồn

Làm theo thứ tự này. Mỗi thay đổi kèm test trong `tests/test_kb_pipeline.py`.

**`scripts/ingest_kb.py`**

1. C7: báo `missing content_sha256` khi hash trống. Các test đang tạo dòng approved không có hash phải bổ sung hash.
2. C8: bao `load_document` bằng `try/except`, ghi nguồn lỗi vào `blocked_sources` và tiếp tục.
3. C5: bỏ các trang trong `exclude_pages`. Gộp mảnh dưới khoảng 100 token vào chunk liền kề cùng trang.
4. D4: áp dụng `text_replacements` trước khi chunk. **Dừng ingest nếu không tìm thấy `find`**, để không âm thầm giữ lại câu cũ. Chuẩn hóa khoảng trắng trước khi so khớp vì PDF có xuống dòng giữa câu.
5. C2: chọn `topic` theo `topic_by_page`, nếu không có thì dùng `row["topic"]`.
6. C4: gom các trang trước khi xác định mục, hoặc truyền `initial_section` từ trang trước sang trang sau.
7. C6: ghi các trang chỉ có ảnh vào báo cáo `pages_needing_manual_review`. Nội dung quan trọng được chép tay thành tệp `.md` riêng, có người duyệt và ghi rõ trang gốc.
8. C9: đọc `is_active` từ metadata, mặc định `true`.

**`backend/app/rag/chunker.py`**

- C4: xét heading theo **từng dòng** thay vì cả đoạn. Bổ sung mẫu `^[IVXLC]+\.\s`, `^\d+(\.\d+)*\.?\s+\S` và dòng in hoa ngắn, kèm kiểm tra để không nhận nhầm các mục liệt kê như `1. Glucose…`.
- Không tách số mục khỏi tiêu đề. Hiện có kết quả dạng `1.` rồi xuống dòng `Chẩn đoán 1.1.`.

**`backend/app/rag/retriever.py`**

- C1: thêm ngưỡng trên **điểm thô, trước khi chuẩn hóa**, ví dụ tỷ lệ từ quan trọng của câu hỏi xuất hiện trong chunk. Hiệu chỉnh ngưỡng bằng tập câu hỏi ngoài phạm vi, không chọn theo cảm tính.
- C3: chọn một trong hai cách:
  - **Đề xuất:** dùng BGE-M3 + pgvector khi demo, vì mô hình hỗ trợ đa ngôn ngữ, và ghi rõ giới hạn của chế độ local.
  - Nếu phải chạy offline: thêm bảng thuật ngữ Việt–Anh để mở rộng câu truy vấn, và tìm riêng trên từng ngôn ngữ rồi gộp kết quả.

**`backend/app/agent/`**

- D11: thêm ghi nguồn cho câu trả lời có dẫn CDC/WHO. CDC cần câu miễn trừ chứng thực rõ ràng; WHO cần ghi nguồn và tuân thủ CC BY-NC-SA.
- D4: giữ dòng lưu ý về QĐ 1353 trong `graph.py:364-373`. Tên văn bản đang viết cứng theo `KB-01A`, cần đọc từ metadata nếu có thêm văn bản sửa đổi.

**Hỗ trợ `.docx`:** chưa cần ở đợt 1. Nếu đưa KB-35 vào sau này, cần thêm bộ đọc và đặt `population=pregnancy`.

### Bước 5 — Chạy thử bằng index tạm

Sao chép `sources.csv` thành `tmp/dry_manifest.csv`, chỉ trong bản sao này mới đặt hai trạng thái thành `approved` cho nguồn đợt 1:

```powershell
$env:DIACARE_RAG_MODE = "local"
python scripts/ingest_kb.py --manifest tmp/dry_manifest.csv --output tmp/dry_index.json
```

Không ghi đè `data/kb/index.json`. Thư mục `tmp/` chưa nằm trong `.gitignore`, nên hãy xóa hai tệp này sau khi xong để không commit nhầm. Đối chiếu với kết quả ban đầu:

| Chỉ số | Lúc kiểm tra | Yêu cầu sau khi sửa |
|---|---|---|
| Chunk không có `section` | 93% (362/389) | Giảm mạnh ở nhóm PDF; xem lại phần còn sót |
| Chunk dưới 100 token | 45 | Chỉ còn trường hợp có lý do |
| Chunk mục lục | 38 | 0 |
| Chunk tài liệu tham khảo, trang hành chính | Có | 0, trừ KB-01A |
| Câu "insulin trộn không được khuyến cáo" | Có ở tr.39 | 0 |
| Câu hỏi ngoài lĩnh vực | Trả `OK` | `INSUFFICIENT_EVIDENCE` |

Người duyệt nên đọc ngẫu nhiên một số chunk của mỗi tài liệu và so với PDF gốc, đặc biệt các bảng, vì bảng trong PDF đang bị làm phẳng thành văn xuôi.

### Bước 6 — Duyệt và ký

Với từng nguồn đợt 1, người duyệt:

1. Xác nhận tác giả, phiên bản và hiệu lực. Với KB-01/KB-01A, kiểm tra lại trang [dự thảo của Cục KCB](https://daithaoduong.kcb.vn/du-thao) xem đã có hướng dẫn mới chưa.
2. Xác nhận quyền lập chỉ mục và ghi căn cứ.
3. Xác nhận đối tượng áp dụng, nhất là tài liệu viết cho nhân viên y tế nhưng ứng dụng trả lời cho người dùng phổ thông.
4. Điền bảng kiểm trong `source_review.md`, thêm dòng cho nguồn mới, ký và ghi ngày.
5. Sau đó mới đổi `review_status` và `license_status` trong `sources.csv`.

### Bước 7 — Dựng index thật

```powershell
python scripts/verify_kb_sources.py   # Kiểm tra số nguồn và tệp
python scripts/ingest_kb.py           # Chỉ index local
python scripts/rebuild_kb.py          # Khi có pgvector: dựng lại cả local và vector
```

- Không có dòng `BLOCKED` nào với nguồn đợt 1.
- `rebuild_kb.py` báo lỗi nếu có chunk được duyệt nhưng thiếu URL Postgres. Nên dùng lệnh này thay cho `index_vectors.py`, vì nó thay toàn bộ bảng trong một transaction.
- Sau mỗi lần đổi tệp nguồn phải chạy lại, vì `chunk_id` chứa hash của tệp.

### Bước 8 — Cập nhật câu hỏi vàng và đánh giá

Trong `evaluation/rag/gold_questions.json`:

| Câu | Thay đổi |
|---|---|
| KB-T06, KB-T15 | KB-28 không có tệp và đang chờ làm rõ bản quyền. Chuyển sang KB-01 nếu người duyệt xác nhận nội dung phù hợp. |
| KB-T07, KB-T25 | KB-29 → KB-31. KB-T25 vẫn phải từ chối. |
| KB-T02 | Thêm nguồn mong đợi (hiện chưa có). |
| KB-T22 | Xác minh KB-25 có trả lời được câu này không: lần chạy thử trả KB-30A. |
| KB-T29 | Giữ nguyên, vì ADA vẫn chưa được duyệt. |
| Câu mới | Thêm câu ngoài lĩnh vực, câu về đoạn sửa đổi của QĐ 1353 và câu về nội dung đã bị thay thế. |

Người duyệt điền `gold_answer` và đặt `blocked_until_approved=false` cho câu đủ điều kiện. Sau đó chạy:

```powershell
python scripts/evaluate_kb.py
python -m pytest tests/test_kb_pipeline.py tests/test_acceptance.py
```

Mục tiêu G3 trong `docs/DESIGN_OBJECTIVES.md`: Recall@5 ≥ 0,90; Citation Accuracy ≥ 0,95; Refusal Accuracy ≥ 0,95; không có citation ngoài kết quả truy xuất. `evaluate_rag.py` chỉ kiểm tra citation về mặt **cấu trúc**, nên người duyệt vẫn phải kiểm tra mẫu xem đoạn trích có thật sự hỗ trợ câu trả lời hay không.

Nếu `DIACARE_LLM_ENABLED=true`, bước đánh giá có thể gửi đoạn trích đã duyệt tới Claude. Nên tắt cờ này khi đo truy xuất.

### Bước 9 — Cập nhật tài liệu

Cập nhật phần mô tả đã lỗi thời trong:

- `README.md`: đường dẫn cũ và câu "No documents are currently eligible".
- `docs/KB_DESIGN.md`: "0 sources ELIGIBLE, 32 BLOCKED" và đường dẫn cũ.
- `docs/EVALUATION_REPORT.md`: số đo mới, nêu rõ chế độ truy xuất đã dùng.
- `kb_manifest/source_review.md`: bảng nguồn, đường dẫn, hash và lý do loại ADA.
- `data/kb/candidates/README.md`: danh mục sau khi sắp xếp.

## 5. Điều kiện hoàn thành

- [ ] Không còn tệp ADA hoặc tệp bị loại trong `candidates/`, Git index hay Docker image.
- [ ] Mọi nguồn đợt 1 có đường dẫn đúng và hash 64 ký tự khớp với tệp.
- [ ] Mọi nguồn đợt 1 có đủ metadata và chữ ký của người duyệt.
- [ ] Index không chứa câu đã bị QĐ 1353 sửa, và có test bảo vệ điều này.
- [ ] Không có chunk từ QĐ 3319, hướng dẫn 2017 hoặc QĐ 3280.
- [ ] Câu hỏi ngoài lĩnh vực nhận `INSUFFICIENT_EVIDENCE`.
- [ ] Câu trả lời dẫn CDC/WHO có ghi nguồn và miễn trừ theo yêu cầu.
- [ ] Đánh giá đạt G3 và báo cáo ghi rõ chế độ truy xuất; toàn bộ test đạt.
- [ ] Tài liệu ở bước 9 đã khớp thực tế.

## 6. Các quyết định cần người phụ trách chốt

| Câu hỏi | Đề xuất | Ảnh hưởng |
|---|---|---|
| Ai là người duyệt nội dung y khoa và ký? | **Đã chốt (2026-11-04):** người phụ trách dự án tự duyệt và ký. Ghi đúng họ tên, chuyên môn và ngày ký trong `source_review.md`; nếu người ký không phải nhân viên y tế, ghi rõ KB là bản demo **chưa được thẩm định lâm sàng** | Không còn chặn bước 6 |
| Có xin ADA cho phép không? | Không cho đợt 1 | ADA đang là nguồn chính cho thuốc, tim mạch, thận |
| Hướng dẫn BYT viết cho nhân viên y tế có được dùng trả lời người dùng phổ thông không? | Có, nhưng chỉ ở mức thông tin chung và giữ nguyên Safety Gate | Ảnh hưởng KB-01, KB-31, KB-32, KB-33 |
| Demo chạy local hay BGE-M3 + pgvector? | BGE-M3 + pgvector | Quyết định cách xử lý C3 |
| Có đưa thai kỳ vào phạm vi không? | Không | Nếu có: cần KB-35, bộ đọc `.docx`, sửa KB-T28 |

## 7. Kết quả thực hiện và phát hiện mới

**Đã làm khác so với mục 4:**

- **C1 ở chế độ local:** ngưỡng độ phủ từ khóa không tách được câu trong và ngoài lĩnh vực, nên đã dùng bộ lọc chủ đề `backend/app/rag/scope.py`. Bộ lọc đạt 14/14 câu trong phạm vi và 0/12 câu ngoài phạm vi, nhưng các câu này cũng là căn cứ để lập danh sách từ khóa, nên con số chưa phải đánh giá độc lập.
- **Ngưỡng reranker:** đã có `DIACARE_RAG_MIN_RERANK_SCORE`, mặc định 0, **chưa hiệu chỉnh** vì chưa chạy được mô hình.
- **C3:** chọn BGE-M3 + pgvector; số đo ở `docs/EVALUATION_REPORT.md`.

**Lỗi mới phát hiện và đã sửa:**

- Dấu chữ ký số nằm chéo trang chen vào giữa câu ở KB-31 và KB-33 (ví dụ `mạn15:53:59tính`).
- Một số trang WHO PEN mất ngưỡng lâm sàng vì lỗi font; các trang này bị bỏ qua và liệt kê để duyệt.
- Chỉ một đoạn có liều thuốc đã làm cả câu trả lời bị chặn: 19/30 câu hỏi vàng ra `CLINICAL_REVIEW`, không có citation nào. Nay chỉ bỏ đúng đoạn đó.
- `evaluate_rag.py` truyền sai tên tham số nên không truy xuất được trong bước gọi agent.

**Việc còn mở, cần xử lý trước khi duyệt:**

1. KB-T25 (xử trí vết loét bàn chân tại nhà) và KB-T09 nhận câu trả lời có citation dù phải từ chối. Cần sửa trước khi duyệt KB-31.
2. Safety Gate Tier 2 báo nhầm cấp cứu với một số câu giáo dục thông thường; xem `docs/SAFETY_POLICY.md`.
3. Bản chạy thử ở chế độ local chưa đạt G3; xem `docs/EVALUATION_REPORT.md`.

## 8. Trạng thái sau khi duyệt (2026-11-04)

Chủ dự án đã duyệt 16 nguồn, và `data/kb/index.json` có 665 chunk. Chủ dự án không phải nhân viên y tế, nên KB là bản demo chưa thẩm định lâm sàng. KB-35 chưa duyệt, QT 3798 đã trả về `rejected/superseded/`. G3 chưa đạt ở chế độ local; số đo nằm trong `docs/EVALUATION_REPORT.md`.
