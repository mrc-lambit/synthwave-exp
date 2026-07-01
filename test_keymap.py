from core.note_mapper import NoteMapper


def test_note_mapper_mapping() -> None:
    mapper = NoteMapper()

    assert mapper.key_to_midi('q') == 60
    assert mapper.key_to_midi('z') == 72
    assert mapper.key_to_midi('x') == 74
    assert mapper.key_to_midi('m') == 83


m = NoteMapper()
upper, lower = m.get_all_mapped_keys()

print("Row 1 (upper):", " ".join(upper))
print("Row 2 (lower):", " ".join(lower))

# Test some keys
print("\nKey mapping test:")
for key in ['z', 's', 'x', 'd', 'c']:
    info = m.get_key_info(key)
    if info:
        print(f"  {key} -> {info['note_name']} ({info['frequency']:.1f} Hz)")

for key in ['q', '2', 'w', '3', 'e']:
    info = m.get_key_info(key)
    if info:
        print(f"  {key} -> {info['note_name']} ({info['frequency']:.1f} Hz)")


test_note_mapper_mapping()
