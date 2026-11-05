const API = '/api/v1';

export const INITIAL_MESSAGE = {
  role: 'assistant',
  content: 'Xin chào, mình là DiaCare AI. Mình có thể tính BMI, giải thích một số ngưỡng xét nghiệm, xem lịch sử hồ sơ mô phỏng và tìm nội dung KB đã được duyệt. Mình không chẩn đoán hay tư vấn liều thuốc.',
  status: 'OK',
};

export async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data?.detail?.code || data?.detail?.message || 'Không thể kết nối API.');
  return data;
}
