import pytest
from bson import ObjectId
from pymongo import monitoring
from werkzeug.exceptions import NotFound

from flask_mongoengine2 import ListFieldPagination, Pagination


class CommandCounter(monitoring.CommandListener):
    def __init__(self):
        self.commands = []

    def started(self, event):
        self.commands.append(event.command)

    def succeeded(self, event):
        pass

    def failed(self, event):
        pass


@pytest.fixture()
def command_counter():
    """Must be requested before ``db``: listeners only apply to new clients."""
    counter = CommandCounter()
    monitoring.register(counter)
    yield counter
    monitoring._LISTENERS.command_listeners.remove(counter)


def test_queryset_paginator(app, todo):
    Todo = todo
    for i in range(42):
        Todo(title=f"post: {i}").save()

    with pytest.raises(NotFound):
        Pagination(iterable=Todo.objects, page=0, per_page=10)

    with pytest.raises(NotFound):
        Pagination(iterable=Todo.objects, page=6, per_page=10)

    paginator = Pagination(Todo.objects, 1, 10)
    _test_paginator(paginator)

    for page in range(1, 10):
        for index, todo in enumerate(
            Todo.objects.paginate(page=page, per_page=5).items
        ):
            assert todo.title == f"post: {(page - 1) * 5 + index}"


def test_queryset_paginator__should_not_modify_original_queryset(app, todo):
    for i in range(30):
        todo(title=f"post: {i}").save()

    queryset = todo.objects.skip(5).limit(20)
    paginator = Pagination(queryset, 1, 10).next()

    assert paginator.page == 2
    assert queryset._skip == 5
    assert queryset._limit == 20


def test_queryset_paginator__empty_queryset__first_page_is_valid(app, todo):
    paginator = Pagination(todo.objects, 1, 10)
    assert paginator.items == []
    assert paginator.total == 0
    assert paginator.pages == 0
    assert not paginator.has_next
    assert list(paginator.iter_pages()) == []


def test_paginate_plain_list():
    with pytest.raises(NotFound):
        Pagination(iterable=range(1, 42), page=0, per_page=10)

    with pytest.raises(NotFound):
        Pagination(iterable=range(1, 42), page=6, per_page=10)

    paginator = Pagination(range(1, 42), 1, 10)
    _test_paginator(paginator)


@pytest.mark.parametrize("per_page", [0, -1])
def test_pagination__should_raise__on_invalid_per_page(per_page):
    with pytest.raises(ValueError, match="per_page"):
        Pagination(list(range(10)), 1, per_page)


@pytest.mark.parametrize(
    ("total", "per_page", "pages"),
    [(0, 10, 0), (1, 10, 1), (10, 10, 1), (11, 10, 2), (41, 10, 5)],
)
def test_pagination__pages_count(total, per_page, pages):
    assert Pagination(list(range(total)), 1, per_page).pages == pages


def test_iter_pages__with_many_pages():
    paginator = Pagination(list(range(200)), 10, 10)
    assert list(paginator.iter_pages()) == [
        1,
        2,
        None,
        8,
        9,
        10,
        11,
        12,
        13,
        14,
        15,
        None,
        19,
        20,
    ]


def test_list_field_pagination(app, todo):
    Todo = todo

    comments = [f"comment: {i}" for i in range(42)]
    todo = Todo(
        title="todo has comments",
        comments=comments,
        comment_count=len(comments),
    ).save()

    # Check without providing a total
    paginator = ListFieldPagination(Todo.objects, todo.id, "comments", 1, 10)
    _test_paginator(paginator)

    # Check with providing a total (saves a query)
    paginator = ListFieldPagination(
        Todo.objects, todo.id, "comments", 1, 10, todo.comment_count
    )
    _test_paginator(paginator)

    paginator = todo.paginate_field("comments", 1, 10)
    _test_paginator(paginator)

    paginator = Todo.objects.paginate_field("comments", todo.id, 1, 10)
    _test_paginator(paginator)

    assert paginator.items == comments[:10]


def test_list_field_pagination__total_computed_server_side(command_counter, todo):
    """Whole list should never be fetched only to be counted."""
    comments = [f"comment: {i}" for i in range(42)]
    doc = todo(title="t", comments=comments).save()

    counter = command_counter
    counter.commands.clear()
    paginator = ListFieldPagination(todo.objects, doc.id, "comments", 2, 10)

    assert paginator.total == 42
    assert paginator.items == comments[10:20]
    finds = [c for c in counter.commands if "find" in c]
    assert len(finds) == 1
    assert finds[0]["projection"] == {"comments": {"$slice": [10, 10]}}
    assert any("aggregate" in c for c in counter.commands)


def test_list_field_pagination__empty_list(app, todo):
    doc = todo(title="t").save()
    paginator = ListFieldPagination(todo.objects, doc.id, "comments", 1, 10)
    assert paginator.items == []
    assert paginator.total == 0
    assert paginator.pages == 0


def test_list_field_pagination__missing_document__should_raise_404(app, todo):
    with pytest.raises(NotFound):
        ListFieldPagination(todo.objects, ObjectId(), "comments", 1, 10)

    with pytest.raises(NotFound):
        todo.objects.paginate_field("comments", ObjectId(), 1, 10)


def test_list_field_pagination__page_out_of_range__should_raise_404(app, todo):
    doc = todo(title="t", comments=["a", "b"]).save()
    with pytest.raises(NotFound):
        ListFieldPagination(todo.objects, doc.id, "comments", 0, 10)
    with pytest.raises(NotFound):
        ListFieldPagination(todo.objects, doc.id, "comments", 2, 10)


def _test_paginator(paginator):
    assert paginator.pages == 5
    assert list(paginator.iter_pages()) == [1, 2, 3, 4, 5]

    for i in [1, 2, 3, 4, 5]:
        if i == 1:
            assert not paginator.has_prev
            with pytest.raises(NotFound):
                paginator.prev()
        else:
            assert paginator.has_prev

        if i == 5:
            assert not paginator.has_next
            with pytest.raises(NotFound):
                paginator.next()
        else:
            assert paginator.has_next

        if i == 3:
            assert list(paginator.iter_pages(0, 1, 1, 0)) == [None, 2, 3, 4, None]

        assert i == paginator.page
        assert i - 1 == paginator.prev_num
        assert i + 1 == paginator.next_num

        # Paginate to the next page
        if i < 5:
            paginator = paginator.next()
