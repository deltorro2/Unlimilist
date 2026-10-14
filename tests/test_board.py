from datetime import date, datetime, timedelta

import pytest

from unlimilist.board import Board, InMemoryStore
from unlimilist.domain import Activity, DeleteRefused, InvalidTask, LaneKind, Stage, Task, UnfinishedSubtasks, Urgency


class FakeClock:
    """Starts at a fixed moment and advances one minute per reading."""

    def __init__(self, start=datetime(2026, 10, 12, 9, 0)):
        self.now = start

    def __call__(self):
        current = self.now
        self.now += timedelta(minutes=1)
        return current


@pytest.fixture
def board():
    return Board(clock=FakeClock())


def titles(tasks):
    return [t.title for t in tasks]


def test_new_task_goes_to_bottom_of_inbox_someday_lane(board):
    board.add_task("Buy milk")
    board.add_task("Call mom")

    lane = board.lane(Stage.INBOX, LaneKind.SOMEDAY)

    assert titles(lane) == ["Buy milk", "Call mom"]
    assert [t.priority for t in lane] == [1, 2]


def test_task_with_a_date_goes_to_time_limited_lane_without_priority(board):
    board.add_task("Buy milk")
    board.add_task("Pay rent", deadline=date(2026, 10, 31))
    board.add_task("Start course", due_date=date(2026, 11, 1))

    time_limited = board.lane(Stage.INBOX, LaneKind.TIME_LIMITED)

    assert titles(time_limited) == ["Pay rent", "Start course"]
    assert [t.priority for t in time_limited] == [None, None]
    assert titles(board.lane(Stage.INBOX, LaneKind.SOMEDAY)) == ["Buy milk"]


def test_time_limited_lane_is_ordered_by_earlier_date(board):
    board.add_task("Tax return", deadline=date(2026, 12, 1))
    board.add_task("Renovation", due_date=date(2026, 10, 20), deadline=date(2027, 3, 1))
    board.add_task("Dentist", deadline=date(2026, 10, 25))
    board.add_task("Course", due_date=date(2026, 11, 5))

    lane = board.lane(Stage.INBOX, LaneKind.TIME_LIMITED)

    assert titles(lane) == ["Renovation", "Dentist", "Course", "Tax return"]


def test_adding_with_priority_inserts_at_that_rank_and_shifts_the_rest(board):
    board.add_task("A")
    board.add_task("B")
    board.add_task("C")

    board.add_task("Urgent", priority=2)

    lane = board.lane(Stage.INBOX, LaneKind.SOMEDAY)
    assert titles(lane) == ["A", "Urgent", "B", "C"]
    assert [t.priority for t in lane] == [1, 2, 3, 4]


def test_priority_beyond_the_bottom_is_clamped_to_the_bottom(board):
    board.add_task("A")

    board.add_task("B", priority=99)

    assert [t.priority for t in board.lane(Stage.INBOX, LaneKind.SOMEDAY)] == [1, 2]


def test_moving_within_someday_lane_reranks_it(board):
    board.add_task("A")
    board.add_task("B")
    c = board.add_task("C")

    board.move_task(c.id, Stage.INBOX, priority=1)

    lane = board.lane(Stage.INBOX, LaneKind.SOMEDAY)
    assert titles(lane) == ["C", "A", "B"]
    assert [t.priority for t in lane] == [1, 2, 3]


def test_moving_to_another_stage_takes_the_drop_rank_and_closes_the_gap(board):
    a = board.add_task("A")
    board.add_task("B")
    board.add_task("C")
    board.move_task(a.id, Stage.IN_PROCESS)
    x = board.add_task("X")
    board.move_task(x.id, Stage.IN_PROCESS)
    b = board.lane(Stage.INBOX, LaneKind.SOMEDAY)[0]

    board.move_task(b.id, Stage.IN_PROCESS, priority=2)

    in_process = board.lane(Stage.IN_PROCESS, LaneKind.SOMEDAY)
    assert titles(in_process) == ["A", "B", "X"]
    assert [t.priority for t in in_process] == [1, 2, 3]
    inbox = board.lane(Stage.INBOX, LaneKind.SOMEDAY)
    assert titles(inbox) == ["C"]
    assert [t.priority for t in inbox] == [1]


def test_done_holds_both_kinds_most_recently_completed_first(board):
    a = board.add_task("A")
    b = board.add_task("B")
    rent = board.add_task("Pay rent", deadline=date(2026, 10, 31))

    board.move_task(a.id, Stage.DONE)
    board.move_task(rent.id, Stage.DONE)

    done = board.lane(Stage.DONE)
    assert titles(done) == ["Pay rent", "A"]
    assert all(t.priority is None for t in done)
    assert all(t.completed_at is not None for t in done)
    remaining = board.lane(Stage.INBOX, LaneKind.SOMEDAY)
    assert titles(remaining) == ["B"]
    assert remaining[0].priority == 1


