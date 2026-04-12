import pandas as pd
import re
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
# ==================== 1. Đọc dữ liệu ====================
df = pd.read_csv('benchmark_results1.csv', encoding='utf-8-sig')
df = df.dropna(subset=['id'])  # bỏ dòng trống nếu có

# ==================== 2. Xác định dạng câu ====================
def get_question_type(id_str):
    if '_mc_' in id_str:
        return 'Trắc nghiệm'
    elif '_tf_common_' in id_str:
        return 'Đúng-sai chung'
    elif '_tf_special_' in id_str:
        return 'Đúng-sai riêng'
    else:
        return 'Khác'

df['question_type'] = df['id'].apply(get_question_type)

# ==================== 3. Xác định mức độ Bloom ====================
def classify_bloom(question):
    question = question.lower()
    if re.search(r'\b(định nghĩa|liệt kê|nhận biết|mô tả|trình bày)\b', question):
        return 'Nhớ'
    elif re.search(r'\b(giải thích|phân tích|so sánh|mô tả)\b', question):
        return 'Hiểu'
    elif re.search(r'\b(vận dụng|áp dụng|sử dụng)\b', question):
        return 'Vận dụng'
    elif re.search(r'\b(phân tích|đánh giá|so sánh)\b', question):
        return 'Phân tích'
    elif re.search(r'\b(sáng tạo|thiết kế|lập kế hoạch)\b', question):
        return 'Sáng tạo'
    else:
        return 'Không xác định'

df['bloom'] = df['question'].apply(classify_bloom)

# ==================== 4. Điểm số ====================
# Đảm bảo cột điểm là số
df['gemini_score'] = pd.to_numeric(df['gemini_score'], errors='coerce')
df['groq_score'] = pd.to_numeric(df['groq_score'], errors='coerce')

# ==================== 5. Thống kê ====================
# Tổng điểm trung bình
print("=== Điểm trung bình tổng thể ===")
print(df[['gemini_score', 'groq_score']].mean())

# Theo dạng câu
print("\n=== Điểm trung bình theo dạng câu ===")
group_type = df.groupby('question_type')[['gemini_score', 'groq_score']].mean()
print(group_type)

# Theo mức độ Bloom
print("\n=== Điểm trung bình theo mức độ Bloom ===")
group_bloom = df.groupby('bloom')[['gemini_score', 'groq_score']].mean()
print(group_bloom)

# Theo dạng câu + Bloom
print("\n=== Điểm trung bình theo dạng câu & Bloom ===")
group_both = df.groupby(['question_type', 'bloom'])[['gemini_score', 'groq_score']].mean()
print(group_both)

# ==================== 6. Lưu kết quả ====================
with pd.ExcelWriter('benchmark_analysis.xlsx') as writer:
    # Chi tiết từng câu
    df_detail = df[['id', 'question', 'correct', 'gemini', 'gemini_score', 'groq', 'groq_score', 'question_type', 'bloom']]
    df_detail.to_excel(writer, sheet_name='Chi tiết', index=False)
    
    # Thống kê theo dạng câu
    group_type.to_excel(writer, sheet_name='Theo dạng câu')
    
    # Thống kê theo Bloom
    group_bloom.to_excel(writer, sheet_name='Theo Bloom')
    
    # Thống kê kết hợp
    group_both.to_excel(writer, sheet_name='Kết hợp')

print("\nĐã lưu kết quả vào file 'benchmark_analysis.xlsx'")