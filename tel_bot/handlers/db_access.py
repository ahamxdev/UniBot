from __future__ import annotations

from typing import Optional

from db.db import SessionLocal
from db.models import StudentAccess, StudentStatus


def get_active_access(user_id: int) -> Optional[StudentAccess]:
    session = SessionLocal()
    try:
        return (
            session.query(StudentAccess)
            .filter_by(telegram_user_id=str(user_id), is_active=True)
            .first()
        )
    finally:
        session.close()


def get_student_status(user_id: int) -> Optional[StudentStatus]:
    session = SessionLocal()
    try:
        return (
            session.query(StudentStatus)
            .filter_by(telegram_user_id=str(user_id))
            .first()
        )
    finally:
        session.close()


def list_active_student_user_ids() -> list[int]:
    session = SessionLocal()
    try:
        rows = (
            session.query(StudentAccess.telegram_user_id)
            .filter_by(is_active=True)
            .all()
        )
        ids: list[int] = []
        for (raw_id,) in rows:
            try:
                ids.append(int(str(raw_id)))
            except Exception:
                continue
        return ids
    finally:
        session.close()


def list_active_user_ids_by_student_number(student_number: str) -> list[int]:
    session = SessionLocal()
    try:
        rows = (
            session.query(StudentAccess.telegram_user_id)
            .filter_by(student_number=student_number, is_active=True)
            .all()
        )
        ids: list[int] = []
        for (raw_id,) in rows:
            try:
                ids.append(int(str(raw_id)))
            except Exception:
                continue
        return ids
    finally:
        session.close()


def upsert_student_access(
    *,
    telegram_user_id: str,
    student_number: str,
    max_courses: int,
    is_active: bool = True,
) -> StudentAccess:
    session = SessionLocal()
    try:
        access = (
            session.query(StudentAccess)
            .filter_by(telegram_user_id=str(telegram_user_id))
            .first()
        )
        if access is None:
            access = StudentAccess(
                telegram_user_id=str(telegram_user_id),
                student_number=student_number,
                max_courses=max_courses,
                is_active=is_active,
            )
            session.add(access)
        else:
            access.student_number = student_number
            access.max_courses = max_courses
            access.is_active = is_active

        status = (
            session.query(StudentStatus)
            .filter_by(telegram_user_id=str(telegram_user_id))
            .first()
        )
        if status is None:
            status = StudentStatus(
                telegram_user_id=str(telegram_user_id),
                student_number=student_number,
            )
            session.add(status)
        else:
            status.student_number = student_number

        session.commit()
        return access
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