def test_task_leaving_done_returns_to_the_lane_its_dates_imply(board):
    a = board.add_task("A")
    board.add_task("B")
    rent = board.add_task("Pay rent", deadline=date(2026, 10, 31))
    board.move_task(a.id, Stage.DONE)
    board.move_task(rent.id, Stage.DONE)

    board.move_task(a.id, Stage.INBOX, priority=1)
    board.move_task(rent.id, Stage.IN_PROCESS)

    someday = board.lane(Stage.INBOX, LaneKind.SOMEDAY)
    assert titles(someday) == ["A", "B"]
    assert [t.priority for t in someday] == [1, 2]
    assert someday[0].completed_at is None
    assert titles(board.lane(Stage.IN_PROCESS, LaneKind.TIME_LIMITED)) == ["Pay rent"]
    assert board.lane(Stage.DONE) == []


def test_editing_text_fields_keeps_the_task_in_place(board):
    board.add_task("A")
    b = board.add_task("B")

    board.edit_task(b.id, title="B2", details="**bold**", usable_data="[link](https://x.io)")

    lane = board.lane(Stage.INBOX, LaneKind.SOMEDAY)
    assert titles(lane) == ["A", "B2"]
    assert lane[1].details == "**bold**"
    assert lane[1].usable_data == "[link](https://x.io)"


def test_adding_a_date_converts_to_time_limited_and_drops_priority(board):
    a = board.add_task("A")
    board.add_task("B")

    board.edit_task(a.id, deadline=date(2026, 11, 1))

    time_limited = board.lane(Stage.INBOX, LaneKind.TIME_LIMITED)
    assert titles(time_limited) == ["A"]
    assert time_limited[0].priority is None
    someday = board.lane(Stage.INBOX, LaneKind.SOMEDAY)
    assert titles(someday) == ["B"]
    assert someday[0].priority == 1


def test_clearing_both_dates_converts_to_someday_at_the_bottom(board):
    board.add_task("A")
    board.add_task("B")
    rent = board.add_task("Pay rent", due_date=date(2026, 10, 25), deadline=date(2026, 10, 31))

    board.edit_task(rent.id, due_date=None, deadline=None)

    someday = board.lane(Stage.INBOX, LaneKind.SOMEDAY)
    assert titles(someday) == ["A", "B", "Pay rent"]
    assert someday[2].priority == 3
    assert board.lane(Stage.INBOX, LaneKind.TIME_LIMITED) == []


def test_editing_priority_moves_the_task_to_that_rank(board):
    board.add_task("A")
    board.add_task("B")
    c = board.add_task("C")

    board.edit_task(c.id, priority=1)

    assert titles(board.lane(Stage.INBOX, LaneKind.SOMEDAY)) == ["C", "A", "B"]


@pytest.mark.parametrize("title", ["", "   "])
def test_title_is_required(board, title):
    with pytest.raises(InvalidTask, match="Title"):
        board.add_task(title)


def test_blank_title_is_rejected_on_edit_and_the_task_is_unchanged(board):
    a = board.add_task("A")

    with pytest.raises(InvalidTask, match="Title"):
        board.edit_task(a.id, title=" ")

    assert titles(board.lane(Stage.INBOX, LaneKind.SOMEDAY)) == ["A"]


def test_due_date_cannot_be_after_deadline(board):
    with pytest.raises(InvalidTask, match="Due date"):
        board.add_task("Trip", due_date=date(2026, 11, 2), deadline=date(2026, 11, 1))

    trip = board.add_task("Trip", due_date=date(2026, 11, 1), deadline=date(2026, 11, 1))
    with pytest.raises(InvalidTask, match="Due date"):
        board.edit_task(trip.id, deadline=date(2026, 10, 30))


def test_deleting_a_task_closes_the_gap(board):
    a = board.add_task("A")
    board.add_task("B")

    board.delete_task(a.id)

    lane = board.lane(Stage.INBOX, LaneKind.SOMEDAY)
    assert titles(lane) == ["B"]
    assert lane[0].priority == 1


