"""Extended version of :mod:`mongoengine.document`."""

from __future__ import annotations

from typing import NoReturn

import mongoengine
from flask import abort
from mongoengine.errors import DoesNotExist
from mongoengine.queryset import QuerySet

from flask_mongoengine2.pagination import ListFieldPagination, Pagination


def _abort_404(message: str | None = None) -> NoReturn:
    abort(404, message) if message else abort(404)


class BaseQuerySet(QuerySet):
    """Extends :class:`~mongoengine.queryset.QuerySet` class with handy methods."""

    def _abort_404(self, _message_404: str | None = None) -> NoReturn:
        """Returns 404 error with message, if message provided.

        :param _message_404: Message for 404 comment
        """
        _abort_404(_message_404)

    def get_or_404(self, *args, _message_404: str | None = None, **kwargs):
        """Get a document and raise a 404 Not Found error if it doesn't exist.

        :param _message_404: Message for 404 comment, not forwarded to
            :func:`~mongoengine.queryset.QuerySet.get`
        :param args: args list, silently forwarded to
            :func:`~mongoengine.queryset.QuerySet.get`
        :param kwargs: keywords arguments, silently forwarded to
            :func:`~mongoengine.queryset.QuerySet.get`
        """
        try:
            return self.get(*args, **kwargs)
        except DoesNotExist:
            self._abort_404(_message_404)

    def first_or_404(self, _message_404: str | None = None):
        """
        Same as :func:`~BaseQuerySet.get_or_404`, but uses
        :func:`~mongoengine.queryset.QuerySet.first`, not
        :func:`~mongoengine.queryset.QuerySet.get`.

        :param _message_404: Message for 404 comment, not forwarded to
            :func:`~mongoengine.queryset.QuerySet.get`
        """
        result = self.first()
        if result is None:
            self._abort_404(_message_404)
        return result

    def paginate(self, page: int, per_page: int) -> Pagination:
        """
        Paginate the QuerySet with a certain number of docs per page
        and return docs for a given page.
        """
        return Pagination(self, page, per_page)

    def paginate_field(
        self, field_name: str, doc_id, page: int, per_page: int, total=None
    ) -> ListFieldPagination:
        """
        Paginate items within a list field from one document in the
        QuerySet.

        If the document defines a ``<field_name>_count`` field, it is used as the
        total. Otherwise, the total is computed server side, without loading the
        whole list.
        """
        count_field = f"{field_name}_count"
        if not total and count_field in self._document._fields:
            item = self.only(count_field).filter(pk=doc_id).first()
            if item is None:
                _abort_404()
            total = getattr(item, count_field)
        return ListFieldPagination(
            self, doc_id, field_name, page, per_page, total=total
        )


class Document(mongoengine.Document):
    """Abstract Document with QuerySet"""

    meta = {"abstract": True, "queryset_class": BaseQuerySet}

    def paginate_field(
        self, field_name: str, page: int, per_page: int, total=None
    ) -> ListFieldPagination:
        """Paginate items within a list field."""
        total = (
            total
            or getattr(self, f"{field_name}_count", None)
            or len(getattr(self, field_name))
        )
        return ListFieldPagination(
            self.__class__.objects, self.pk, field_name, page, per_page, total=total
        )


class DynamicDocument(mongoengine.DynamicDocument):
    """Abstract DynamicDocument with QuerySet."""

    meta = {"abstract": True, "queryset_class": BaseQuerySet}


class EmbeddedDocument(mongoengine.EmbeddedDocument):
    """Abstract EmbeddedDocument document."""

    meta = {"abstract": True}


class DynamicEmbeddedDocument(mongoengine.DynamicEmbeddedDocument):
    """Abstract DynamicEmbeddedDocument document."""

    meta = {"abstract": True}
