from ledgerlite.release import revision


def test_revision_is_a_sha():
    assert len(revision()) == 40
