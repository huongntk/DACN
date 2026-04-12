import os
import glob
import sys
import io
import re
import json
import pdfplumber
import pytesseract
from pdf2image import convert_from_path

# Cấu hình OCR
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
POPPLER_PATH = r"C:\poppler-25.07.0\Library\bin"
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

OUTPUT_JSON = "de_thi_tin_hoc_TNTHPT_2025.json"

# ===================== CÁC HÀM TIỆN ÍCH =====================
def extract_text_from_pdf(path):
    try:
        with pdfplumber.open(path) as pdf:
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            if text.strip():
                return text
    except Exception as e:
        print(f"Lỗi pdfplumber cho {path}: {e}")

    print(f"Không có text trong {path}, chuyển sang OCR...")
    images = convert_from_path(path, poppler_path=POPPLER_PATH)
    full_text = ""
    for i, img in enumerate(images):
        text = pytesseract.image_to_string(img, lang='vie')
        full_text += f"\n--- PAGE {i+1} ---\n{text}\n"
    return full_text

def clean_text(text):
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

# ===================== PHÂN TÍCH CÂU HỎI =====================
def parse_mc_question(question_text):
    num_match = re.search(r'C[âa]u\s*(\d+)', question_text)
    number = num_match.group(1) if num_match else "?"
    option_pattern = r'([A-D])\.\s*(.*?)(?=(?:[A-D]\.|$))'
    options = re.findall(option_pattern, question_text, re.DOTALL)
    parsed_options = [{"label": label, "content": clean_text(content)} for label, content in options]
    
    if parsed_options:
        first_opt = re.search(r'[A-D]\.', question_text)
        content = question_text[:first_opt.start()].strip() if first_opt else question_text
    else:
        content = question_text
    content = re.sub(r'^C[âa]u\s*\d+\s*[:\-]\s*', '', content).strip()
    
    return {
        "number": number,
        "content": clean_text(content),
        "options": parsed_options,
        "type": "mc"
    }

def parse_tf_question(question_text):
    """Trả về LIST 4 câu độc lập (stem + từng ý a,b,c,d)"""
    num_match = re.search(r'C[âa]u\s*(\d+)', question_text)
    original_number = int(num_match.group(1)) if num_match else -1

    if 1 <= original_number <= 2:
        q_type = "tf_common"
        part = None
    elif original_number in (3, 4):
        q_type = "tf_special"
        part = "computer_science"
    elif original_number in (5, 6):
        q_type = "tf_special"
        part = "applied_informatics"
    else:
        q_type = "tf_special"
        part = "unknown"

    # Lấy stem (phần trước ý a))
    option_start = re.search(r'[a-d]\)', question_text)
    stem = question_text[:option_start.start()].strip() if option_start else question_text
    stem = re.sub(r'^C[âa]u\s*\d+\s*[:\-]\s*', '', stem).strip()

    option_pattern = r'([a-d])\)\s*(.*?)(?=(?:[a-d]\)|$))'
    options = re.findall(option_pattern, question_text, re.DOTALL)

    parsed_questions = []
    for label, content in options:
        full_content = clean_text(stem + " " + label.upper() + ") " + content)
        parsed = {
            "number": str(original_number),   # sẽ gán lại sequential sau
            "content": full_content,
            "options": [],                    # KHÔNG còn options
            "type": q_type
        }
        if q_type == "tf_special":
            parsed["part"] = part
        parsed_questions.append(parsed)
    return parsed_questions

