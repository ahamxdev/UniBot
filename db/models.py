from sqlalchemy import Column, Integer, String, ForeignKey, Enum
from sqlalchemy.orm import relationship
from db.db import Base
import enum


class PaymentStatusEnum(enum.Enum):
    not_paid = "not_paid"
    paid = "paid"
    paid_with_discount = "paid_with_discount"


class StudentInfo(Base):
    """
    ORM model for the 'students_info' table.
    Stores personal and academic information about a student.
    """
    __tablename__ = "students_info"

    student_id = Column(Integer, ForeignKey("students_status.id"), primary_key=True, index=True)
    student_number = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String)
    faculty = Column(String)
    degree = Column(String)
    major = Column(String)
    course_type = Column(String)
    advisor = Column(String)
    entry_term = Column(String)
    status = Column(String)
    date = Column(String)

    # One to One relationship with StudentStatus
    status_info = relationship(
        "StudentStatus",
        back_populates="student",
        uselist=False,
    )


# class SelectedCourse(Base):

#     """
#     ORM model for the 'selected_courses' table.
#     Stores information about each course selected by a student.
#     """

#     __tablename__ = "selected_courses"

#     id = Column(Integer, primary_key=True, index=True)
#     student_id = Column(Integer, ForeignKey("students_info.id"), nullable=False)  # FK to StudentInfo
#     row = Column(Integer)             # Course row   
#     course_code = Column(String)      # Course code (e.g., 3030513)
#     course_name = Column(String)      # Course title
#     group_code = Column(String)            # Course group code
#     unit = Column(String)             # Number of credits/units
#     weekly_schedule = Column(String)  # Weekly schedular
#     exam_date = Column(String)        # Exam date (e.g., 1404/05/29)
#     tuition = Column(String)          # Tuition amount

#     # Relationship back to student
#     student = relationship("StudentInfo", back_populates="courses")


class StudentStatus(Base):
    """
    ORM model for the 'students_status' table.
    Stores payment and metadata about student actions.
    """
    __tablename__ = "students_status"

    row_index = Column(Integer, nullable=True)
    id = Column(Integer, primary_key=True, index=True)
    telegram_user_id = Column(String, unique=True, index=True, nullable=True)
    student_number = Column(String, nullable=False)
    payment_status = Column(Enum(PaymentStatusEnum), nullable=False, default=PaymentStatusEnum.not_paid)
    discount_code = Column(String, nullable=True)

    # One to One relationship with StudentInfo
    student = relationship(
        "StudentInfo",
        back_populates="status_info",
        uselist=False
    )
