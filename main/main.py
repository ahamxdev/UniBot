import time
from response_checker import analyze_response
from network_module import create_session, send_course_request
from logic_module import is_done
from extract_data import extract_data
from extract_response import save_response




def main():
    print("🔹 Auto Unit Selection Bot Started")

    stno = input("Enter your Student Number (StNo): ").strip()
    term_code = input("Enter Term Code (e.g., 14033): ").strip()
    raw_cookie = input("\nPaste your full Cookie header from browser (one line):\n").strip()

    session = create_session(raw_cookie)

    course_list = []

    while True:
        course = input("\n➕ Enter course code: ").strip()
        group = input("➕ Enter group code: ").strip()

        print("➕ Select operation for this course:")
        print("1. Final Register")
        print("2. Delete Course")
        op = input("Enter 1 or 2: ").strip()

        if op == "1":
            ins_view = "4"
            operation = "register"
        elif op == "2":
            ins_view = "5"
            operation = "delete"
        else:
            print("❌ Invalid operation choice. Skipping this course.")
            continue

        course_list.append({
            "course": course,
            "group": group,
            "ins_view": ins_view,
            "operation": operation,
            "done": False
        })

        another = input("➕ Do you want to add another course? (y/n): ").strip().lower()
        if another != 'y':
            break

    print("\n🔄 Starting submission loop...\n")
    round_num = 1

    while True:
        print(f"\n📘 Round {round_num}")
        all_done = True

        for item in course_list:
            if item["done"]:
                continue

            all_done = False

            try:
                print(f"\n⏳ Sending request for course {item['course']} - group {item['group']}...")
                response = send_course_request(
                    session,
                    item["ins_view"],
                    item["course"],
                    item["group"],
                    stno,
                    term_code
                )

                html = response.content.decode('utf-8', errors='ignore')

                result = analyze_response(html, item["operation"], course_code=item["course"], group_code=item["group"])
                print(f"📄 Result: {result['message']}")

                if is_done(result["status_code"], item["operation"]):
                    item["done"] = True

                student_info = extract_data(html)
                if student_info["status"] == "ok":
                    print("\nℹ️ اطلاعات دانشجویی:")
                    for k, v in student_info["data"].items():
                        print(f"📌 {k}: {v}")

                    print("\n📚 لیست دروس انتخاب‌شده:")
                    if student_info["selected_courses"]:
                        for i, course in enumerate(student_info["selected_courses"], start=1):
                            print(f"{i}. 🧾 {course['کد درس']} - {course['نام درس']} | گروه: {course['کد گروه']} | واحد: {course['واحد']} | امتحان: {course['تاریخ امتحان']} | شهریه: {course['شهریه']}")
                    else:
                        print("⚠️ هیچ درسی انتخاب نشده است.")

                    save_response(result["status_code"], html)

                else:
                    print(student_info["message"])

            except Exception as e:
                print(f"❌ Error while sending request for course {item['course']}: {str(e)}")

        if all_done:
            print("\n✅ All tasks completed. Exiting loop.")
            break

        round_num += 1
        print("\n⏱ Waiting 5 seconds before next round...\n")
        time.sleep(5)

if __name__ == "__main__":
    main()
