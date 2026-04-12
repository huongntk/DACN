import pandas as pd
import sys

# Thiết lập encoding cho console
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# ==================== 1. Đọc dữ liệu ====================
df = pd.read_csv('final_benchmark_v2.csv', encoding='utf-8-sig')
df = df.dropna(subset=['id'])  # Loại bỏ dòng trống nếu có

# ==================== 2. Chuẩn hóa tên loại câu hỏi ====================
type_mapping = {
    'mcq': 'Trắc nghiệm (MCQ)',
    'tf_common': 'Đúng/Sai chung (TF Common)',
    'tf_special': 'Đúng/Sai riêng (TF Special)'
}
df['question_type'] = df['type'].map(type_mapping).fillna('Khác')

# ==================== 3. Sử dụng cột Bloom có sẵn ====================
# Đảm bảo cột 'bloom' là số (nếu có giá trị lỗi thì chuyển thành NaN)
df['bloom'] = pd.to_numeric(df['bloom'], errors='coerce')
# Đổi tên để dễ hiểu khi hiển thị
bloom_labels = {
    1.0: 'Nhớ (1)',
    2.0: 'Hiểu (2)',
    3.0: 'Vận dụng (3)',
    4.0: 'Phân tích (4)'
}
df['bloom_level'] = df['bloom'].map(bloom_labels).fillna('Không xác định')

# ==================== 4. Điểm số ====================
df['gemini_score'] = pd.to_numeric(df['gemini_score'], errors='coerce')
df['groq_score'] = pd.to_numeric(df['groq_score'], errors='coerce')

# ==================== 5. Thống kê tổng quan ====================
print("=== KẾT QUẢ TỔNG QUAN ===")
total_questions = len(df)
gemini_correct = (df['gemini_score'] == 1).sum()
groq_correct = (df['groq_score'] == 1).sum()
gemini_acc = gemini_correct / total_questions
groq_acc = groq_correct / total_questions

print(f"Tổng số câu hỏi: {total_questions}")
print(f"Gemini - Đúng: {gemini_correct}, Accuracy: {gemini_acc:.2%}")
print(f"Groq   - Đúng: {groq_correct}, Accuracy: {groq_acc:.2%}")

# ==================== 6. Thống kê theo dạng câu hỏi ====================
print("\n=== ĐIỂM TRUNG BÌNH THEO DẠNG CÂU HỎI ===")
group_type = df.groupby('question_type').agg(
    Số_câu=('id', 'count'),
    Gemini_Đúng=('gemini_score', lambda x: (x == 1).sum()),
    Groq_Đúng=('groq_score', lambda x: (x == 1).sum()),
    Gemini_TB=('gemini_score', 'mean'),
    Groq_TB=('groq_score', 'mean')
)
group_type['Gemini_Accuracy'] = group_type['Gemini_Đúng'] / group_type['Số_câu']
group_type['Groq_Accuracy'] = group_type['Groq_Đúng'] / group_type['Số_câu']
print(group_type[['Số_câu', 'Gemini_Accuracy', 'Groq_Accuracy']])

# ==================== 7. Thống kê theo mức Bloom ====================
print("\n=== ĐIỂM TRUNG BÌNH THEO MỨC BLOOM ===")
group_bloom = df.groupby('bloom_level').agg(
    Số_câu=('id', 'count'),
    Gemini_Đúng=('gemini_score', lambda x: (x == 1).sum()),
    Groq_Đúng=('groq_score', lambda x: (x == 1).sum())
)
group_bloom['Gemini_Accuracy'] = group_bloom['Gemini_Đúng'] / group_bloom['Số_câu']
group_bloom['Groq_Accuracy'] = group_bloom['Groq_Đúng'] / group_bloom['Số_câu']
print(group_bloom[['Số_câu', 'Gemini_Accuracy', 'Groq_Accuracy']])

# ==================== 8. Thống kê kết hợp Dạng câu & Bloom ====================
print("\n=== ĐIỂM TRUNG BÌNH THEO DẠNG CÂU & BLOOM ===")
group_both = df.groupby(['question_type', 'bloom_level']).agg(
    Số_câu=('id', 'count'),
    Gemini_Đúng=('gemini_score', lambda x: (x == 1).sum()),
    Groq_Đúng=('groq_score', lambda x: (x == 1).sum())
)
group_both['Gemini_Accuracy'] = group_both['Gemini_Đúng'] / group_both['Số_câu']
group_both['Groq_Accuracy'] = group_both['Groq_Đúng'] / group_both['Số_câu']
print(group_both[['Số_câu', 'Gemini_Accuracy', 'Groq_Accuracy']])

# ==================== 9. Xuất ra file Excel ====================
with pd.ExcelWriter('benchmark_analysis.xlsx') as writer:
    # Sheet chi tiết từng câu
    df_detail = df[['id', 'type', 'question', 'correct', 'gemini', 'gemini_score',
                    'groq', 'groq_score', 'bloom', 'question_type', 'bloom_level']]
    df_detail.to_excel(writer, sheet_name='Chi tiết', index=False)

    # Sheet tổng hợp theo dạng câu
    group_type.to_excel(writer, sheet_name='Theo dạng câu')

    # Sheet tổng hợp theo Bloom
    group_bloom.to_excel(writer, sheet_name='Theo Bloom')

    # Sheet kết hợp
    group_both.to_excel(writer, sheet_name='Kết hợp')

print("\n✅ Đã lưu kết quả phân tích vào file 'benchmark_analysis.xlsx'")