# FakeClock's "today" is 12/10/2026.
@pytest.mark.parametrize(
    ("due_date", "deadline", "stage", "expected"),
    [
        (None, None, Stage.INBOX, Urgency.NONE),
        (None, date(2026, 10, 11), Stage.IN_PROCESS, Urgency.OVERDUE),
        (None, date(2026, 10, 12), Stage.IN_PROCESS, Urgency.DUE_SOON),
        (None, date(2026, 10, 13), Stage.INBOX, Urgency.DUE_SOON),
        (None, date(2026, 10, 14), Stage.INBOX, Urgency.NONE),
        (date(2026, 10, 11), date(2026, 10, 30), Stage.INBOX, Urgency.START_PASSED),
        (date(2026, 10, 11), date(2026, 10, 30), Stage.IN_PROCESS, Urgency.NONE),
        (date(2026, 10, 11), date(2026, 10, 13), Stage.INBOX, Urgency.START_PASSED),  # late outranks Due soon
        (date(2026, 10, 12), None, Stage.INBOX, Urgency.NONE),
        (date(2026, 10, 1), date(2026, 10, 11), Stage.INBOX, Urgency.OVERDUE),
        (None, date(2026, 10, 1), Stage.DONE, Urgency.NONE),
    ],
)
def test_urgency(board, due_date, deadline, stage, expected):
    task = board.add_task("T", due_date=due_date, deadline=deadline)
    board.move_task(task.id, stage)

    assert board.urgency(task.id) == expected


def test_a_reopened_board_shows_the_same_tasks():
    store = InMemoryStore()
    board = Board(store=store, clock=FakeClock())
    a = board.add_task("A", details="notes")
    board.add_task("B")
    rent = board.add_task("Pay rent", deadline=date(2026, 10, 31))
    gone = board.add_task("Gone")
    board.move_task(a.id, Stage.IN_PROCESS)
    board.move_task(rent.id, Stage.DONE)
    board.delete_task(gone.id)

    reopened = Board(store=store, clock=FakeClock())

    assert reopened.lane(Stage.INBOX, LaneKind.SOMEDAY) == board.lane(Stage.INBOX, LaneKind.SOMEDAY)
    assert reopened.lane(Stage.IN_PROCESS, LaneKind.SOMEDAY) == board.lane(Stage.IN_PROCESS, LaneKind.SOMEDAY)
    assert reopened.lane(Stage.DONE) == board.lane(Stage.DONE)
    assert titles(reopened.lane(Stage.IN_PROCESS, LaneKind.SOMEDAY)) == ["A"]
    assert reopened.task(a.id).details == "notes"


def test_opening_a_board_repairs_duplicate_and_missing_priorities():
    created = datetime(2026, 10, 1)
    store = InMemoryStore(
        [
            Task(id="c", title="C", stage=Stage.INBOX, created_at=created, priority=7),
            Task(id="a", title="A", stage=Stage.INBOX, created_at=created, priority=2),
            Task(id="b", title="B", stage=Stage.INBOX, created_at=created, priority=2),
            Task(id="d", title="D", stage=Stage.INBOX, created_at=created, priority=None),
        ]
    )

    board = Board(store=store, clock=FakeClock())

    lane = board.lane(Stage.INBOX, LaneKind.SOMEDAY)
    assert titles(lane) == ["A", "B", "C", "D"]
    assert [t.priority for t in lane] == [1, 2, 3, 4]


def test_column_interleaves_first_time_limited_then_top_five_someday(board):
    for n in range(1, 9):
        board.add_task(f"S{n}")
    for n in range(1, 4):
        board.add_task(f"T{n}", deadline=date(2026, 11, n))

    assert titles(board.column(Stage.INBOX)) == [
        "T1", "S1", "S2", "S3", "S4", "S5", "T2", "T3", "S6", "S7", "S8",
    ]


def test_column_with_only_one_kind_is_just_that_lane(board):
    board.add_task("S1")
    board.add_task("S2")
    t = board.add_task("T1", deadline=date(2026, 11, 1))
    board.move_task(t.id, Stage.IN_PROCESS)

    assert titles(board.column(Stage.INBOX)) == ["S1", "S2"]
    assert titles(board.column(Stage.IN_PROCESS)) == ["T1"]


def test_done_column_is_the_done_lane(board):
    a = board.add_task("A")
    t = board.add_task("T", deadline=date(2026, 11, 1))
    board.move_task(a.id, Stage.DONE)
    board.move_task(t.id, Stage.DONE)

    assert titles(board.column(Stage.DONE)) == ["T", "A"]


def test_a_task_with_unfinished_subtasks_cannot_enter_done(board):
    task = board.add_task("Ship", details="- [x] Build\n- [ ] Test\n- [ ] Release\n\nNotes")

    with pytest.raises(UnfinishedSubtasks) as refused:
        board.move_task(task.id, Stage.DONE)

    assert refused.value.count == 2
    assert board.task(task.id).stage == Stage.INBOX


