"""Tests for extended documents and queryset."""

import pytest
from bson import ObjectId
from werkzeug.exceptions import NotFound

from flask_mongoengine2.documents import BaseQuerySet


def test_queryset_class__is_base_queryset(todo):
    assert isinstance(todo.objects, BaseQuerySet)


def test_get_or_404__should_return_document(todo):
    doc = todo(title="t").save()
    assert todo.objects.get_or_404(id=doc.id) == doc


@pytest.mark.parametrize("message", [None, "Custom message"])
def test_get_or_404__should_abort__with_optional_message(todo, message):
    with pytest.raises(NotFound) as error:
        todo.objects.get_or_404(id=ObjectId(), _message_404=message)
    if message:
        assert error.value.description == message


def test_first_or_404__should_return_document(todo):
    doc = todo(title="t").save()
    assert todo.objects.first_or_404() == doc


@pytest.mark.parametrize("message", [None, "Custom message"])
def test_first_or_404__should_abort__with_optional_message(todo, message):
    with pytest.raises(NotFound) as error:
        todo.objects.first_or_404(_message_404=message)
    if message:
        assert error.value.description == message


def test_dynamic_document__has_base_queryset(db):
    class Dyn(db.DynamicDocument):
        pass

    doc = Dyn(anything="value").save()
    assert isinstance(Dyn.objects, BaseQuerySet)
    assert Dyn.objects.get_or_404(id=doc.id).anything == "value"


def test_embedded_documents__are_abstract_and_usable(db):
    class Inner(db.EmbeddedDocument):
        name = db.StringField()

    class DynInner(db.DynamicEmbeddedDocument):
        pass

    class Outer(db.Document):
        inner = db.EmbeddedDocumentField(Inner)
        dyn = db.EmbeddedDocumentField(DynInner)

    Outer(inner=Inner(name="x"), dyn=DynInner(extra=1)).save()
    stored = Outer.objects.first()
    assert stored.inner.name == "x"
    assert stored.dyn.extra == 1


def test_paginate_field__uses_count_field__when_defined(db):
    class Post(db.Document):
        comments = db.ListField(db.StringField())
        comments_count = db.IntField()

    post = Post(comments=[str(i) for i in range(30)], comments_count=30).save()
    paginator = Post.objects.paginate_field("comments", post.id, 2, 10)
    assert paginator.total == 30
    assert paginator.items == [str(i) for i in range(10, 20)]
    assert post.paginate_field("comments", 3, 10).items == [
        str(i) for i in range(20, 30)
    ]

    with pytest.raises(NotFound):
        Post.objects.paginate_field("comments", ObjectId(), 1, 10)
