
from teleop.gello_cr.tests.fakes.paths import implementation_path


def test_new_bootstrap_has_no_qt_dependency() -> None:
    for name in ('bootstrap/runtime_factory.py', 'recording/source.py'):
        source = implementation_path('teleop/gello_cr/' + name).read_text(encoding='utf-8')
        assert 'PyQt5' not in source
        assert 'PySide6' not in source
        assert 'TEST_INEXBOT' not in source


def test_factory_uses_package_runtime_and_recorder() -> None:
    source = implementation_path('teleop/gello_cr/bootstrap/runtime_factory.py').read_text(encoding='utf-8')
    assert "teleop_runtime" not in source
    assert "lerobot_recorder" not in source


def test_cr3a_lifecycle_is_explicit_not_constructor_side_effect() -> None:
    source = implementation_path('teleop/gello_cr/bootstrap/runtime_factory.py').read_text(encoding='utf-8')
    init_block = source.split('class Cr3aLifecycle:', 1)[1].split(
        '    def _event(', 1
    )[0]
    assert '.connect(' not in init_block
    assert '.power_on(' not in init_block


def test_capture_source_builds_canonical_frames():
    source = implementation_path('teleop/gello_cr/recording/source.py').read_text(encoding='utf-8')
    assert "CaptureFrame(" in source
    assert "observation.images." not in source
