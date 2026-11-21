"""Module responsible for custom pagination."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

from flask import abort
from mongoengine.queryset import QuerySet

__all__ = ("ListFieldPagination", "Pagination")


def _validate_page_args(page: int, per_page: int) -> None:
    if page < 1:
        abort(404)
    if per_page < 1:
        raise ValueError("per_page should be a positive integer")


class Pagination:
    """Paginate a :class:`~mongoengine.queryset.QuerySet` or any sliceable sequence."""

    def __init__(self, iterable: QuerySet | Sequence, page: int, per_page: int):
        _validate_page_args(page, per_page)

        self.iterable = iterable
        self.page = page
        self.per_page = per_page

        start_index = (page - 1) * per_page

        if isinstance(iterable, QuerySet):
            self.total = iterable.count()
            # ``skip``/``limit`` return clones, the original queryset is untouched.
            self.items = (
                iterable.skip(start_index).limit(per_page).select_related()
                if start_index < self.total
                else []
            )
        else:
            self.total = len(iterable)
            self.items = iterable[start_index : start_index + per_page]

        if not self.items and page != 1:
            abort(404)

    @property
    def pages(self) -> int:
        """The total number of pages"""
        return -(-self.total // self.per_page)

    def prev(self, error_out: bool = False) -> Pagination:
        """Returns a :class:`Pagination` object for the previous page."""
        return self.__class__(self.iterable, self.page - 1, self.per_page)

    @property
    def prev_num(self) -> int:
        """Number of the previous page."""
        return self.page - 1

    @property
    def has_prev(self) -> bool:
        """True if a previous page exists"""
        return self.page > 1

    def next(self, error_out: bool = False) -> Pagination:
        """Returns a :class:`Pagination` object for the next page."""
        return self.__class__(self.iterable, self.page + 1, self.per_page)

    @property
    def has_next(self) -> bool:
        """True if a next page exists."""
        return self.page < self.pages

    @property
    def next_num(self) -> int:
        """Number of the next page"""
        return self.page + 1

    def iter_pages(
        self,
        left_edge: int = 2,
        left_current: int = 2,
        right_current: int = 5,
        right_edge: int = 2,
    ) -> Iterator[int | None]:
        """Iterates over the page numbers in the pagination.  The four
        parameters control the thresholds how many numbers should be produced
        from the sides.  Skipped page numbers are represented as `None`.
        This is how you could render such a pagination in the templates:

        .. sourcecode:: html+jinja

            {% macro render_pagination(pagination, endpoint) %}
              <div class=pagination>
              {%- for page in pagination.iter_pages() %}
                {% if page %}
                  {% if page != pagination.page %}
                    <a href="{{ url_for(endpoint, page=page) }}">{{ page }}</a>
                  {% else %}
                    <strong>{{ page }}</strong>
                  {% endif %}
                {% else %}
                  <span class=ellipsis>…</span>
                {% endif %}
              {%- endfor %}
              </div>
            {% endmacro %}
        """
        pages = self.pages
        last = 0
        for num in range(1, pages + 1):
            if (
                num <= left_edge
                or num > pages - right_edge
                or self.page - left_current <= num <= self.page + right_current
            ):
                if last + 1 != num:
                    yield None
                yield num
                last = num
        if last != pages:
            yield None


class ListFieldPagination(Pagination):
    def __init__(
        self,
        queryset: QuerySet,
        doc_id: Any,
        field_name: str,
        page: int,
        per_page: int,
        total: int | None = None,
    ):
        """Allows an array within a document to be paginated.

        Queryset must contain the document which has the array we're
        paginating, and doc_id should be it's _id.
        Field name is the name of the array we're paginating.
        Page and per_page work just like in Pagination.
        Total is an argument because it can be computed more efficiently
        elsewhere. If omitted, it is computed server side with ``$size``, so the
        array itself is never transferred just to be counted.
        """
        _validate_page_args(page, per_page)

        self.page = page
        self.per_page = per_page

        self.queryset = queryset
        self.doc_id = doc_id
        self.field_name = field_name

        start_index = (page - 1) * per_page

        qs = queryset(pk=doc_id)
        document = qs.fields(
            **{field_name: {"$slice": [start_index, per_page]}}
        ).first()
        if document is None:
            abort(404)

        self.items = getattr(document, field_name)
        self.total = total if total is not None else self._count_items(qs)

        if not self.items and page != 1:
            abort(404)

    def _count_items(self, qs: QuerySet) -> int:
        """Count array items in database, without fetching them."""
        db_field = qs._document._fields[self.field_name].db_field
        pipeline = [
            {"$project": {"_id": 0, "n": {"$size": {"$ifNull": [f"${db_field}", []]}}}}
        ]
        result = next(iter(qs.aggregate(pipeline)), None)
        return result["n"] if result else 0

    def prev(self, error_out: bool = False) -> ListFieldPagination:
        """Returns a :class:`Pagination` object for the previous page."""
        return self.__class__(
            self.queryset,
            self.doc_id,
            self.field_name,
            self.page - 1,
            self.per_page,
            self.total,
        )

    def next(self, error_out: bool = False) -> ListFieldPagination:
        """Returns a :class:`Pagination` object for the next page."""
        return self.__class__(
            self.queryset,
            self.doc_id,
            self.field_name,
            self.page + 1,
            self.per_page,
            self.total,
        )