def parse_pdf_by_sections(text):
    results = {
        "multiple_choice": [],
        "true_false_common": [],
        "true_false_special": []
    }

    # Tìm vị trí phần
    pos1 = text.find("PHẦN I") if text.find("PHẦN I") != -1 else text.find("PHẦN I".lower())
    pos2 = text.find("PHẦN II") if text.find("PHẦN II") != -1 else text.find("PHẦN II".lower())
    if pos1 == -1: pos1 = re.search(r'PHẦN\s+I', text, re.IGNORECASE).start() if re.search(r'PHẦN\s+I', text, re.IGNORECASE) else -1
    if pos2 == -1: pos2 = re.search(r'PHẦN\s+II', text, re.IGNORECASE).start() if re.search(r'PHẦN\s+II', text, re.IGNORECASE) else -1

    section1 = text[pos1:pos2] if pos1 != -1 and pos2 != -1 else (text[pos1:] if pos1 != -1 else text)
    section2 = text[pos2:] if pos2 != -1 else ""

    # === PHẦN I: Trắc nghiệm ===
    mc_pattern = r'(?m)^C[âa]u\s+(\d+)\s*[:\.\-]\s*(.*?)(?=\nC[âa]u\s+\d+|\nPHẦN|\Z)'
    mc_matches = re.findall(mc_pattern, section1, re.DOTALL)
    for num, content in mc_matches:
        full_q = f"Câu {num}: {content}".strip()
        parsed = parse_mc_question(full_q)
        if 1 <= int(parsed["number"]) <= 24:
            results["multiple_choice"].append(parsed)

    # === PHẦN II: Đúng/Sai (SỬA REGEX – KHÔNG DÙNG ^) ===
    tf_pattern = r'C[âa]u\s+(\d+)\s*[:\.\-]\s*(.*?)(?=C[âa]u\s+\d+|\nB\.\s*PHẦN\s+RIÊNG|\Z)'
    tf_matches = re.findall(tf_pattern, section2, re.DOTALL)

    common_counter = 1
    special_counter = 1
    for num, content in tf_matches:
        full_q = f"Câu {num}: {content}".strip()
        parsed_list = parse_tf_question(full_q)
        for parsed in parsed_list:
            if parsed["type"] == "tf_common":
                parsed["number"] = str(common_counter)
                results["true_false_common"].append(parsed)
                common_counter += 1
            else:
                parsed["number"] = str(special_counter)
                results["true_false_special"].append(parsed)
                special_counter += 1

    # === FALLBACK (luôn chạy nếu TF rỗng) ===
    if len(results["true_false_common"]) != 8 or len(results["true_false_special"]) != 16:
        print("⚠ TF chưa đủ → chạy fallback toàn bộ văn bản...")
        all_questions = re.findall(r'(C[âa]u\s+(\d+)\s*[:\.\-].*?)(?=C[âa]u\s+\d+|\Z)', text, re.DOTALL)

        results["true_false_common"] = []
        results["true_false_special"] = []
        common_counter = 1
        special_counter = 1

        for full_q, num_str in all_questions:
            num = int(num_str)
            if 1 <= num <= 24 and not any(q["number"] == str(num) for q in results["multiple_choice"]):
                parsed = parse_mc_question(full_q)
                results["multiple_choice"].append(parsed)
            elif 1 <= num <= 6:
                parsed_list = parse_tf_question(full_q)
                for parsed in parsed_list:
                    if parsed["type"] == "tf_common":
                        parsed["number"] = str(common_counter)
                        results["true_false_common"].append(parsed)
                        common_counter += 1
                    else:
                        parsed["number"] = str(special_counter)
                        results["true_false_special"].append(parsed)
                        special_counter += 1

    # Sắp xếp
    results["multiple_choice"].sort(key=lambda x: int(x["number"]))
    results["true_false_common"].sort(key=lambda x: int(x["number"]))
    results["true_false_special"].sort(key=lambda x: int(x["number"]))
    return results

