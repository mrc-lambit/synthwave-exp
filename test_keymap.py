from core.note_mapper import NoteMapper


def test_note_mapper_mapping() -> None:
    mapper = NoteMapper()

    assert mapper.key_to_midi('q') == 60
    assert mapper.key_to_midi('z') == 72
    assert mapper.key_to_midi('x') == 73
    assert mapper.key_to_midi('m') == 78


def test_four_octave_rows_exist() -> None:
    mapper = NoteMapper()
    rows = mapper.get_all_mapped_keys()

    assert len(rows) == 4
    assert rows[0][0] == 'a'
    assert rows[1][0] == 'q'
    assert rows[2][0] == 'z'
    assert rows[3][0] == '1'

    assert mapper.key_to_midi('a') == 48
    assert mapper.key_to_midi('q') == 60
    assert mapper.key_to_midi('z') == 72
    assert mapper.key_to_midi('1') == 84
