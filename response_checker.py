import re
from bs4 import BeautifulSoup




def extract_alerts(html):
    return re.findall(r"alert\('([^']+)'\)", html)


def analyze_response(html, operation, course_code=None, group_code=None):
    soup = BeautifulSoup(html, 'html.parser')
    alerts = extract_alerts(html)

    # -------------------- DELETE OPERATION --------------------
    if operation == "delete":
        for alert in alerts:
            if "پاک شد" in alert:
                return {
                    "status_code": "deleted",
                    "message": "✅ درس انتخابی حذف شد"
                }
            elif "درس مورد نظر پیدا نشد" in alert:
                return {
                    "status_code": "not_found",
                    "message": "⚠️ درس مورد نظر برای حذف پیدا نشد."
                }
        return {
            "status_code": "unknown_delete",
            "message": "⚠️ No recognizable alert found for delete operation."
        }

    # -------------------- REGISTER OPERATION --------------------
    if operation == "register":
        # Step 1: Check "وضعیت درخواستهای شما" (final table)
        target_caption = soup.find('div', class_='caption', string=lambda t: t and "وضعیت درخواستهای شما" in t)
        if target_caption:
            portlet_body = target_caption.find_parent("div", class_="portlet").find("div", class_="portlet-body")
            table = portlet_body.find("table") if portlet_body else None
            if table:
                rows = table.find_all("tr")
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) >= 9:
                        status = cols[8].get_text(strip=True)
                        if "ثبت شد" in status:
                            return {
                                "status_code": "registered",
                                "message": "✅ Status in final table: Registered."
                            }

        # Step 2: Check "لیست انتخاب واحد" table
        course_code = str(course_code).strip()
        group_code = str(group_code).strip()

        all_tables = soup.find_all("table")
        for table in all_tables:
            rows = table.find_all("tr")
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 4:
                    lesson_code = cols[1].get_text(strip=True)
                    group = cols[3].get_text(strip=True)

                    if lesson_code == course_code and group == group_code:
                        return {
                            "status_code": "already_registered",
                            "message": f"ℹ️ This course has already been selected: Lesson Code: {lesson_code} | Group: {group}"
                        }

        # Step 3: Not found anywhere
        return {
            "status_code": "not_registered",
            "message": "⚠️ Registration not confirmed in the final table."
        }

    return {
        "status_code": "unknown",
        "message": "⚠️ Unknown operation or response."
    }