def test_a_task_whose_subtasks_are_all_finished_can_enter_done(board):
    task = board.add_task("Ship", details="- [x] Build\n- [X] Test")

    board.move_task(task.id, Stage.DONE)

    assert board.task(task.id).stage == Stage.DONE


def test_a_done_task_keeps_its_place_when_a_subtask_is_unticked(board):
    task = board.add_task("Ship", details="- [x] Build")
    board.move_task(task.id, Stage.DONE)

    board.edit_task(task.id, details="- [ ] Build\n- [ ] Celebrate")
    board.move_task(task.id, Stage.DONE, priority=1)

    assert board.task(task.id).stage == Stage.DONE


def test_a_task_in_process_cannot_be_deleted(board):
    task = board.add_task("Write report")
    board.move_task(task.id, Stage.IN_PROCESS)

    with pytest.raises(DeleteRefused):
        board.delete_task(task.id)

    assert board.task(task.id).stage == Stage.IN_PROCESS


def test_a_new_task_is_a_general_task_unless_another_activity_is_given(board):
    plain = board.add_task("Plan the garden")
    call = board.add_task("Call the bank", activity=Activity.PHONE_CALL)

    assert board.task(plain.id).activity == Activity.GENERAL_TASK
    assert board.task(call.id).activity == Activity.PHONE_CALL


def test_changing_the_activity_keeps_the_task_in_place(board):
    board.add_task("A")
    b = board.add_task("B")

    board.edit_task(b.id, activity=Activity.MEETING)

    assert board.task(b.id).activity == Activity.MEETING
    assert titles(board.lane(Stage.INBOX, LaneKind.SOMEDAY)) == ["A", "B"]


def test_a_task_has_the_tags_in_its_details_in_the_order_first_written(board):
    task = board.add_task("T", details="Call #Client-X about #invoice_2\n\n- [ ] send #INVOICE_2 and #client-x again")

    assert task.tags == ("Client-X", "invoice_2")


@pytest.mark.parametrize(
    ("details", "tags"),
    [
        ("\\#home is escaped at the start of a line", ("home",)),
        ("(see #work), then #done.", ("work", "done")),
        ("https://site.com/page#section and issue#12", ()),
        ("`#define` in code and [#link](https://a.com/#frag)", ()),
        ("```\n#fenced\n```\n\nafter #real", ("real",)),
        ("# Heading, #1 and #-dash are not tags", ()),
    ],
)
def test_a_hash_starts_a_tag_only_at_the_start_of_a_word_and_outside_code_and_links(board, details, tags):
    assert board.add_task("T", details=details).tags == tags


def test_tags_are_not_read_from_the_title_or_usable_data(board):
    assert board.add_task("Pay #rent", usable_data="#bank").tags == ()


def test_board_lists_its_tags_a_to_z_with_how_many_tasks_have_each(board):
    board.add_task("A", details="#Work and #home")
    board.add_task("B", details="#work")
    done = board.add_task("C", details="#zoo #work")
    board.move_task(done.id, Stage.DONE)

    assert board.tags() == [("home", 1), ("Work", 3), ("zoo", 1)]  # spelled as first used


def test_board_tags_follow_edits_and_deletes(board):
    a = board.add_task("A", details="#home")
    b = board.add_task("B", details="#home #car")

    board.edit_task(a.id, details="#garden")
    board.delete_task(b.id)

    assert board.tags() == [("garden", 1)]


def test_tags_already_in_task_files_are_listed_when_the_board_opens():
    store = InMemoryStore([Task(id="t1", title="T", stage=Stage.INBOX, created_at=datetime(2026, 10, 1), details="#home")])

    assert Board(store, clock=FakeClock()).tags() == [("home", 1)]


def test_a_tag_filter_matches_tasks_with_any_selected_tag_ignoring_case(board):
    work = board.add_task("A", details="#Work")
    home = board.add_task("B", details="#home #car")
    untagged = board.add_task("C")

    shown = [t.title for t in (work, home, untagged) if t.matches_tag_filter({"work", "car"})]

    assert shown == ["A", "B"]
    assert untagged.matches_tag_filter(set())  # an empty filter shows everything


def test_tag_suggestions_put_prefix_matches_first_then_fuzzy_ones_most_used_first(board):
    board.add_task("A", details="#work #wiki #weekly #network")
    board.add_task("B", details="#work #wiki")
    board.add_task("C", details="#work #home")

    assert board.suggest_tags("w") == ["work", "wiki", "weekly", "network"]
    assert board.suggest_tags("wk") == ["work", "wiki", "network", "weekly"]  # equally used: A to Z
    assert board.suggest_tags("WE") == ["weekly"]
    assert board.suggest_tags("xyz") == []
