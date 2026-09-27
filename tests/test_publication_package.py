"""Check lossless trajectory packaging and the six published replay commands."""

import gzip
import hashlib
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import package_publication_data as package  # noqa: E402
import run_calculation as runner  # noqa: E402


def sample_dump():
    """Keep deliberately precise decimal text, which projection must not round."""
    frames = []
    for step in (0, 1000, 2000):
        frames.append(
            f"ITEM: TIMESTEP\n{step}\nITEM: NUMBER OF ATOMS\n2\n"
            "ITEM: BOX BOUNDS pp pp ff\n0 10\n0 20\n-5 30\n"
            "ITEM: ATOMS id type x y z c_st[5]\n"
            "1 1 1.1234567890 2.0 3.00 -1.01010e+03\n"
            "2 2 4.1234567890 5.0 6.00 +1.01010e+03\n"
        )
    return "".join(frames).encode()


def test_full_column_shards_recover_every_source_byte(monkeypatch):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        monkeypatch.setattr(package, "ROOT", root)
        source = root / "source.dump"
        source.write_bytes(sample_dump())
        result = package.positions(source, root / "alloy", 2, full_columns=True)
        recovered = b"".join(
            gzip.decompress((root / p["path"]).read_bytes()) for p in result["outputs"]
        )
        assert recovered == sample_dump()
        assert hashlib.sha256(recovered).hexdigest() == result["source"]["sha256"]
        assert result["timesteps"] == [0, 1000, 2000]
        assert result["omitted_columns"] == []


def test_position_projection_preserves_decimal_coordinates(monkeypatch):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        monkeypatch.setattr(package, "ROOT", root)
        source = root / "source.dump"
        source.write_bytes(sample_dump())
        result = package.positions(source, root / "positions", 2)
        recovered = b"".join(
            gzip.decompress((root / p["path"]).read_bytes()) for p in result["outputs"]
        )
        assert recovered.count(b"ITEM: TIMESTEP") == 3
        assert recovered.count(b"1 1 1.1234567890 2.0 3.00\n") == 3
        assert b"c_st[5]" not in recovered
        assert len(result["outputs"]) == 2


def test_replay_commands_use_available_inputs_without_running_lammps():
    cases = (
        "interface_control",
        "interface_strained",
        "g15_free_control",
        "g15_held_control",
        "g15_held_strained",
        "alloy",
    )
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "unused"
        for case in cases:
            command, initial = runner.command(case, "lmp", output, kokkos=False)
            assert initial.is_file()
            assert command[0] == "lmp"
            assert Path(command[command.index("-in") + 1]).is_file()
        assert not output.exists()


def test_held_ramp_preserves_the_original_loading_rate_with_rounding():
    _, _, held = runner.specification("g15_held_control")
    _, _, free = runner.specification("g15_free_control")

    def rate(settings):
        return settings["TAUMAX_MPA"] / (settings["NSTEPS"] - 5000 - 8000)

    assert abs(rate(held) / rate(free) - 1) < 4e-5
    assert held["HOLD_INCL"] == 1
    assert free["HOLD_INCL"] == 0
