import re
from bs4 import BeautifulSoup


def extract_data(html: str):

    """
    Parses the given HTML and extracts student information and selected courses.
    
    Returns a dictionary with:
    - 'student_info': Persian-keyed student info (for display)
    - 'db_student_info': English-keyed student info (for database)
    - 'selected_courses': Persian-keyed course list (for display)
    - 'db_selected_courses': English-keyed course list (for database)
    """

    soup = BeautifulSoup(html, 'html.parser')
    result = {}

    # Find and extract student info table
    student_info_title = soup.find('div', class_='caption', string=lambda t: t and "اطلاعات دانشجویی" in t)
    if not student_info_title:
        return {"status": "not_found", "message": "ℹ️ Student info not found."}

    table = student_info_title.find_parent("div", class_="portlet").find("table")
    if not table:
        return {"status": "not_found", "message": "ℹ️ Student info table not found."}

    # Extract key-value pairs from student info table (Persian keys)
    rows = table.find_all("tr")
    for row in rows:
        cols = row.find_all("td")
        for i in range(0, len(cols), 2):
            if i + 1 < len(cols):
                key = cols[i].get_text(strip=True).replace(":", "")
                value = cols[i+1].get_text(strip=True)
                result[key] = value

    # Extract selected courses (Persian keys for display)
    selected_courses = []
    course_table_caption = soup.find('div', class_='caption', string=lambda t: t and "واحدهای انتخاب شده نیمسال" in t)
    if course_table_caption:
        course_table = course_table_caption.find_parent("div", class_="portlet").find("table")
        if course_table:
            rows = course_table.find("tbody").find_all("tr")
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 9:
                    course = {
                        "ردیف": cols[0].get_text(strip=True),
                        "کد درس": cols[1].get_text(strip=True),
                        "نام درس": cols[2].get_text(strip=True),
                        "کد گروه": cols[3].get_text(strip=True),
                        "واحد": cols[4].get_text(strip=True),
                        "برنامه هفتگی": cols[5].get_text(strip=True),
                        "تاریخ امتحان": cols[6].get_text(strip=True),
                        "وضعیت": cols[7].get_text(strip=True),
                        "شهریه": cols[8].get_text(strip=True),
                    }
                    selected_courses.append(course)

    # Mapping Persian keys to English keys for student info
    key_map_student = {
        "شماره دانشجویی": "student_number",
        "نام خانوادگی و نام": "full_name",
        "دانشکده": "faculty",
        "مقطع تحصیلی": "degree",
        "رشته تحصیلی": "major",
        "نوع دوره": "course_type",
        "استاد راهنما": "advisor",
        "نیمسال ورود": "entry_term",
        "وضعیت کلی": "status",
        "تاریخ": "date"
    }

    # Mapping Persian keys to English keys for courses
    key_map_courses = {
        "ردیف": "row",
        "نام درس": "course_name",
        "کد درس": "course_code",
        "کد گروه": "group_code",
        "واحد": "unit",
        "برنامه هفتگی": "weekly_schedule",
        "تاریخ امتحان": "exam_date",
        "وضعیت": "status",
        "شهریه": "tuition"
    }

    def normalize_key(key):
        """Remove all whitespace from keys (useful for fuzzy matching)"""
        return re.sub(r"\s+", "", key)

    # Normalize keys for accurate lookup
    normalized_result = {normalize_key(k): v for k, v in result.items()}
    db_result = {}

    # Convert Persian keys to English using normalized keys
    for farsi_key, english_key in key_map_student.items():
        norm_key = normalize_key(farsi_key)
        db_result[english_key] = normalized_result.get(norm_key, None)

    # Convert selected courses to English-keyed dictionaries
    db_selected_courses = []
    for course in selected_courses:
        db_course = {}
        for farsi_key, english_key in key_map_courses.items():
            db_course[english_key] = course.get(farsi_key, None)
        db_selected_courses.append(db_course)

    return {
        "status": "ok",
        "student_info": result,                  # Persian keys for UI display
        "db_student_info": db_result,            # English keys for DB insertion
        "selected_courses": selected_courses,    # Persian keys for UI display
        "db_selected_courses": db_selected_courses  # English keys for DB insertion
    }
