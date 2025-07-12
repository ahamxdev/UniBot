from bs4 import BeautifulSoup

def extract_data(html: str):
    soup = BeautifulSoup(html, 'html.parser')
    result = {}

    # استخراج اطلاعات دانشجویی
    student_info_title = soup.find('div', class_='caption', string=lambda t: t and "اطلاعات دانشجویی" in t)
    if not student_info_title:
        return {"status": "not_found", "message": "ℹ️ اطلاعات دانشجویی یافت نشد."}

    table = student_info_title.find_parent("div", class_="portlet").find("table")
    if not table:
        return {"status": "not_found", "message": "ℹ️ جدول اطلاعات دانشجویی یافت نشد."}

    rows = table.find_all("tr")
    for row in rows:
        cols = row.find_all("td")
        for i in range(0, len(cols), 2):
            if i + 1 < len(cols):
                key = cols[i].get_text(strip=True).replace(":", "")
                value = cols[i+1].get_text(strip=True)
                result[key] = value

    # استخراج لیست دروس انتخابی
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

    return {
        "status": "ok",
        "data": result,
        "selected_courses": selected_courses
    }
