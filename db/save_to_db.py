from sqlalchemy.orm import Session
from db.models import StudentInfo, StudentStatus, PaymentStatusEnum
from db.db import SessionLocal


def save_student_info(student_data: dict, session: Session = None) -> StudentInfo:

    """
    Saves student information to the database if it doesn't already exist.

    Parameters:
    - student_data (dict): A dictionary containing student info with English keys.
    - session (Session, optional): An existing SQLAlchemy session (used if called from another function)

    Returns:
    - StudentInfo object (existing or newly created)
    """

    external_session = session is not None
    session = session or SessionLocal()

    try:
        student = session.query(StudentInfo).filter(
            StudentInfo.student_number == student_data.get("student_number")
        ).first()

        if not student:
            # پیدا کردن استتوس مربوط به این شماره دانشجویی
            status_record = session.query(StudentStatus).filter(
                StudentStatus.student_number == student_data.get("student_number")
            ).first()

            if not status_record:
                print("❌ No matching StudentStatus found for student info.")
                return None

            student = StudentInfo(
                student_id=status_record.id,  # رابطه با StudentStatus
                student_number=student_data.get("student_number"),
                full_name=student_data.get("full_name"),
                faculty=student_data.get("faculty"),
                degree=student_data.get("degree"),
                major=student_data.get("major"),
                course_type=student_data.get("course_type"),
                advisor=student_data.get("advisor"),
                entry_term=student_data.get("entry_term"),
                status=student_data.get("status"),
                date=student_data.get("date")
            )
            session.add(student)
            session.commit()

        return student

    except Exception as e:
        session.rollback()
        print(f"❌ Error saving student info: {e}")
        return None

    finally:
        if not external_session:
            session.close()


# def save_selected_courses(student_data: dict, courses_data: list):

#     """
#     Saves selected courses for a student. If the student doesn't exist, saves the student first.

#     Parameters:
#     - student_data (dict): A dictionary containing student info with English keys.
#     - courses_data (list): A list of dictionaries containing course info with English keys.
#     """

#     session: Session = SessionLocal()
#     try:
#         # Ensure the student exists (create if not)
#         student = save_student_info(student_data, session=session)
#         if not student:
#             print("❌ Could not save or find student.")
#             return

#         # Delete previous selected courses
#         session.query(SelectedCourse).filter(
#             SelectedCourse.student_id == student.id
#         ).delete()
#         session.commit()

#         # Add new selected courses
#         for course in courses_data:
#             selected_course = SelectedCourse(
#                 student_id=student.id,
#                 row=course.get("row"),
#                 course_name=course.get("course_name"),
#                 course_code=course.get("course_code"),
#                 group_code=course.get("group_code"),
#                 unit=course.get("unit"),
#                 weekly_schedule=course.get("weekly_schedule"),
#                 exam_date=course.get("exam_date"),
#                 tuition=course.get("tuition"),
#             )
#             session.add(selected_course)

#         session.commit()

#     except Exception as e:
#         session.rollback()
#         print(f"❌ Error saving selected courses: {e}")
#     finally:
#         session.close()


def save_student_status(status_data: dict, session: Session = None) -> bool:
    """
    Inserts or updates student status:
    - On first insert, assigns a new row_index, telegram_user_id, and student_number.
    - On update, updates student_number, and optionally payment_status and discount_code.
    """
    print(f"📥 Received status data: {status_data}")
    external_session = session is not None
    session = session or SessionLocal()

    try:
        telegram_user_id = status_data.get("telegram_user_id")
        student_number = status_data.get("student_number")

        if not telegram_user_id or not student_number:
            print("❌ telegram_user_id or student_number is missing.")
            return False

        # بررسی وجود رکورد بر اساس telegram_user_id
        status_record = session.query(StudentStatus).filter_by(
            telegram_user_id=telegram_user_id
        ).first()

        if not status_record:
            # تولید row_index جدید
            max_row = session.query(StudentStatus.row_index).order_by(StudentStatus.row_index.desc()).first()
            next_row_index = (max_row[0] + 1) if max_row and max_row[0] else 1

            new_status = StudentStatus(
                row_index=next_row_index,
                telegram_user_id=telegram_user_id,
                student_number=student_number,
                payment_status=PaymentStatusEnum.not_paid,  # مقدار پیش‌فرض
                discount_code=None
            )
            session.add(new_status)

        else:
            # آپدیت اطلاعات موجود
            status_record.student_number = student_number

            if "payment_status" in status_data:
                status_record.payment_status = PaymentStatusEnum(status_data["payment_status"])

            if "discount_code" in status_data:
                status_record.discount_code = status_data["discount_code"]

        session.commit()
        return True

    except Exception as e:
        session.rollback()
        print(f"❌ Error saving student status: {e}")
        return False

    finally:
        if not external_session:
            session.close()
