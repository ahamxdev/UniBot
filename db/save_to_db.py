from sqlalchemy.orm import Session
from db.models import StudentInfo
from db.db import SessionLocal, init_db

# Initialize database (e.g. create tables if they don't exist)
init_db()


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
            student = StudentInfo(
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
