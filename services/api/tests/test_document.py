from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

import pytest
from pypdf import PdfWriter

from app.agents.document import MAX_BYTES, MAX_STREAM_BYTES, DocumentStore
from app.providers import ProviderError


def pdf_bytes(*texts):
    """Small real text PDFs, with no optional fixture-generation dependency."""
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    writer = PdfWriter()
    for text in texts:
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                                 NameObject('/Subtype'): NameObject('/Type1'),
                                 NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
        stream = DecodedStreamObject()
        stream.set_data(f'BT /F1 12 Tf 50 700 Td ({text}) Tj ET'.encode())
        page[NameObject('/Contents')] = writer._add_object(stream)
    data = BytesIO()
    writer.write(data)
    return data.getvalue()


def ask(store, upload, query):
    return store.answer(upload['document_id'], upload['document_token'], query)


def test_real_pdf_retrieval_cites_correct_page_and_verbatim_excerpt():
    store = DocumentStore()
    uploaded = store.ingest(pdf_bytes('Solar panels reduce electricity costs.', 'Battery storage costs 1200 dollars.'), 'study.pdf')
    result = ask(store, uploaded, 'What does battery storage cost?')
    assert uploaded['pages'] == 2
    assert result['citations'][0]['page'] == 2
    assert result['citations'][0]['excerpt'] == 'Battery storage costs 1200 dollars.'
    assert result['citations'][0]['id'] == 'D1'
    assert result['citations'][0]['document_id'] == uploaded['document_id']
    assert 'no language model' in result['answer']


def test_abstains_for_unrelated_question():
    store = DocumentStore()
    uploaded = store.ingest(b'Battery storage costs 1200 dollars.', 'notes.txt')
    result = ask(store, uploaded, 'Who invented submarines?')
    assert result['source_count'] == 0
    assert result['citations'] == []
    assert 'Insufficient evidence' in result['answer']


def test_summary_uses_representative_pages():
    store = DocumentStore()
    upload = store.ingest(pdf_bytes('First topic.', 'Second topic.', 'Third topic.', 'Fourth topic.'), 'notes.pdf')
    result = ask(store, upload, 'Summarize this PDF')
    assert [c['page'] for c in result['citations']] == [1, 2, 3]
    assert 'not a generated summary' in result['answer']


def test_cross_document_and_missing_token_are_denied():
    store = DocumentStore()
    first = store.ingest(b'Secret apple plans.', 'first.txt')
    second = store.ingest(b'Secret orange plans.', 'second.txt')
    for token in ('', second['document_token'], 'invalid', 'unicode-\u2603'):
        with pytest.raises(ProviderError) as failure:
            store.answer(first['document_id'], token, 'secret')
        assert failure.value.status == 404
    result = ask(store, second, 'apple')
    assert result['citations'] == []


def test_document_is_scoped_to_authenticated_owner():
    store = DocumentStore()
    upload = store.ingest(b'Private roadmap details.', 'roadmap.txt', owner_id='user-a')
    result = store.answer(
        upload['document_id'], upload['document_token'], 'roadmap', owner_id='user-a'
    )
    assert result['source_count'] == 1
    with pytest.raises(ProviderError) as denied:
        store.answer(
            upload['document_id'], upload['document_token'], 'roadmap', owner_id='user-b'
        )
    assert denied.value.status == 404


@pytest.mark.parametrize('data,name,code', [
    (b'', 'empty.txt', 'document_size'),
    (b'x' * (MAX_BYTES + 1), 'big.txt', 'document_size'),
    (b'not pdf', 'bad.pdf', 'document_invalid'),
    (b'%PDF-1.7 broken', 'bad.pdf', 'document_invalid'),
    (b'hello', 'bad.exe', 'document_type'),
    (b'\xff\xfe', 'bad.txt', 'document_encoding'),
    (b'\x00binary', 'bad.txt', 'document_encoding'),
    (b'   ', 'empty.txt', 'document_no_text'),
    (b'x' * 200001, 'large.txt', 'document_text_size'),
], ids=['empty', 'oversize', 'signature', 'malformed', 'extension', 'encoding', 'binary', 'blank', 'textlimit'])
def test_invalid_uploads(data, name, code):
    with pytest.raises(ProviderError) as failure:
        DocumentStore().ingest(data, name)
    assert failure.value.code == code


