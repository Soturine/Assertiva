import tempfile
from pathlib import Path
from scripts.summarize_junit import summarize

def test_summary_counts():
    xml = '<testsuite tests="3"><testcase classname="a" name="ok" time="0.1"/><testcase classname="a" name="bad" time="0.2"><failure message="boom">trace</failure></testcase><testcase classname="a" name="skip"><skipped/></testcase></testsuite>'
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'j.xml'
        p.write_text(xml, encoding='utf-8')
        result = summarize(p)
    assert result['executed'] == 3
    assert result['passed'] == 1
    assert result['failed'] == 1
    assert result['skipped'] == 1
    assert result['failures'][0]['id'] == 'a::bad'
