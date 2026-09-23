from casajev.desktop import DesktopObserver


def test_file_search_is_name_only_bounded_and_skips_hidden_folders(tmp_path):
    visible=tmp_path/'Documents';visible.mkdir()
    wanted=visible/'CasaJev Bericht.txt';wanted.write_text('kein Inhaltsindex')
    hidden=visible/'.private';hidden.mkdir();(hidden/'CasaJev Passwort.txt').write_text('secret')
    result=DesktopObserver([visible]).find_files('casajev')
    assert [item['path'] for item in result['matches']]==[str(wanted.resolve())]
    assert result['truncated'] is False


def test_process_parser_excludes_arguments_and_keeps_resource_metadata():
    rows=DesktopObserver._unix_processes(' 42 12.5 3.2 01:02 /Applications/Test App.app/Contents/MacOS/TestApp\n')
    assert rows==[{'pid':42,'cpu_percent':12.5,'memory_percent':3.2,
                  'elapsed':'01:02','name':'TestApp'}]
    assert 'arguments' not in rows[0]
