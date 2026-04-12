import re
import json
import time
import pandas as pd
from tqdm import tqdm
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# ==================== CẤU HÌNH API & FILE ====================
GEMINI_API_KEY = ""  
GROQ_API_KEY = ""

JSON_PATH = "de_thi_tin_hoc_TNTHPT_2025_cleaned1.json"
CSV_OUTPUT = "final_benchmark_v2.csv"   # File mới với cấu trúc đầy đủ

GROQ_MODEL = "llama-3.3-70b-versatile"
BACKUP_GROQ_MODELS = ["mixtral-8x7b-32768", "gemma2-9b-it"]

# ==================== KHỞI TẠO CLIENT ====================
from google import genai
from groq import Groq

gemini_client = genai.Client(api_key=GEMINI_API_KEY)
groq_client = Groq(api_key=GROQ_API_KEY)

# ==================== PROMPT PHÂN LOẠI BLOOM ====================
BLOOM_PROMPT_4_LEVELS = """
Bạn là chuyên gia đánh giá câu hỏi giáo dục theo thang Bloom sửa đổi. Hãy phân loại câu hỏi dưới đây vào **MỘT** trong 4 cấp độ sau:

1. **Nhận biết**: Nhớ lại kiến thức, định nghĩa, khái niệm.
2. **Thông hiểu**: Giải thích, tóm tắt, so sánh.
3. **Vận dụng**: Áp dụng kiến thức vào tình huống cụ thể.
4. **Vận dụng cao**: Phân tích, đánh giá, giải pháp mới.

**QUAN TRỌNG**: Chỉ trả lời bằng **một số duy nhất**: 1, 2, 3 hoặc 4. Không giải thích thêm.

**Câu hỏi cần phân loại**:
{question}

**Cấp độ Bloom (1-4):**
"""

# ==================== PROMPT ĐÁNH GIÁ ====================
def build_eval_prompt(q):
    if q["type"] == "mcq":
        options = "\n".join([f"{k}. {v}" for k, v in q["options"].items()])
        return f"""Chọn đáp án đúng (A, B, C hoặc D). Chỉ trả lời 1 chữ cái.

{q['question']}
{options}"""
    else:  # tf_common hoặc tf_special
        return f"""Trả lời chỉ bằng một từ: Đúng hoặc Sai.

{q['question']}"""

# ==================== TRÍCH XUẤT ĐÁP ÁN ====================
def extract_mcq_answer(text):
    match = re.search(r"\b([A-D])\b", text.upper())
    return match.group(1) if match else None

def extract_tf_single(text):
    text = text.upper().strip()
    if any(x in text for x in ["ĐÚNG", "Đ"]):
        return "Đ"
    if any(x in text for x in ["SAI", "S"]):
        return "S"
    return None

# ==================== CHẤM ĐIỂM ====================
def evaluate(q, pred):
    if q["type"] == "mcq":
        return 1 if pred == q["answer"] else 0
    else:
        return 1 if pred == q["answer"] else 0

# ==================== CHUYỂN ĐỔI JSON → DATASET (ID PHÂN BIỆT, CÓ TYPE) ====================
def convert_dataset(raw_data):
    questions = []
    for exam_code, exam in raw_data.items():
        # Trắc nghiệm
        for mc in exam.get("multiple_choice", []):
            opts = {opt["label"]: opt["content"] for opt in mc.get("options", [])}
            questions.append({
                "id": f"{exam_code}_mc_{mc['number']}",
                "type": "mcq",
                "question": mc["content"],
                "options": opts,
                "answer": mc["correct_answer"],
                "full_text_for_bloom": mc["content"] + "\n\nCác lựa chọn:\n" +
                                       "\n".join([f"{opt['label']}. {opt['content']}" for opt in mc.get("options", [])])
            })

        # True/False phần chung
        for tf in exam.get("true_false_common", []):
            questions.append({
                "id": f"{exam_code}_tf_c_{tf['number']}",
                "type": "tf_common",
                "question": tf["content"],
                "options": {},
                "answer": tf["correct_answer"],
                "full_text_for_bloom": tf["content"]
            })

        # True/False phần riêng
        for tf in exam.get("true_false_special", []):
            questions.append({
                "id": f"{exam_code}_tf_s_{tf['number']}",
                "type": "tf_special",
                "question": tf["content"],
                "options": {},
                "answer": tf["correct_answer"],
                "full_text_for_bloom": tf["content"]
            })
    return questions

