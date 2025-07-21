import time
import threading
import traceback
from main.response_checker import analyze_response
from main.network_module import create_session, send_course_request, send_keep_alive_ping
from main.logic_module import is_done
from main.extract_data import extract_data
from main.save_response import save_response
from db.save_to_db import save_student_info


def keep_session_alive_loop(session):
    print("\n🛟 Keep-alive thread started.\n")
    while True:
        time.sleep(5 * 60)
        send_keep_alive_ping(session)


def get_course_list():
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

    return course_list


def main():
    print("🔹 Auto Unit Selection Bot Started")

    # 🧾 Get inputs
    stno = input("Enter your Student Number (StNo): ").strip()
    term_code = input("Enter Term Code (e.g., 14033): ").strip()
    # stno = 140215365450
    # term_code = 14033
    raw_cookie = input("\nPaste your full Cookie header from browser (one line):\n").strip()
    term_code = "14041"
    # 🧾 Create session with headers and cookies
    session = create_session(raw_cookie)

    # 🧾 Get courses
    course_list = get_course_list()

    # 🚀 Start keep-alive thread after inputs are done
    threading.Thread(target=keep_session_alive_loop, args=(session,), daemon=True).start()

    print("\n🔄 Starting submission loop...\n")
    round_num = 1

    student_info_printed = False

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
                print(f"\n📄 Result: {result['message']}")

                student_info = extract_data(html)
                if student_info["status"] == "ok":
                    if not student_info_printed:
                        save_student_info(student_info["db_student_info"])
                        # print("🧪 db_student_info:", student_info["db_student_info"])
                        # print("\nℹ️ اطلاعات دانشجویی:")
                        # for k, v in student_info["student_info"].items():
                        #     print(f"📌 {k}: {v}")
                        student_info_printed = True

                    # save_selected_courses(student_info["db_student_info"], student_info["db_selected_courses"])
                    # print("🧾 db_selected_courses:", student_info["db_selected_courses"])

                    if not result["status_code"] == "capacity_full":
                        print("\n📚 لیست دروس انتخاب شده:")
                        selected_courses = student_info.get("selected_courses", [])
                        if selected_courses:
                            for i, course in enumerate(selected_courses, start=1):
                                print(f"{i}. {course['نام درس']} | {course['کد درس']} | گروه: {course['کد گروه']} | واحد: {course['واحد']} | امتحان: {course['تاریخ امتحان']} | شهریه: {course['شهریه']}")
                        else:
                            print("⚠️ هیچ درسی انتخاب نشده است.")

                else:
                    print(student_info["message"])

                if is_done(result["status_code"], item["operation"]):
                    item["done"] = True

                # Save response only if result is a dictionary with status_code
                # if isinstance(result, dict) and "status_code" in result:
                #     save_response(result["status_code"], html)

            except Exception as e:
                print(traceback.format_exc())
                print(f"❌ Error while sending request for course {item['course']}: {str(e)}")

        if all_done:
            print("\n✅ All tasks completed. Exiting loop.")
            break

        round_num += 1
        print("\n⏱ Waiting 5 seconds before next round...")
        time.sleep(5)


if __name__ == "__main__":
    main()
