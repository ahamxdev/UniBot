# main.py
"""
Automated Unit Selection Bot - Main Execution Loop

Responsibilities:
----------------
1. Create an authenticated HTTP session using the provided cookie.
2. Keep the session alive via periodic pings (background thread).
3. Submit course registration/deletion requests in rounds until all are done.
4. Analyze responses, print logs for visibility, and push user-facing messages
   into the shared message_queue (to be delivered by the Telegram bot).
5. Extract and persist student info (once per run) if available.

Design:
-------
- This function (`main`) is intended to be run in a background thread, 
  triggered from Telegram bot handlers.
- Direct messaging to users does NOT happen here; instead, human-readable 
  messages are put into `tel_bot.message_queue.message_queue`.
"""

import time
import threading
import traceback
from typing import Optional
from main.response_checker import analyze_response
from main.network_module import create_session, send_course_request, send_keep_alive_ping
from main.logic_module import is_done
from main.extract_data import extract_data
# from main.save_response import save_response
from db.save_to_db import save_student_info
from tel_bot.message_queue import message_queue


def keep_session_alive_loop(session):
    """
    Background loop to keep the HTTP session alive by sending periodic pings.
    Runs indefinitely in a daemon thread.
    """
    print("\n🛟 Keep-alive thread started.\n")
    while not cancel_event.is_set():

        for _ in range(5 * 60):
            if cancel_event.is_set():
                break
            time.sleep(1)
        if cancel_event.is_set():
            break
        try:
            send_keep_alive_ping(session)
        except Exception as e:
            print(f"[KeepAlive] Error: {e}")
    print("🛟 Keep-alive thread exiting.")


def main(stno, term_code, raw_cookie, course_list, chat_id, cancel_event: threading.Event):
    """
    Main loop for processing unit selection requests.

    Args:
        stno (str): Student number
        term_code (int): Current academic term code (e.g., 14041)
        raw_cookie (str): Raw cookie string for authentication
        course_list (list[dict]): List of course operations:
            {
                "course": str,
                "group": str,
                "ins_view": "4" | "5",   # 4=register, 5=delete
                "operation": "register" | "delete",
                "done": bool
            }
        chat_id (int): Telegram chat ID to send messages to (via queue)

    Behavior:
        - Submits requests in rounds.
        - Logs results with print().
        - Pushes messages into message_queue for Telegram delivery.
        - Stops when all operations are completed.
    """
    print("🔹 Auto Unit Selection Bot Started")

    if cancel_event.is_set():
        print("🔹 Cancel requested before start; exiting.")
        return

    # Create authenticated session
    session = create_session(raw_cookie)

    # Start keep-alive thread
    threading.Thread(
        target=keep_session_alive_loop, args=(session,), daemon=True
    ).start()

    print("\n🔄 Starting submission loop...\n")
    round_num = 1
    student_info_printed = False

    while not cancel_event.is_set():
        print(f"\n📘 Round {round_num}")
        all_done = True

        for item in course_list:
            if cancel_event.is_set():
                break

            if item["done"]:
                continue

            all_done = False
            try:
                print(
                    f"⏳ Sending request for course {item['course']} - group {item['group']}..."
                )
                response = send_course_request(
                    session,
                    item["ins_view"],
                    item["course"],
                    item["group"],
                    stno,
                    term_code,
                )

                html = response.content.decode("utf-8", errors="ignore")

                # Analyze response
                result = analyze_response(
                    html,
                    item["operation"],
                    course_code=item["course"],
                    group_code=item["group"],
                )

                print(f"📄 Result: {result['message']}")
                # print("[MQ] in main before put, mq id:", id(message_queue))  # DEBUG
                # print("[MQ] put:", (chat_id, result["message"][:40]))  # DEBUG

                # Push message to queue for Telegram bot
                if result["status_code"] != "capacity_full":
                    message_queue.put_nowait((chat_id, result["message"]))

                # Extract and save student info
                student_info = extract_data(html)
                if student_info["status"] == "ok":
                    if not student_info_printed:
                        save_student_info(student_info["db_student_info"])
                        # Debug prints for student info (kept as requested)
                        # print("🧪 db_student_info:", student_info["db_student_info"])
                        # print("\nℹ️ اطلاعات دانشجویی:")
                        # for k, v in student_info["student_info"].items():
                        #     print(f"📌 {k}: {v}")
                        student_info_printed = True

                    if not result["status_code"] == "capacity_full":
                        print("\n📚 لیست دروس انتخاب شده:")
                        selected_courses = student_info.get("selected_courses", [])
                        if selected_courses:
                            for i, course in enumerate(selected_courses, start=1):
                                print(
                                    f"{i}. {course['نام درس']} | {course['کد درس']} "
                                    f"| Group: {course['کد گروه']} | Units: {course['واحد']} "
                                    f"| Exam: {course['تاریخ امتحان']} | Fee: {course['شهریه']}"
                                )
                        else:
                            print("⚠️ هیچ درسی انتخاب نشده است.")

                else:
                    print(student_info["message"])

                # Mark operation done if condition met
                if is_done(result["status_code"], item["operation"]):
                    item["done"] = True

            except Exception as e:
                print(traceback.format_exc())
                error_msg = (
                    f"❌ خطا هنگام ارسال درخواست برای درس {item['course']} - گروه {item['group']}:\n"
                    f"{str(e)}"
                )
                print(error_msg)
                try:
                    message_queue.put_nowait((chat_id, error_msg))
                except Exception:
                    pass

        if cancel_event.is_set():
            print("🛑 Cancel requested; exiting submission loop.")
            break

        if all_done:
            print("\n✅ All tasks completed. Exiting loop.")
            break

        round_num += 1
        print("⏱ Waiting 5 seconds before next round...")
        for _ in range(5):
            if cancel_event.is_set():
                break
            time.sleep(1)

    if cancel_event.is_set():
        try:
            message_queue.put_nowait((chat_id, "⛔️ عملیات به درخواست شما متوقف شد."))
        except Exception:
            pass