# ==================== GỌI API ====================
def ask_gemini(prompt, max_retries=8, base_delay=12):
    if prompt is None or prompt.strip() == "":
        return None
    for attempt in range(max_retries):
        try:
            response = gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            if "429" in str(e).lower() or "resource_exhausted" in str(e).lower():
                wait = 30
                print(f"⏳ Gemini quota → chờ {wait}s...")
                time.sleep(wait)
            else:
                print(f"⚠️ Gemini lỗi: {e}")
                time.sleep(5)
    return None

def ask_groq_eval(prompt, max_retries=8):
    if prompt is None or prompt.strip() == "":
        return None
    for attempt in range(max_retries):
        try:
            response = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=100
            )
            return response.choices[0].message.content.strip()
        except Exception:
            time.sleep(3)
    return None

def classify_bloom(question_text):
    models = [GROQ_MODEL] + BACKUP_GROQ_MODELS
    for model_name in models:
        try:
            resp = groq_client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": BLOOM_PROMPT_4_LEVELS.format(question=question_text)}],
                temperature=0.0,
                max_tokens=10
            )
            answer = resp.choices[0].message.content.strip()
            match = re.search(r'\b[1-4]\b', answer)
            if match:
                return int(match.group())
        except Exception:
            continue
    return None

# ==================== HÀM MIGRATE CSV CŨ (NẾU CÓ) ====================
def migrate_old_csv(old_path, new_path, raw_data):
    """
    Đọc file CSV cũ (chỉ có cột id, question, correct, gemini,...),
    chuyển đổi ID sang định dạng mới (_tf_c_, _tf_s_) và thêm cột 'type'.
    Lưu thành file mới với đầy đủ cột.
    """
    if not os.path.exists(old_path):
        return

    print("🔁 Phát hiện file CSV cũ, đang chuyển đổi sang định dạng mới...")
    df_old = pd.read_csv(old_path, encoding='utf-8-sig')

    # Xây dựng mapping ID cũ -> ID mới và type từ JSON
    id_map = {}
    type_map = {}
    for exam_code, exam in raw_data.items():
        for mc in exam.get("multiple_choice", []):
            old_id = f"{exam_code}_mc_{mc['number']}"
            new_id = old_id
            id_map[old_id] = new_id
            type_map[new_id] = "mcq"
        for tf in exam.get("true_false_common", []):
            old_id = f"{exam_code}_tf_{tf['number']}"
            new_id = f"{exam_code}_tf_c_{tf['number']}"
            id_map[old_id] = new_id
            type_map[new_id] = "tf_common"
        for tf in exam.get("true_false_special", []):
            old_id = f"{exam_code}_tf_{tf['number']}"
            new_id = f"{exam_code}_tf_s_{tf['number']}"
            id_map[old_id] = new_id
            type_map[new_id] = "tf_special"

    # Áp dụng mapping
    df_old['id'] = df_old['id'].map(id_map).fillna(df_old['id'])
    # Thêm cột type
    df_old['type'] = df_old['id'].map(type_map)

    # Sắp xếp lại cột theo đúng thứ tự mong muốn
    cols = ['id', 'type', 'question', 'correct', 'gemini', 'gemini_score', 'groq', 'groq_score', 'bloom']
    # Đảm bảo tất cả các cột cần thiết đều có mặt (nếu thiếu thì tạo rỗng)
    for col in cols:
        if col not in df_old.columns:
            df_old[col] = None
    df_new = df_old[cols]

    df_new.to_csv(new_path, index=False, encoding='utf-8-sig')
    print(f"✅ Đã tạo file mới: {new_path} với {len(df_new)} dòng.")
    return df_new

