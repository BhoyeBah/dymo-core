from typing import Any, List, Tuple
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from dymo_saas_core.core.responses import PaginatedMeta

def paginate_query(db: Session, query: Any, page: int = 1, per_page: int = 20) -> Tuple[List[Any], PaginatedMeta]:
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 20
    elif per_page > 100:
        per_page = 100

    offset_val = (page - 1) * per_page

    from sqlalchemy.orm import Query
    # Handle SQLAlchemy 2.0 select() construct
    if not isinstance(query, Query):
        count_stmt = select(func.count()).select_from(query.subquery())
        total = db.scalar(count_stmt) or 0
        stmt = query.offset(offset_val).limit(per_page)
        results = db.scalars(stmt).all()
    else:
        # Handle Legacy or Query-like objects
        total = query.count()
        results = query.offset(offset_val).limit(per_page).all()

    total_pages = (total + per_page - 1) // per_page if total > 0 else 0

    meta = PaginatedMeta(
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages
    )

    return list(results), meta
