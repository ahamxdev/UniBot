import os
from datetime import datetime

def save_response(result, html):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_dir = "saved_html"
    os.makedirs(save_dir, exist_ok=True)
    file_path = os.path.join(save_dir, f"{result['status_code']}_{timestamp}.html")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html)