# ==================== MAIN ====================
if __name__ == "__main__":
    # Đọc JSON
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    dataset = convert_dataset(raw_data)
    print(f"📚 Tổng số câu hỏi sau khi convert: {len(dataset)}")

    # Nếu tồn tại file CSV cũ (tên cũ final_benchmark_with_bloom.csv) thì migrate
    OLD_CSV = "final_benchmark_with_bloom.csv"
    if os.path.exists(OLD_CSV) and not os.path.exists(CSV_OUTPUT):
        migrate_old_csv(OLD_CSV, CSV_OUTPUT, raw_data)

    # Load hoặc tạo DataFrame mới
    if os.path.exists(CSV_OUTPUT):
        df = pd.read_csv(CSV_OUTPUT, encoding='utf-8-sig')
        print(f"📂 Đã load file CSV hiện có: {len(df)} dòng.")
    else:
        df = pd.DataFrame(columns=['id', 'type', 'question', 'correct', 'gemini', 'gemini_score', 'groq', 'groq_score', 'bloom'])
        print("🆕 Tạo file CSV mới.")

    # Đảm bảo đầy đủ cột
    for col in ['type', 'gemini', 'gemini_score', 'groq', 'groq_score', 'bloom']:
        if col not in df.columns:
            df[col] = None

    # Duyệt từng câu hỏi trong dataset
    for q in tqdm(dataset, desc="🚀 Đang benchmark"):
        qid = q["id"]
        mask = df['id'] == qid
        if mask.any():
            row_idx = df[mask].index[0]
        else:
            # Tạo dòng mới với đầy đủ thông tin
            new_row = {
                "id": qid,
                "type": q["type"],
                "question": q["question"],
                "correct": q["answer"]
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            row_idx = df.index[-1]

        prompt_eval = build_eval_prompt(q)
        updated = False

        # Gemini
        if pd.isna(df.at[row_idx, 'gemini']) or df.at[row_idx, 'gemini'] is None:
            gemini_out = ask_gemini(prompt_eval)
            if gemini_out:
                ans = extract_mcq_answer(gemini_out) if q["type"] == "mcq" else extract_tf_single(gemini_out)
                score = evaluate(q, ans)
                df.at[row_idx, 'gemini'] = ans
                df.at[row_idx, 'gemini_score'] = score
                updated = True
                print(f"✅ [Gemini] {qid} → {score} điểm")

        # Groq
        if pd.isna(df.at[row_idx, 'groq']) or df.at[row_idx, 'groq'] is None:
            groq_out = ask_groq_eval(prompt_eval)
            if groq_out:
                ans = extract_mcq_answer(groq_out) if q["type"] == "mcq" else extract_tf_single(groq_out)
                score = evaluate(q, ans)
                df.at[row_idx, 'groq'] = ans
                df.at[row_idx, 'groq_score'] = score
                updated = True
                print(f"✅ [Groq]   {qid} → {score} điểm")

        # Bloom
        if pd.isna(df.at[row_idx, 'bloom']) or df.at[row_idx, 'bloom'] is None:
            bloom_level = classify_bloom(q["full_text_for_bloom"])
            if bloom_level is not None:
                df.at[row_idx, 'bloom'] = bloom_level
                updated = True
                print(f"✅ [Bloom]  {qid} → Level {bloom_level}")

        if updated:
            # Lưu ngay sau mỗi cập nhật
            df.to_csv(CSV_OUTPUT, index=False, encoding='utf-8-sig')

    print("\n🎉 HOÀN TẤT!")
    print(f"Kết quả được lưu tại: {CSV_OUTPUT}")
    print("   • Mỗi câu trắc nghiệm = 1 điểm")
    print("   • Mỗi ý đúng/sai (a,b,c,d) = 1 điểm")