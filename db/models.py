from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from db.db import Base


class StudentInfo(Base):

    """
    ORM model for the 'students_info' table.
    Stores personal and academic information about a student.
    """

    __tablename__ = "students_info"

    id = Column(Integer, primary_key=True, index=True)
    student_number = Column(String, unique=True, index=True, nullable=False)  # Unique student ID
    full_name = Column(String)         # Full name (last name + first name)
    faculty = Column(String)           # Faculty or department
    degree = Column(String)            # Degree level (e.g., Bachelor's)
    major = Column(String)             # Major or field of study
    course_type = Column(String)       # Type of program (e.g., Guest)
    advisor = Column(String)           # Advisor name
    entry_term = Column(String)        # Entry term (e.g., 14021)
    status = Column(String)            # Status (e.g., Active)
    date = Column(String)              # Date of data retrieval or registration

    # Relationship to selected courses
    # courses = relationship(
    #     "SelectedCourse",
    #     back_populates="student",
    #     cascade="all, delete-orphan"
    # )



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