def test_pdf_bounds_encryption_and_no_text():
    for kind, expected in [('blank', 'document_no_text'), ('encrypted', 'document_encrypted'), ('pages', 'document_pages')]:
        writer = PdfWriter()
        for _ in range(31 if kind == 'pages' else 1):
            writer.add_blank_page(width=100, height=100)
        if kind == 'encrypted':
            writer.encrypt('secret')
        data = BytesIO()
        writer.write(data)
        with pytest.raises(ProviderError) as failure:
            DocumentStore().ingest(data.getvalue(), 'test.pdf')
        assert failure.value.code == expected


def test_expiry_capacity_and_delete(monkeypatch):
    clock = [100]
    monkeypatch.setattr('app.agents.document.time.monotonic', lambda: clock[0])
    store = DocumentStore(ttl_seconds=10, max_documents=1)
    upload = store.ingest(b'Hello world.', '../../notes.txt')
    assert upload['filename'] == 'notes.txt'
    with pytest.raises(ProviderError) as failure:
        store.ingest(b'Other text.', 'other.txt')
    assert failure.value.code == 'document_capacity'
    clock[0] = 111
    with pytest.raises(ProviderError) as failure:
        ask(store, upload, 'hello')
    assert failure.value.code == 'document_not_found'
    new = store.ingest(b'New text.', 'new.txt')
    store.delete(new['document_id'], new['document_token'])
    with pytest.raises(ProviderError):
        ask(store, new, 'new')


def test_concurrent_ingest_preserves_capacity():
    store = DocumentStore(max_documents=2)
    def upload(index):
        try:
            return store.ingest(b'Hello world.', f'{index}.txt')
        except ProviderError as exc:
            assert exc.code == 'document_capacity'
            return None
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(upload, range(10)))
    assert sum(result is not None for result in results) == 2


def test_untrusted_markdown_is_escaped_in_answer():
    store = DocumentStore()
    upload = store.ingest(b'Click [link](https://bad.invalid) for battery evidence.', 'notes.txt')
    result = ask(store, upload, 'battery')
    assert r'\[link\]' in result['answer']
    assert result['citations'][0]['excerpt'].startswith('Click [link]')


def test_concise_exact_sentence_preserves_page_provenance():
    store = DocumentStore()
    target = 'The battery installation budget is 1200 dollars.'
    page = 'General background information. ' * 10 + target + ' Further background discussion.' * 10
    upload = store.ingest(pdf_bytes('An unrelated introduction.', page), 'budget.pdf')
    result = ask(store, upload, 'What is the battery installation budget?')
    assert result['citations'][0]['excerpt'] == target
    assert result['citations'][0]['page'] == 2


def test_long_sentence_window_and_summary_are_exact_bounded_substrings():
    store = DocumentStore()
    source = 'background ' * 45 + 'battery budget 1200 dollars ' + 'additional ' * 35
    upload = store.ingest(source.encode(), 'long.txt')
    for query in ('battery budget', 'summarize'):
        excerpt = ask(store, upload, query)['citations'][0]['excerpt']
        assert len(excerpt) <= 500
        assert excerpt in source
        if query == 'battery budget':
            assert 'battery budget 1200 dollars' in excerpt


def test_weak_secondary_page_match_is_filtered():
    store = DocumentStore()
    upload = store.ingest(pdf_bytes('Battery installation budget is 1200 dollars.', 'A general budget overview.'), 'notes.pdf')
    result = ask(store, upload, 'battery installation budget')
    assert [c['page'] for c in result['citations']] == [1]


@pytest.mark.parametrize('compressed', [True, False], ids=['compressed', 'declared-length'])
def test_pdf_stream_resource_limit_before_text_extraction(compressed, monkeypatch):
    from pypdf._page import PageObject
    from pypdf.generic import DecodedStreamObject, NameObject
    writer = PdfWriter()
    page = writer.add_blank_page(width=100, height=100)
    stream = DecodedStreamObject()
    stream.set_data(b' ' * (MAX_STREAM_BYTES + 1))
    page[NameObject('/Contents')] = writer._add_object(stream.flate_encode() if compressed else stream)
    data = BytesIO()
    writer.write(data)
    assert len(data.getvalue()) < MAX_BYTES
    def extraction_must_not_run(*args, **kwargs):
        pytest.fail('Oversized stream reached text extraction')
    monkeypatch.setattr(PageObject, 'extract_text', extraction_must_not_run)
    with pytest.raises(ProviderError) as failure:
        DocumentStore().ingest(data.getvalue(), 'large-stream.pdf')
    assert failure.value.code == 'document_resource_limit'
    assert failure.value.status == 413

