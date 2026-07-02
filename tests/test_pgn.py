import io
import chess.pgn

def validate_pgn_helper(text):
    text = text.strip()
    if not text:
        return True
    pgn_io = io.StringIO(text)
    try:
        game = chess.pgn.read_game(pgn_io)
        if game is None:
            return False
        if game.errors:
            return False
        has_moves = any(True for _ in game.mainline_moves())
        has_brackets = "[" in text and "]" in text
        if not has_moves and not has_brackets:
            return False
        return True
    except Exception:
        return False

def test_validate_pgn_valid_moves():
    pgn_data = "1. e4 e5 2. Nf3 Nc6 3. Bb5"
    assert validate_pgn_helper(pgn_data) is True

def test_validate_pgn_valid_headers():
    pgn_data = '[Event "Test Event"]\n[Result "*"]\n*'
    assert validate_pgn_helper(pgn_data) is True

def test_validate_pgn_invalid_moves():
    pgn_data = "1. e5 e4"  # Black e5 on move 1 is illegal
    assert validate_pgn_helper(pgn_data) is False

def test_validate_pgn_random_text():
    pgn_data = "this is some random text that is not a pgn"
    assert validate_pgn_helper(pgn_data) is False

def test_validate_pgn_empty():
    assert validate_pgn_helper("") is True

def test_pgn_header_injection():
    pgn_data = "1. e4 e5 2. Nf3 Nc6"
    game = chess.pgn.read_game(io.StringIO(pgn_data))
    assert game is not None
    
    # Inject tournament tags
    game.headers["Event"] = "Spring Tournament"
    game.headers["Site"] = "Rome, ITA"
    game.headers["Date"] = "2026.07.02"
    game.headers["Round"] = "3"
    game.headers["White"] = "Rossi, Mario"
    game.headers["Black"] = "Bianchi, Luigi"
    game.headers["Result"] = "1-0"
    game.headers["WhiteElo"] = "1650"
    game.headers["BlackElo"] = "1420"
    
    exporter = chess.pgn.StringExporter(headers=True, comments=True, variations=True)
    modified = game.accept(exporter)
    
    # Reload and assert headers are present
    reloaded_game = chess.pgn.read_game(io.StringIO(modified))
    assert reloaded_game.headers["Event"] == "Spring Tournament"
    assert reloaded_game.headers["Site"] == "Rome, ITA"
    assert reloaded_game.headers["Date"] == "2026.07.02"
    assert reloaded_game.headers["Round"] == "3"
    assert reloaded_game.headers["White"] == "Rossi, Mario"
    assert reloaded_game.headers["Black"] == "Bianchi, Luigi"
    assert reloaded_game.headers["Result"] == "1-0"
    assert reloaded_game.headers["WhiteElo"] == "1650"
    assert reloaded_game.headers["BlackElo"] == "1420"
