import json
import re
import sys

# Đảm bảo stdout có thể in Unicode nếu môi trường hỗ trợ
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def clean_text(text: str) -> str:
    """Clean text: fix encoding, typos, special characters."""
    if not isinstance(text, str):
        return text

    replacements = {
        '\x92': "'", '\x93': '"', '\x94': '"', '\x96': '-',
        '“': '"', '”': '"', '’': "'", '‘': "'",
        '…': '...', '—': '-', '–': '-',
        'nbsp;': ' ', '&nbsp;': ' ',
        '\\r': ' ', '\\n': '\n', '\r': ' ', '\u200b': '',
        '†': '', '‡': '', '€': 'e', '°': '°',
        '½': '1/2', '¼': '1/4', '¾': '3/4', 
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    typos = {
        'tắn công': 'tấn công',
        'phỗ biến': 'phổ biến',
        'chần đoán': 'chẩn đoán',
        'thẳm định': 'thẩm định',
        'm wiếu': 'in phiếu',
        'ưng dụng': 'ứng dụng',
        'cầu hình': 'cấu hình',
        'thông mình': 'thông minh',
        'không ồn định': 'không ổn định',
        'cần trọng': 'cẩn trọng',
        'ủm bè': 'bạn bè',
        'tíin nhắn': 'tin nhắn',
        'dâu hiệu': 'dấu hiệu',
        'Nộp tiên đặt cọc': 'Nộp tiền đặt cọc',
        'kll(ìllg': 'không',
        'ưưong': 'trường',
        'JmaTram': 'maTram',
        'za7ram': 'maTram',
        'njietDoTB': 'nhietDoTB',
        'zaNhom': 'maNhom',
        'zzaL,oai': 'maLoai',
        'soLaoDong..': 'soLaoDong',
        'hen kết': 'liên kết',
        'ffllet kế': 'thiết kế',
        'fflay thế': 'thay thế',
        'ủan mềm': 'phần mềm',
        'ủa.n mềm': 'phần mềm',
        'zx<': 'mắc',
        'm1c': 'mắc',
        '7?aKV': 'maKV',
        '/a7ïnh': 'maTinh',
        'danSoTB': 'danSoTB',
        'en7ïnh': 'tenTinh',
        'en7ram': 'tenTram',
    }
    for wrong, right in typos.items():
        text = text.replace(wrong, right)

    text = re.sub(r'\n\s*\n', '\n', text)
    text = re.sub(r' +', ' ', text)
    text = text.strip()
    return text

def clean_code_blocks(text: str) -> str:
    """Clean common code errors in Python/C++ snippets."""
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        line = re.sub(r'range\(1l,', 'range(1,', line)
        line = re.sub(r'range\(8, 10\):', 'range(8, 10):', line)
        line = re.sub(r'for \(inti =', 'for (int i =', line)
        line = re.sub(r'i+r\+', 'i++', line)
        line = re.sub(r'while \(j >= 0 &&§', 'while (j >= 0 &&', line)
        line = re.sub(r'AI\[j \+ 1\] = AI\[j\]', 'A[j + 1] = A[j]', line)
        line = re.sub(r'AI\[3\]', 'A[j]', line)
        line = re.sub(r'AIj \+ 1\] = x', 'A[j + 1] = x', line)
        line = re.sub(r'35371', 'j = j - 1;', line)
        line = re.sub(r'3=3 -= 1', 'j = j - 1', line)
        line = re.sub(r'if\(i%2==0:', 'if i % 2 == 0:', line)
        line = re.sub(r'if\(i1%3 2 = 0\)', 'if (i % 2 == 0)', line)
        line = re.sub(r'else: x= x // 3', 'else: x = x // 3', line)
        line = re.sub(r'x= x / 3;', 'x = x / 3;', line)
        line = re.sub(r'x=zx*2', 'x = x * 2', line)
        line = re.sub(r'print\(s\[x\]\)', 'print(s[x])', line)
        line = re.sub(r'cout << s\[x\];', 'cout << s[x];', line)
        line = re.sub(r'S=Ss+i', 'S = S + i', line)
        line = re.sub(r'S=sri', 'S = S + i', line)
        line = re.sub(r'i=11+92', 'i = i + 2', line)
        line = re.sub(r'i= i + 27', 'i = i + 2', line)
        line = re.sub(r'iz=i.+2', 'i = i + 2', line)
        cleaned.append(line)
    return '\n'.join(cleaned)

def clean_question(q):
    """Clean a single question (MC or TF)."""
    if 'content' in q:
        q['content'] = clean_text(q['content'])
        if 'while' in q['content'] or 'for' in q['content'] or 'def F' in q['content']:
            q['content'] = clean_code_blocks(q['content'])
    if 'options' in q:
        for opt in q['options']:
            if 'content' in opt:
                opt['content'] = clean_text(opt['content'])
    return q

def clean_dataset(data):
    """Clean entire dataset."""
    for exam_code, exam_data in data.items():
        for mc in exam_data.get('multiple_choice', []):
            clean_question(mc)
        for tf in exam_data.get('true_false_common', []):
            clean_question(tf)
        for tf in exam_data.get('true_false_special', []):
            clean_question(tf)
    return data

def main(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)

    cleaned_data = clean_dataset(raw_data)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=2)

    print(f"Cleaned data saved to {output_file}")  # dùng tiếng Anh để tránh lỗi Unicode


def check_missing_options(input_file):
    # Các nhãn bắt buộc phải có
    expected_labels = {"A", "B", "C", "D"}
    
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except FileNotFoundError:
        print(f"Lỗi: Không tìm thấy file {input_file}")
        return

    missing_log = []

    for exam_code, exam in raw_data.items():
        # Danh sách các loại câu hỏi cần quét
        question_types = {
            "multiple_choice": "Trắc nghiệm",
            
        }

        for q_type_key, q_type_name in question_types.items():
            questions = exam.get(q_type_key, [])
            for q in questions:
                # Thu thập các nhãn hiện có trong danh sách options
                current_labels = {opt["label"].upper() for opt in q.get("options", [])}
                
                # Tìm các nhãn bị thiếu
                missing = expected_labels - current_labels
                
                if missing:
                    q_id = f"{exam_code}_{q_type_key}_{q.get('number', 'unknown')}"
                    missing_log.append({
                        "id": q_id,
                        "type": q_type_name,
                        "missing": sorted(list(missing)),
                        "current": sorted(list(current_labels))
                    })

    # In kết quả báo cáo
    if not missing_log:
        print("✅ Tuyệt vời! Không có câu hỏi nào bị thiếu option A, B, C, D.")
    else:
        print(f"⚠️ Tìm thấy {len(missing_log)} câu hỏi bị thiếu option:")
        print("-" * 50)
        for item in missing_log:
            print(f"Mã câu: {item['id']}")
            print(f"  - Loại: {item['type']}")
            print(f"  - Nhãn đang thiếu: {', '.join(item['missing'])}")
            print(f"  - Nhãn hiện có: {', '.join(item['current'])}")
            print("-" * 30)

if __name__ == '__main__':
    
    main('de_thi_tin_hoc_TNTHPT_2025_final.json', 'de_thi_tin_hoc_TNTHPT_2025_cleaned1.json')
    DATA_FILE = "de_thi_tin_hoc_TNTHPT_2025_final.json"
    check_missing_options(DATA_FILE)