# ===================== PHÂN TÍCH ĐÁP ÁN (đã flat) =====================
def parse_answer_pdf(pdf_path):
    print(f"\nĐang đọc đáp án từ {pdf_path}...")
    answers_per_code = {
        "0501": {
            "multiple_choice": {"1":"D","2":"C","3":"A","4":"D","5":"D","6":"C","7":"C","8":"B","9":"A","10":"B","11":"D","12":"A","13":"D","14":"A","15":"B","16":"C","17":"A","18":"A","19":"A","20":"D","21":"D","22":"C","23":"B","24":"B"},
            "true_false_common": ["S","Đ","S","Đ","S","Đ","S","Đ"],
            "true_false_special": ["Đ","S","Đ","S","S","S","Đ","Đ","Đ","Đ","S","S","Đ","S","S","Đ"]
        },
        "0503": {
            "multiple_choice": {"1":"C","2":"C","3":"A","4":"C","5":"B","6":"D","7":"A","8":"A","9":"C","10":"D","11":"B","12":"C","13":"C","14":"D","15":"A","16":"C","17":"B","18":"B","19":"D","20":"D","21":"A","22":"C","23":"A","24":"D"},
            "true_false_common": ["Đ","Đ","Đ","S","Đ","S","Đ","S"],
            "true_false_special": ["Đ","S","S","Đ","S","Đ","S","Đ","S","S","Đ","Đ","Đ","Đ","S","S"]
        },
        "0537": {
            "multiple_choice": {"1":"D","2":"C","3":"B","4":"C","5":"D","6":"B","7":"D","8":"B","9":"B","10":"A","11":"A","12":"C","13":"B","14":"D","15":"A","16":"C","17":"C","18":"D","19":"A","20":"D","21":"D","22":"A","23":"D","24":"D"},
            "true_false_common": ["Đ","Đ","Đ","S","Đ","S","Đ","S"],
            "true_false_special": ["Đ","S","S","Đ","S","Đ","S","Đ","S","S","Đ","Đ","Đ","Đ","S","S"]
        },
        "0539": {
            "multiple_choice": {"1":"C","2":"B","3":"A","4":"B","5":"A","6":"B","7":"D","8":"A","9":"A","10":"A","11":"A","12":"A","13":"C","14":"C","15":"B","16":"D","17":"D","18":"A","19":"B","20":"C","21":"D","22":"B","23":"B","24":"C"},
            "true_false_common": ["S","Đ","S","Đ","S","Đ","S","Đ"],
            "true_false_special": ["Đ","S","Đ","S","S","S","Đ","Đ","Đ","Đ","S","S","Đ","S","S","Đ"]
        }
    }
    print("✅ Đáp án đã load (TF flat).")
    return answers_per_code

def merge_answers(questions_data, answers_per_code):
    for exam_code, exam in questions_data.items():
        if exam_code not in answers_per_code: continue
        ans = answers_per_code[exam_code]

        # MC
        for q in exam.get("multiple_choice", []):
            if q["number"] in ans["multiple_choice"]:
                q["correct_answer"] = ans["multiple_choice"][q["number"]]

        # TF common (flat list)
        for i, q in enumerate(exam.get("true_false_common", [])):
            if i < len(ans["true_false_common"]):
                q["correct_answer"] = ans["true_false_common"][i]

        # TF special (flat list)
        for i, q in enumerate(exam.get("true_false_special", [])):
            if i < len(ans["true_false_special"]):
                q["correct_answer"] = ans["true_false_special"][i]
    return questions_data

# ===================== MAIN =====================
def process_pdf(pdf_path):
    print(f"\nĐang xử lý: {pdf_path}")
    text = extract_text_from_pdf(pdf_path)
    results = parse_pdf_by_sections(text)
    print(f"   MC: {len(results['multiple_choice'])} | TF chung: {len(results['true_false_common'])} | TF riêng: {len(results['true_false_special'])}")
    return results

def main():
    pdf_files = glob.glob("*.pdf")
    answer_file = next((f for f in pdf_files if "TinHoc-2018" in f or "dap-an" in f.lower() or "answer" in f.lower()), None)
    if answer_file:
        pdf_files.remove(answer_file)
        answer_data = parse_answer_pdf(answer_file)
    else:
        answer_data = None

    all_results = {}
    for pdf in pdf_files:
        results = process_pdf(pdf)
        if results:
            all_results[os.path.splitext(pdf)[0]] = results

    if answer_data:
        all_results = merge_answers(all_results, answer_data)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n✅ HOÀN TẤT! File JSON: {OUTPUT_JSON}")
    print("   True_false_common  → 8 câu độc lập")
    print("   True_false_special → 16 câu độc lập")

if __name__ == "__main__":
    main()